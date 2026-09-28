"""Fixed-horizon censoring analysis. S(t)=Pr(T>t), RMST=sum S(t), t=0..H-1.

All jobs have the same administrative cutoff. No early censoring is supported:
empirical survival is simply the proportion whose first event has not occurred.
"""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import numpy as np
from .analysis import write_csv, wilson, bootstrap_mean
from .persistence_theory import METRICS, predict


def empirical_survival(times, horizon):
    values = np.array([horizon+1 if x is None else x for x in times], int)
    counts = np.bincount(values, minlength=horizon+2)
    return 1-np.cumsum(counts[:horizon+1])/len(values)


def analyze(folder, bootstrap=1000, max_plots=12):
    folder=Path(folder); manifest=json.loads((folder/'manifest.json').read_text())
    config=manifest['config']; H=config['horizon']; reports=folder/'analysis'
    reports.mkdir(exist_ok=True)
    completed=[]; skipped=[]
    for path in sorted((folder/'records').glob('*.json')):
        record=json.loads(path.read_text())
        (completed if record['status']=='complete' else skipped).append(record)
    if not completed: raise ValueError('No complete paired jobs to analyze')
    groups=defaultdict(list); conditions={}; flat=[]; paired=[]
    for job in completed:
        c=job['condition']; cid=job['condition_id']; conditions[cid]=c
        by_arm={r['arm']:r for r in job['paired']}
        for arm, result in by_arm.items():
            groups[(cid,result['branch'],arm)].append(result)
            row={'job_id':job['id'],'condition_id':cid,'seed':job['seed'],
                 'design':c['design'],'mode':c['mode'],'rule':c['learner']['rule'],
                 'eta':c['eta'],'C':c['C'],'Delta':c['Delta'],
                 'initialization':json.dumps(c['initialization'],sort_keys=True)}
            for k,v in result.items():
                if k=='times': row.update(v)
                elif k=='censored': row.update({m+'_censored':x for m,x in v.items()})
                else: row[k]=json.dumps(v) if isinstance(v,list) else v
            flat.append(row)
        for metric in METRICS:
            times=[by_arm[a]['times'][metric] for a in ['faa','clean']]
            restricted=[H if t is None else t for t in times]
            paired.append({'condition_id':cid,'seed':job['seed'],'branch':by_arm['faa']['branch'],
                           'metric':metric,'faa_minus_clean_restricted_time':restricted[0]-restricted[1]})
    write_csv(reports/'runs.csv',flat); write_csv(reports/'skipped.csv',skipped)
    write_csv(reports/'paired_differences.csv',paired)
    summaries=[]; curves={}; cache={}; rng=np.random.default_rng(481)
    grid=np.unique(np.r_[np.arange(0,H+1,max(1,H//200)),H])
    survival_file=(reports/'survival.csv').open('w',newline='')
    writer=csv.writer(survival_file)
    writer.writerow(['condition_id','branch','arm','metric','t','survival','pointwise_low',
                     'pointwise_high','theory_survival'])
    for (cid,branch,arm), rows in groups.items():
        c=conditions[cid]; predictions=[]
        for row in rows:
            # Warm-up studies are empirical generalization, not this idealized theorem.
            key=json.dumps([row['post_q'],row['post_counts'],row['intervention_action'],c['learner']],sort_keys=True)
            if c['mode']=='controlled':
                if key not in cache:
                    cache[key]=predict(row['post_q'],row['post_counts'],config['rewards'],
                        row['intervention_action'],c['learner'],H,config['q_tolerance'],config['confirmation_window'])
                predictions.append(cache[key])
            else: predictions.append(None)
        eligible=all(x is not None for x in predictions)
        n=len(rows); stochastic=c['learner']['rule']!='ucb'
        for metric in METRICS:
            times=[r['times'][metric] for r in rows]
            surv=empirical_survival(times,H)
            theory=np.mean([p['curves'][metric] for p in predictions],axis=0) if eligible else None
            restricted=[H if t is None else t for t in times]
            mean,low,high,_=bootstrap_mean(restricted,rng,bootstrap)
            if not stochastic: low=high=None
            median_indices=np.flatnonzero(surv<=.5)
            q25=np.flatnonzero(surv<=.75);q75=np.flatnonzero(surv<=.25)
            theoretical_means=[p['summaries'][metric]['mean'] for p in predictions] if eligible else []
            full_theory=(float(np.mean(theoretical_means)) if theoretical_means and
                         all(x is not None and math.isfinite(x) for x in theoretical_means) else None)
            dkw=math.sqrt(math.log(2/.05)/(2*n)) if stochastic else None
            difference=float(np.max(np.abs(surv-theory))) if eligible else None
            paired_values=[p['faa_minus_clean_restricted_time'] for p in paired
                           if p['condition_id']==cid and p['branch']==branch and p['metric']==metric]
            pairmean,pairlow,pairhigh,_=bootstrap_mean(paired_values,rng,bootstrap)
            if not stochastic: pairlow=pairhigh=None
            summary={'condition_id':cid,'design':c['design'],'mode':c['mode'],
                'initialization':json.dumps(c['initialization'],sort_keys=True),
                'rule':c['learner']['rule'],'branch_request':c['branch_request'],'branch':branch,
                'arm':arm,'eta':c['eta'],'C':c['C'],'Delta':c['Delta'],'metric':metric,'n':n,
                'horizon':H,'recovered':sum(t is not None for t in times),
                'censored':sum(t is None for t in times),'survival_at_horizon':float(surv[-1]),
                'q25':int(q25[0]) if len(q25) else None,
                'median':int(median_indices[0]) if len(median_indices) else None,
                'q75':int(q75[0]) if len(q75) else None,
                'restricted_mean':mean,'restricted_mean_ci_low':low,'restricted_mean_ci_high':high,
                'observed_mean_if_no_censoring':float(np.mean(times)) if all(t is not None for t in times) else None,
                'spent_mean':float(np.mean([r['spent'] for r in rows])),
                'spent_min':min(r['spent'] for r in rows),'spent_max':max(r['spent'] for r in rows),
                'attainment_rate':float(np.mean([r['attained_target'] for r in rows])),
                'clipped_count':sum(r['clipped_by_delta'] or r['clipped_by_budget'] for r in rows),
                'pre_q_error_mean':float(np.mean([r['pre_q_error'] for r in rows])),
                'pre_count_optimal_mean':float(np.mean([r['pre_counts'][0] for r in rows])),
                'pre_count_other_mean':float(np.mean([r['pre_counts'][1] for r in rows])),
                'theory_eligible':eligible,'theory_full_mean':full_theory,
                'theory_restricted_mean':float(theory[:-1].sum()) if eligible else None,
                'max_survival_discrepancy':difference,'dkw_95_radius':dkw,
                'within_dkw_band':bool(difference<=dkw) if eligible and stochastic else None,
                'paired_faa_minus_clean_restricted_mean':pairmean,
                'paired_difference_ci_low':pairlow,'paired_difference_ci_high':pairhigh}
            summaries.append(summary)
            curves[(cid,branch,arm,metric)]=(surv,theory)
            for t in grid:
                count=sum(x is None or x>t for x in times)
                lo,hi=wilson(count,n) if stochastic else (None,None)
                writer.writerow([cid,branch,arm,metric,int(t),surv[t],lo,hi,
                                 theory[t] if eligible else None])
    survival_file.close(); write_csv(reports/'summary.csv',summaries)
    # Per-condition figures keep counts, caps and branch fixed. No pooled ranking.
    if max_plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        keys=sorted(set((cid,b) for cid,b,_ in groups))[:max_plots]
        for cid,branch in keys:
            c=conditions[cid];fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
            for ax,metric in zip(axes.flat,METRICS):
                for arm,color in [('clean','C0'),('faa','C1')]:
                    if (cid,branch,arm,metric) not in curves: continue
                    empirical,theory=curves[(cid,branch,arm,metric)]
                    ax.step(np.arange(H+1),empirical,where='post',color=color,label=arm+' empirical')
                    if theory is not None: ax.plot(theory,'--',color=color,label=arm+' exact')
                ax.set(title=metric.replace('_',' '),xlabel='Clean steps since intervention',ylabel='Fraction not yet recovered' if metric!='first_revisit' else 'Fraction not yet revisited',ylim=(-.02,1.02))
                ax.legend(fontsize=7)
            fig.suptitle(f'{c["design"]}: {c["learner"]["rule"]}, {branch}; eta={c["eta"]}, C={c["C"]}, Delta={c["Delta"]}\n{c["initialization"]}',fontsize=10)
            fig.savefig(reports/f'survival_{cid}_{branch}.png',dpi=140);plt.close(fig)
        faa=[s for s in summaries if s['arm']=='faa' and s['metric']=='q_recovery']
        fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
        for ax,mode in zip(axes,['controlled','warmup']):
            for rule,color in [('epsilon_greedy','C0'),('softmax','C1'),('ucb','C2')]:
                for branch,marker in [('demotion','o'),('promotion','^')]:
                    selected=[s for s in faa if s['mode']==mode and s['rule']==rule and s['branch']==branch]
                    if selected: ax.scatter([s['spent_mean'] for s in selected],[s['restricted_mean'] for s in selected],color=color,marker=marker,label=f'{rule}: {branch}')
            ax.set(title=mode+' (each point is one condition)',xlabel='Actual absolute reward expenditure',ylabel=f'Mean min(Q recovery time, {H})')
            if ax.collections: ax.legend(fontsize=6)
        fig.savefig(reports/'spend_vs_recovery.png',dpi=140);plt.close(fig)
    notes=f'''# Analysis status
Completed paired jobs: {len(completed)}. Skipped impossible branch requests: {len(skipped)}.
Expected jobs: {manifest['job_count']}. Partial results are allowed; check completion before interpretation.

All runs share cutoff H={H}. Blank times/quantiles mean unobserved, not zero.
Survival S(t)=P(T>t); restricted mean E[min(T,H)]=sum_(t=0)^(H-1) S(t).
The survival CSV samples at most ~201 time points; calculations use every step.
Bootstrap intervals concern the restricted mean, not an unobserved full mean.
Wilson intervals are pointwise; DKW checks concern one entire CDF at a time.
Across many conditions, occasional DKW failures are expected; these are diagnostics,
not a familywise hypothesis test or proof of correctness. UCB is deterministic here.
First revisit tracks the intervention action even in the paired clean arm.
First recovery is not permanent recovery in arbitrary MDPs. In this deterministic
terminal task, Q-errors cannot increase under clean updates.
Controlled predictions require constant alpha and only one initially inaccurate value.
Warm-up runs do not receive idealized theory overlays. No UCB1 regret theorem is claimed.
The spend plot is descriptive and mixes counts/margins; use condition-level tables
and survival figures for comparisons. C is allowed budget; spent is actual expenditure.
No larger FAA navigation experiment is claimed by this runner. See PERSISTENCE.md.
'''
    (reports/'README.md').write_text(notes)
    print(f'Analyzed {len(completed)} paired jobs; saved {reports}',flush=True)
    return summaries
