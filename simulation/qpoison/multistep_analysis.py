"""Censoring-aware summaries and linked reports for paired multi-state runs."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .multistep import read_json, jobs, EVENTS

COLORS = {'epsilon_greedy':'tab:blue','softmax':'tab:orange','ucb':'tab:green'}


def wilson(successes, n):
    if not n: return None, None
    z=1.959963984540054; p=successes/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0.,center-half),min(1.,center+half)


def interval(values, rng, bootstrap=1000, deterministic=False):
    values=np.asarray(values,float)
    if not len(values): return None,None,None
    mean=float(values.mean())
    if deterministic or len(values)<2: return mean,None,None
    draws=rng.choice(values,size=(bootstrap,len(values)),replace=True).mean(axis=1)
    lo,hi=np.quantile(draws,[.025,.975])
    return mean,float(lo),float(hi)


def event_summary(times,H,rng,deterministic=False):
    n=len(times); seen=sorted(t for t in times if t is not None)
    restricted=[H if t is None else min(t,H) for t in times]
    mean,lo,hi=interval(restricted,rng,deterministic=deterministic)
    result={'n':n,'horizon':H,'recovered':len(seen),'censored':n-len(seen),
            'survival_at_horizon':(n-len(seen))/n if n else None,
            'restricted_mean':mean,'restricted_mean_ci_low':lo,'restricted_mean_ci_high':hi,
            'observed_mean_if_no_censoring':float(np.mean(seen)) if n and len(seen)==n else None}
    for label,p in [('q25',.25),('median',.5),('q75',.75)]:
        index=int(np.ceil(p*n))-1
        result[label]=seen[index] if n and index<len(seen) else None
    return result


def write_csv(path,rows):
    if not rows: return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def slug(text):
    return re.sub(r'[^a-zA-Z0-9_-]+','-',str(text)).strip('-')


def fmt(x):
    return '—' if x is None else f'{x:.4g}' if isinstance(x,(float,np.floating)) else str(x)


def identity(record):
    c=record['condition']
    return {'condition_id':record['condition_id'],'design':c['design']['name'],
            'rule':c['learner']['rule'],'C':c['C'],'Delta':c['Delta'],'eta':c['eta'],'sign':c['sign']}


def compare_key(c):
    return (c['design']['name'],c['C'],c['Delta'],c['eta'],c['sign'])


def analysis_settings(zoom):
    return {'zoom':zoom,'bootstrap_replicates':1000,'bootstrap_seed':773,
            'interval_level':0.95,'proportion_interval':'Wilson, marginal',
            'mean_interval':'paired-run or single-arm percentile bootstrap, marginal',
            'deterministic_intervals':None,'trace_selection':'smallest saved seed, budget nearest 3',
            'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'numpy_version':np.__version__,'matplotlib_version':matplotlib.__version__}


def analyze(source,out,zoom=200):
    source=Path(source);out=Path(out)
    if zoom<1: raise ValueError('zoom must be positive')
    if out.resolve()==source.resolve() or source.resolve() in out.resolve().parents:
        raise ValueError('Write reports outside the raw results folder')
    if out.exists() and any(out.iterdir()): raise ValueError('Use a new empty report folder to prevent stale figures')
    if out.with_suffix('.zip').exists(): raise ValueError('Report archive exists; use a fresh report name')
    manifest=read_json(source/'manifest.json'); config=manifest['config'];H=config['post_steps'];A=config['attack_steps']
    expected={j['id']:j for j in jobs(config)}
    records=[];groups={};trace_records=[]
    for path in sorted((source/'records').glob('*.json.gz')):
        r=read_json(path)
        if r['id'] not in expected or r['condition']!=expected[r['id']]['condition']:
            raise ValueError(f'Record mismatch: {path.name}')
        if r['arms']['faa']['trace']: trace_records.append(r)
        # Only selected trace references retain these arrays; bulk records need summaries.
        slim={**r,'arms':{arm:{k:v for k,v in data.items() if k not in ('attack_log','trace')} for arm,data in r['arms'].items()}}
        records.append(slim);groups.setdefault(r['condition_id'],[]).append(slim)
    if not records: raise ValueError('No completed records available')
    if len({r['id'] for r in records})!=len(records): raise ValueError('Duplicate record IDs')
    out.mkdir(parents=True,exist_ok=True);(out/'plots').mkdir(exist_ok=True)
    shutil.copyfile(source/'manifest.json',out/'manifest.json')
    (out/'analysis_settings.json').write_text(json.dumps(analysis_settings(zoom),indent=2)+'\n')
    rng=np.random.default_rng(773)
    summary=[];conditions=[];pairs=[];entries=[];run_rows=[];survival=[]
    for cid,rs in sorted(groups.items()):
        ident=identity(rs[0]);c=rs[0]['condition'];n=len(rs)
        deterministic=c['learner']['rule']=='ucb' and c['design']['environment'].get('slip',0)==0
        condition={**ident,'n':n,'deterministic':deterministic,'initialization':json.dumps(c['design']['initialization']),
                   'settings':json.dumps(c,sort_keys=True),'pre_q_error_mean':float(np.mean([r['initial']['q_error'] for r in rs]))}
        for label,values in {
            'attained_by_cutoff':[r['arms']['faa']['attained_by_cutoff'] for r in rs],
            'target_at_cutoff':[r['arms']['faa']['cutoff']['target_success'] for r in rs],
            'clip_delta_any':[r['arms']['faa']['clip_delta_count']>0 for r in rs],
            'clip_budget_any':[r['arms']['faa']['clip_budget_count']>0 for r in rs]}.items():
            condition[label+'_rate']=float(np.mean(values))
            low,high=(None,None) if deterministic else wilson(sum(values),n)
            condition[label+'_ci_low']=low;condition[label+'_ci_high']=high
        for label,values in {
            'spent':[r['arms']['faa']['spent'] for r in rs],
            'navigation_spend':[r['arms']['faa']['spending_by_purpose']['navigation'] for r in rs],
            'teaching_spend':[r['arms']['faa']['spending_by_purpose']['teaching'] for r in rs],
            'maintenance_spend':[r['arms']['faa']['spending_by_purpose']['maintenance'] for r in rs],
            'target_occupancy':[r['arms']['faa']['target_occupancy'] for r in rs],
            'attainment_spend_successes_only':[r['arms']['faa']['attainment_spend'] for r in rs if r['arms']['faa']['attained_by_cutoff']]}.items():
            condition[label+'_mean']=float(np.mean(values)) if len(values) else None
        conditions.append(condition)
        for arm in ('clean','faa'):
            for metric in (*EVENTS,'attainment'):
                horizon=A if metric=='attainment' else H
                cohorts=[('all',rs)]
                if metric=='target_loss':cohorts.append(('target_at_cutoff',[r for r in rs if r['arms'][arm]['cutoff']['target_success']]))
                for cohort,chosen in cohorts:
                    times=[r['arms'][arm]['attainment_time'] if metric=='attainment' else r['arms'][arm]['events'][metric] for r in chosen]
                    row={**ident,'arm':arm,'metric':metric,'cohort':cohort,
                         **event_summary(times,horizon,rng,deterministic)}
                    summary.append(row)
                    # Full-resolution first-event curve, including u=0. No invented times for censoring.
                    if times:
                        changes=np.zeros(horizon+1,dtype=int)
                        for t in times:
                            if t is not None: changes[t]+=1
                        not_seen=len(times)-np.cumsum(changes)
                        # Export at changes and endpoints; these represent the exact staircase.
                        for u in np.unique(np.r_[0,np.flatnonzero(changes),horizon]):
                            low,high=(None,None) if deterministic else wilson(int(not_seen[u]),len(times))
                            survival.append({**ident,'arm':arm,'metric':metric,'cohort':cohort,'time':int(u),
                                             'n':len(times),'survival':float(not_seen[u]/len(times)),
                                             'pointwise_ci_low':low,'pointwise_ci_high':high})
        paired_values={}
        for metric in EVENTS:
            if metric=='target_loss': continue # Different success-conditioned subsets are not paired effects.
            paired_values[metric+'_restricted_faa_minus_clean']=[
                (H if r['arms']['faa']['events'][metric] is None else r['arms']['faa']['events'][metric])-
                (H if r['arms']['clean']['events'][metric] is None else r['arms']['clean']['events'][metric]) for r in rs]
        for phase in ('attack','recovery'):
            for measure in ('reward','goals'):
                paired_values[phase+'_'+measure+'_clean_minus_faa']=[r['arms']['clean']['totals'][phase][measure]-r['arms']['faa']['totals'][phase][measure] for r in rs]
        for measure,values in paired_values.items():
            mean,low,high=interval(values,rng,deterministic=deterministic)
            pairs.append({**ident,'metric':measure,'n':n,'mean':mean,'ci_low':low,'ci_high':high})
        for r in rs:
            poisoned=np.asarray(r['arms']['faa']['poisoned_entries'])
            for arm,data in r['arms'].items():
                row={**ident,'seed':r['seed'],'arm':arm,'initial_q_error':r['initial']['q_error'],
                     'cutoff_q_error':data['cutoff']['q_error'],'final_q_error':data['final']['q_error'],
                     'target_at_cutoff':data['cutoff']['target_success'],'attainment_time':data['attainment_time'],
                     'attainment_spend':data['attainment_spend'],'spent':data['spent'],
                     'clip_delta_count':data['clip_delta_count'],'clip_budget_count':data['clip_budget_count'],
                     'target_occupancy':data['target_occupancy'],'sweeps':len(data['sweeps']),
                     'last_nonzero_poison_step':data['last_nonzero_poison_step'],
                     **data['events'],**{'recurrence_'+k:v for k,v in data['recurrence'].items()}}
                for phase in ('attack','recovery'):
                    row.update({phase+'_'+k:v for k,v in data['totals'][phase].items()})
                run_rows.append(row)
                for s,qs in enumerate(r['q_star']):
                    for action in range(len(qs)):
                        ft=data['first_entry_update'][s][action];fv=data['first_state_visit'][s]
                        entries.append({**ident,'seed':r['seed'],'arm':arm,'state':s,'action':action,
                                        'target_state':s in r['target_states'],'clean_optimal':qs[action]>=max(qs)-1e-10,
                                        'altered_in_faa_arm':bool(poisoned[s,action]),
                                        'first_state_visit':None if fv<0 else fv,'first_entry_update':None if ft<0 else ft,
                                        'first_entry_update_censored':ft<0,'horizon':H,
                                        'initial_q':r['initial']['q'][s][action],'initial_count':r['initial']['counts'][s][action],
                                        'cutoff_q':data['cutoff']['q'][s][action],'cutoff_count':data['cutoff']['counts'][s][action],
                                        'final_q':data['final']['q'][s][action],
                                        'attack_updates':data['visits']['attack'][s][action],
                                        'recovery_updates':data['visits']['recovery'][s][action]})
    for name,rows in [('summary',summary),('conditions',conditions),('paired_differences',pairs),('runs',run_rows),('coverage',entries),('survival',survival)]:
        write_csv(out/(name+'.csv'),rows)
    lookup={(r['condition_id'],r['arm'],r['metric'],r['cohort']):r for r in summary}
    figure_sections=[]
    comparisons={}
    for r in records:comparisons.setdefault(compare_key(r['condition']),[]).append(r)
    for key,rs in sorted(comparisons.items()):
        design,C,Delta,eta,sign=key
        name=slug(f'{design}_C{C}_Delta{Delta}_eta{eta}_{sign}')
        for view,stop in [('full',H),('zoom',min(zoom,H))]:
            fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
            panels=[('greedy_recovery','all'),('q_recovery','all'),('target_loss','target_at_cutoff'),('q_confirmation','all')]
            for ax,(metric,cohort) in zip(axes.flat,panels):
                for rule in COLORS:
                    for arm in ('faa','clean'):
                        if metric=='target_loss' and arm=='clean':continue
                        chosen=[r for r in rs if r['condition']['learner']['rule']==rule and (cohort=='all' or r['arms'][arm]['cutoff']['target_success'])]
                        if not chosen:continue
                        times=[r['arms'][arm]['events'][metric] for r in chosen]
                        changes=np.zeros(H+1,int)
                        for t in times:
                            if t is not None:changes[t]+=1
                        ax.step(np.arange(H+1),1-np.cumsum(changes)/len(times),where='post',color=COLORS[rule],
                                linestyle='-' if arm=='faa' else ':',label=f'{rule} {arm}, n={len(times)}')
                ax.set(xlim=(0,stop),ylim=(-.02,1.02),xlabel='Clean transitions after cessation',ylabel='Fraction without first event',
                       title=metric+(' | successful at cessation' if cohort!='all' else ' | all runs'))
                ax.grid(alpha=.2)
                if ax.lines:ax.legend(fontsize=6)
                else:ax.text(.5,.5,'No eligible runs',transform=ax.transAxes,ha='center')
            fig.suptitle(f'{design}; C={C}; Delta={Delta}; eta={eta}; {sign}\nH={H}; fixed learner settings in manifest; {view} view',fontsize=10)
            filename=f'plots/survival_{name}_{view}.png';fig.savefig(out/filename,dpi=140);plt.close(fig)
            figure_sections.append((f'{design}: C={C}, {view}',filename,
              'All-run policy/value recovery; target-loss curves include only FAA runs successful at cessation. Curves show first events, not current correctness. No uncertainty bands are drawn; pointwise intervals are in survival.csv.'))
    # Budget sweeps: keep design, cap, margin and sign fixed.
    sweep_keys=sorted({(r['design'],r['Delta'],r['eta'],r['sign']) for r in conditions})
    for key in sweep_keys:
        design,delta,eta,sign=key
        fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
        for rule,color in COLORS.items():
            selected=sorted([r for r in conditions if (r['design'],r['Delta'],r['eta'],r['sign'])==key and r['rule']==rule],key=lambda r:r['C'])
            if not selected:continue
            xs=[r['C'] for r in selected]
            for ax,field in zip(axes.flat[:2],('attained_by_cutoff_rate','target_at_cutoff_rate')):
                ys=[r[field] for r in selected];base=field[:-5]
                ax.plot(xs,ys,'o-',color=color,label=rule)
                valid=[i for i,r in enumerate(selected) if r.get(base+'_ci_low') is not None]
                if valid:
                    ax.errorbar(np.array(xs)[valid],np.array(ys)[valid],yerr=[
                        [max(0,ys[i]-selected[i][base+'_ci_low']) for i in valid],
                        [max(0,selected[i][base+'_ci_high']-ys[i]) for i in valid]],fmt='none',color=color,capsize=3)
            ys=[lookup[(r['condition_id'],'faa','q_recovery','all')]['restricted_mean'] for r in selected]
            axes[1,0].plot(xs,ys,'o-',color=color,label=rule)
            for x,r,y in zip(xs,selected,ys):
                sm=lookup[(r['condition_id'],'faa','q_recovery','all')]
                if sm['censored']:axes[1,0].plot(x,y,'^',color=color,markersize=10)
                if sm['restricted_mean_ci_low'] is not None:
                    axes[1,0].errorbar(x,y,yerr=[[max(0,y-sm['restricted_mean_ci_low'])],[max(0,sm['restricted_mean_ci_high']-y)]],color=color,capsize=3)
            ps=[next(p for p in pairs if p['condition_id']==r['condition_id'] and p['metric']=='recovery_reward_clean_minus_faa') for r in selected]
            axes[1,1].plot(xs,[p['mean'] for p in ps],'o-',color=color,label=rule)
            for x,p in zip(xs,ps):
                if p['ci_low'] is not None:axes[1,1].errorbar(x,p['mean'],yerr=[[max(0,p['mean']-p['ci_low'])],[max(0,p['ci_high']-p['mean'])]],color=color,capsize=3)
        for ax,title in zip(axes.flat,['Attained at least once by cutoff','Target still attained at cutoff',f'FAA Q-recovery RMST; H={H}; triangles = censoring','Recovery reward loss: clean minus FAA']):
            ax.set(title=title,xlabel='Allocated absolute budget C');ax.grid(alpha=.2);ax.legend(fontsize=7)
        for ax in axes[0]:ax.set_ylim(-.05,1.05)
        fig.suptitle(f'{design}; Delta={delta}; eta={eta}; {sign}\n95% marginal intervals where stochastic replication is available',fontsize=10)
        filename=f'plots/budgets_{slug(str(key))}.png';fig.savefig(out/filename,dpi=140);plt.close(fig)
        figure_sections.append((f'Budget comparison: {design}',filename,'Allocated budget is the controlled setting. Actual spend is reported separately. Positive reward loss means the attacked arm earned less. UCB deterministic points have no sampling interval.'))
    # Representative traces are selected before observing results: smallest saved seed, budget nearest 3.
    representatives={}
    for r in trace_records:
        c=r['condition'];key=(c['design']['name'],c['learner']['rule'],c['Delta'],c['eta'],c['sign'])
        priority=(abs(c['C']-3),c['C'],r['seed'])
        if key not in representatives or priority<representatives[key][0]:representatives[key]=(priority,r)
    for key,(_,r) in sorted(representatives.items()):
        c=r['condition'];data=r['arms']['faa'];tr=[x for x in data['trace'] if x['t']>=A]
        if not tr:continue
        ts=np.array([x['t']-A for x in tr]);qs=np.array([x['q'] for x in tr]);counts=np.array([x['counts'] for x in tr]);star=np.array(r['q_star'])
        errs=np.abs(qs-star);fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
        for arm,style in [('faa','-'),('clean',':')]:
            series=[x for x in r['arms'][arm]['trace'] if x['t']>=A]
            axes[0,0].plot([x['t']-A for x in series],[x['q_error'] for x in series],style,label=arm)
        for s in range(len(star)):
            axes[0,1].plot(ts,errs[:,s,:].max(axis=1),label=f'state {s}')
            action=int(star[s].argmax())
            local_updates=counts[:,s,action]-data['cutoff']['counts'][s][action]
            axes[1,0].plot(local_updates,errs[:,s,action],label=f'state {s}, optimal action')
            axes[1,0].scatter(local_updates[[0,-1]],errs[[0,-1],s,action],s=18)
            axes[1,1].plot(ts,(counts[:,s,:]-np.array(data['cutoff']['counts'])[s]).sum(axis=1),label=f'state {s}')
        labels=[('Sup-norm Q error','Clean transitions','Error'),('FAA local errors','Clean transitions','Max local error'),
                ('FAA optimal-entry error vs its updates','Updates of plotted entry','Absolute error'),('FAA state visits','Clean transitions','Cumulative visits')]
        for ax,(title,xlab,ylab) in zip(axes.flat,labels):ax.set(title=title,xlabel=xlab,ylabel=ylab);ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.suptitle(f"{c['design']['name']}; {c['learner']['rule']}; C={c['C']}; Delta={c['Delta']}; eta={c['eta']}; {c['sign']}; seed={r['seed']}\nRepresentative trace, sampled every {config['trace_every']} transitions; not an ensemble estimate",fontsize=9)
        filename=f"plots/mechanism_{slug(str(key))}_C{c['C']}_seed{r['seed']}.png";fig.savefig(out/filename,dpi=140);plt.close(fig)
        figure_sections.append((f"Mechanism trace: {c['design']['name']}, {c['learner']['rule']}",filename,'A prespecified representative run, not evidence of a typical trajectory. Error versus entry updates also reflects intervening downstream changes. Complete sweep endpoints remain in raw records.'))
    lines=['# Multi-state FAA experiment report','',f'Completed paired jobs: **{len(records)}/{len(expected)}**. '+('Complete.' if len(records)==len(expected) else '**PARTIAL RESULTS: do not treat this as the completed experiment.**'),'',
           '## What was run','',f'Warmup or controlled initialization → {A} attack transitions → {H} clean transitions. Each pair runs to the full horizon. FAA uses the documented demotion convention and both caps. This is a reconstruction/transfer study, not a literal reproduction of the source paper.','',
           f"Common learner settings: `{json.dumps(config['learner_defaults'],sort_keys=True)}`. Gamma={config['gamma']}; accuracy tolerance={config['q_tolerance']}; confirmation={config['confirmation']} observations. Ties select the lowest action index. UCB uses local state counts. Fixed navigation settings: `{json.dumps(config['faa'],sort_keys=True)}`.",'',
           'Complete environments, initializations, targets, signs, seeds and simulation code hashes: [manifest.json](manifest.json). Analysis parameters and source hash: [analysis_settings.json](analysis_settings.json).','',
           '## Primary results','',
           'Q recovery uses all runs. Target-loss persistence is conditional on success at cessation; its sample size can differ between learners. RMST is E[min(T,H)], not an estimate of an uncensored mean when censoring occurs.','',
           '| Design | Rule | C / Delta / eta / sign | n | Ever attained | At cutoff | Actual spend | Q RMST | Q censored | Conditional target-loss n / RMST | Recovery reward loss |',
           '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |']
    for r in sorted(conditions,key=lambda x:(x['design'],x['sign'],x['eta'],x['Delta'],x['C'],x['rule'])):
        cid=r['condition_id'];q=lookup[(cid,'faa','q_recovery','all')];loss=lookup[(cid,'faa','target_loss','target_at_cutoff')]
        reward=next(p for p in pairs if p['condition_id']==cid and p['metric']=='recovery_reward_clean_minus_faa')
        lines.append(f"| {r['design']} | {r['rule']} | {r['C']} / {r['Delta']} / {r['eta']} / {r['sign']} | {r['n']} | {fmt(r['attained_by_cutoff_rate'])} | {fmt(r['target_at_cutoff_rate'])} | {fmt(r['spent_mean'])} | {fmt(q['restricted_mean'])} | {q['censored']} | {loss['n']} / {fmt(loss['restricted_mean'])} | {fmt(reward['mean'])} |")
    lines+=['','## Clean-baseline diagnostic','',
            'Whole-table accuracy may remain poor even without poisoning. Read the clean baseline alongside the FAA result; a censored Q-recovery time alone does not identify attack-induced delay. Repeated clean results across budgets use the same seeds and are not independent replications.','',
            '| Design | Rule | C | n | Clean Q RMST | Clean Q censored | Initial Q-error mean |',
            '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in conditions:
        clean=lookup[(r['condition_id'],'clean','q_recovery','all')]
        lines.append(f"| {r['design']} | {r['rule']} | {r['C']} | {r['n']} | {fmt(clean['restricted_mean'])} | {clean['censored']} | {fmt(r['pre_q_error_mean'])} |")
    lines+=['','## Measurement files','',
            '- [summary.csv](summary.csv): attainment and all recovery endpoints, both arms, cohort sizes, censoring, quartiles, restricted means and bootstrap intervals.',
            '- [conditions.csv](conditions.csv): attainment proportions and Wilson intervals; clipping rates; actual spend and its purpose; initial Q error.',
            '- [paired_differences.csv](paired_differences.csv): paired reward/goal loss and recovery-delay differences with bootstrap intervals.',
            '- [runs.csv](runs.csv): per-run endpoints, recurrence, occupancy, error, sweeps, and full-horizon reward/goal totals.',
            '- [coverage.csv](coverage.csv): state/action first visits, inherited counts, entry errors, and update totals. Altered-entry flags refer to the FAA arm for both paired arms.',
            '- [survival.csv](survival.csv): exact empirical staircase at event times; marginal Wilson intervals. Hold each value constant until the next event time.',
            '- Raw compressed records in the input folder retain Q/count snapshots, complete sweep endpoints, and every FAA request/applied perturbation. Keep them for reproducibility.','',
            '## Interpretation limits','',
            'These outputs separate attainment from persistence and task damage. Failure to attain is not robust recovery from a successful attack. Longer waiting or Q-error delay is not automatically larger reward loss. Real warmup changes values and count imbalance; controlled initialization isolates designated factors. No universal ranking or general multi-state UCB convergence theorem follows from these plots.','',
            'Intervals are marginal 95% intervals, not simultaneous guarantees. Identical deterministic UCB runs are collapsed to one; no sampling intervals are shown for those conditions. Shared seeds across budgets/designs induce dependence. Conditional target-loss samples can be small and selectively different. Blank values mean unavailable, not zero.','',
            '## Figures','']
    for title,filename,caption in figure_sections:lines.extend([f'### {title}','',f'![{title}]({filename})','',caption,''])
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for _,filename,_ in figure_sections:
        assert (out/filename).exists()
    archive=out.with_suffix('.zip')
    if archive.exists():raise ValueError('Report archive already exists; choose a fresh report name')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in out.rglob('*'):
            if path.is_file():z.write(path,Path(out.name)/path.relative_to(out))
    print(f'Report: {(out/"REPORT.md").resolve()}\nUpload together: {archive.resolve()}\nCompleted pairs: {len(records)}/{len(expected)}',flush=True)
