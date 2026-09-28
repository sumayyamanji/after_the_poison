"""Questions 3/5: audit saved multi-state records without rerunning a sweep.

Standalone add-on: only numpy/matplotlib required. Optional selected replays use
an independent deterministic-chain implementation, not qpoison's learner/runner.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    p=Path(path);b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def flags(q,star,targets,tol,xi):
    states=np.flatnonzero(~targets.all(axis=1))
    target=all(q[s,targets[s]].max()-q[s,~targets[s]].max()>xi for s in states)
    policy=bool(np.all(star[np.arange(len(q)),q.argmax(axis=1)]>=star.max(axis=1)-1e-10))
    return {'q':bool(np.max(np.abs(q-star))<=tol),'policy':policy,'target_loss':not target}


def reconstruct(r,c):
    """Exact attack-window tables, first-event times and last-poison clock."""
    a=r['arms']['faa'];star=np.array(r['q_star']);q=np.array(r['initial']['q'],float)
    targets=np.array(r['targets'],bool);A=c['attack_steps'];H=c['post_steps']
    log=[dict(zip(r['attack_log_columns'],row)) for row in a['attack_log']]
    assert len(log)==A
    active=[x['step'] for x in log if x['delta']!=0]
    ell=max(active) if active else None
    assert ell==a['last_nonzero_poison_step']
    spent=0.;tables=[q.copy()];counts=np.array(r['initial']['counts'],int)
    repair=np.zeros_like(counts);first=np.full_like(counts,-1);visits=np.full(len(q),-1)
    first_events={k:None for k in ('q','policy','target_loss')};qell=None;target_at_last=None
    if ell is None:ell_for_scan=0
    else:ell_for_scan=ell
    for x in log:
        t=x['step'];s=x['state'];ac=x['action'];n=x['successor'];alpha=x['alpha']
        assert t==len(tables)
        future=0. if x['terminated'] else q[n].max()
        clean=(1-alpha)*q[s,ac]+alpha*(x['reward']+c['gamma']*future)
        np.testing.assert_allclose(clean,x['clean_candidate'],atol=1e-10,rtol=1e-10)
        np.testing.assert_allclose(clean+alpha*x['delta'],x['updated_value'],atol=1e-10,rtol=1e-10)
        assert abs(x['delta'])<=r['condition']['Delta']+1e-9
        spent+=abs(x['delta']);assert spent<=r['condition']['C']+1e-8
        q[s,ac]=x['updated_value'];counts[s,ac]+=1;tables.append(q.copy())
        if ell is not None and t>ell:
            repair[s,ac]+=1
            if first[s,ac]<0:first[s,ac]=t-ell
            if visits[s]<0:visits[s]=t-ell
    np.testing.assert_allclose(q,a['cutoff']['q'],atol=1e-10,rtol=1e-10)
    np.testing.assert_array_equal(counts,a['cutoff']['counts'])
    np.testing.assert_allclose(spent,a['spent'],atol=1e-8)
    if ell is not None:
        qell=tables[ell]
        for t in range(ell,A+1):
            f=flags(tables[t],star,targets,c['q_tolerance'],c['faa'].get('ranking_tolerance',1e-10))
            if t==ell:target_at_last=not f['target_loss']
            for key in f:
                if f[key] and first_events[key] is None:first_events[key]=t-ell
        for key,saved in [('q','q_recovery'),('policy','greedy_recovery'),('target_loss','target_loss')]:
            if first_events[key] is None and a['events'][saved] is not None:
                first_events[key]=A-ell+a['events'][saved]
        post_first=np.array(a['first_entry_update']);post_visits=np.array(a['first_state_visit'])
        mask=(first<0)&(post_first>=0);first[mask]=A-ell+post_first[mask]
        mask=(visits<0)&(post_visits>=0);visits[mask]=A-ell+post_visits[mask]
    return {'last':ell,'q_last':qell,'target_at_last':target_at_last,'events':first_events,
            'first':first,'state_first':visits,'updates_before_cutoff':repair,'tables':tables}


def mean_ci(values,rng,deterministic=False):
    x=np.asarray(values,float)
    if not len(x):return None,None,None
    if deterministic or len(x)<2:return float(x.mean()),None,None
    boot=rng.choice(x,(1000,len(x))).mean(axis=1)
    lo,hi=np.quantile(boot,[.025,.975]);return float(x.mean()),float(lo),float(hi)


def independent_replay(r,c):
    """Replay logged poison in a separate deterministic-chain learner.

    Verifies actions/transitions during attack, all snapshots, event endpoints,
    phase rewards/counts, and first visits. It does NOT independently optimize FAA.
    """
    spec=r['condition']['learner'];env=r['condition']['design']['environment']
    if env['kind']!='chain' or env.get('slip',0)!=0:
        raise ValueError('Independent replay currently supports deterministic chains only')
    A,H=c['attack_steps'],c['post_steps'];star=np.array(r['q_star']);n,k=star.shape
    assert k==2
    target=np.array(r['targets'],bool);log=[dict(zip(r['attack_log_columns'],x)) for x in r['arms']['faa']['attack_log']]
    results={}
    for arm in ['clean','faa']:
        q=np.array(r['initial']['q'],float);count=np.array(r['initial']['counts'],int);state=r['initial']['state']
        rng=np.random.default_rng(np.random.SeedSequence([r['seed'],201]))
        records=[];tables=[];count_history=[];totals={p:{'reward':0.,'goals':0,'updates':0} for p in ['attack','recovery']}
        events={x:None for x in ['q_recovery','greedy_recovery','target_loss','q_confirmation','greedy_confirmation']}
        streak={'q':0,'policy':0}
        for t in range(A+H+1):
            tables.append(q.copy());count_history.append(count.copy())
            if t>=A:
                fs=flags(q,star,target,c['q_tolerance'],c['faa'].get('ranking_tolerance',1e-10))
                for key,out in [('q','q_recovery'),('policy','greedy_recovery'),('target_loss','target_loss')]:
                    if fs[key] and events[out] is None:events[out]=t-A
                for key,out in [('q','q_confirmation'),('policy','greedy_confirmation')]:
                    streak[key]=streak[key]+1 if fs[key] else 0
                    if streak[key]>=c['confirmation'] and events[out] is None:events[out]=t-A
            if t==A+H:break
            vals=q[state];ns=count[state]
            if spec['rule']=='epsilon_greedy':
                prob=np.full(k,spec['epsilon']/k);prob[vals.argmax()]+=1-spec['epsilon']
            elif spec['rule']=='softmax':
                weights=np.exp((vals-vals.max())/spec['temperature']);prob=weights/weights.sum()
            else:
                unused=np.flatnonzero(ns==0)
                action=int(unused[0]) if len(unused) else int(np.argmax(vals+spec['beta']*np.sqrt(np.log1p(float(ns.sum()))/ns)))
                prob=np.eye(k)[action]
            action=int(rng.choice(k,p=prob));done=state==n-1 and action==1
            nxt=-1 if done else max(0,state-1) if action==0 else state+1
            reward=env.get('goal_reward',1.) if done else env.get('step_reward',-.1)
            delta=log[t]['delta'] if arm=='faa' and t<A else 0.
            if arm=='faa' and t<A:
                x=log[t]
                assert (state,action,nxt,done)==(x['state'],x['action'],x['successor'],x['terminated'])
                assert reward==x['reward']
            alpha=spec['alpha'] if spec.get('alpha_schedule','constant')=='constant' else (count[state,action]+1)**(-spec.get('omega',.75))
            old=q[state,action];future=0. if done else q[nxt].max()
            future_error=0. if done else c['gamma']*(future-star[nxt].max())
            clean=(1-alpha)*old+alpha*(reward+c['gamma']*future)
            q[state,action]=clean+alpha*delta;count[state,action]+=1
            phase='attack' if t<A else 'recovery'
            totals[phase]['reward']+=reward;totals[phase]['goals']+=int(done);totals[phase]['updates']+=1
            records.append({'arm':arm,'step':t+1,'state':state,'action':action,'reward':reward,'terminated':done,
                'delta':delta,'alpha':float(alpha),'q_before':old,'q_after':q[state,action],
                'entry_error_before':abs(old-star[state,action]),'entry_error_after':abs(q[state,action]-star[state,action]),
                'bootstrap_target_error':float(future_error),'sup_error_after':float(np.abs(q-star).max())})
            state=env.get('start',n-1) if done else nxt
        saved=r['arms'][arm]
        assert events==saved['events'],(arm,events,saved['events'])
        np.testing.assert_allclose(tables[A],saved['cutoff']['q'],atol=1e-10,rtol=1e-10)
        np.testing.assert_allclose(q,saved['final']['q'],atol=1e-10,rtol=1e-10)
        np.testing.assert_array_equal(count,saved['final']['counts'])
        for phase in totals:
            for key in totals[phase]:np.testing.assert_allclose(totals[phase][key],saved['totals'][phase][key],atol=1e-8,rtol=1e-10)
        results[arm]={'steps':records,'q':np.array(tables),'counts':np.array(count_history)}
    return results


def fmt(x):return '—' if x is None else f'{x:.4g}' if isinstance(x,(float,np.floating)) else str(x)


def analyze(source,out,replay=False,replay_budget=3.):
    source=Path(source);out=Path(out)
    if source.resolve()==out.resolve() or source.resolve() in out.resolve().parents:raise ValueError('Write audit reports outside raw results')
    if (out.exists() and any(out.iterdir())) or out.with_suffix('.zip').exists():raise ValueError('Choose a fresh audit report name')
    manifest=read(source/'manifest.json');c=manifest['config'];A,H=c['attack_steps'],c['post_steps']
    paths=sorted((source/'records').glob('*.json.gz'))
    if not paths:raise ValueError('No raw .json.gz records; use results folder, not report folder')
    out.mkdir(parents=True);(out/'plots').mkdir();shutil.copyfile(source/'manifest.json',out/'manifest.json')
    settings={'replay':replay,'replay_budget':replay_budget,'bootstrap_seed':7735,'bootstrap_replicates':1000,
      'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'clock':'Immediately after last nonzero reward perturbation; no-poison runs excluded from last-poison metrics',
      'common_last_poison_horizon':H,'numpy':np.__version__}
    (out/'audit_settings.json').write_text(json.dumps(settings,indent=2))
    rows=[];entry_rows=[];groups=collections.defaultdict(list);representatives={};seen=set()
    for i,path in enumerate(paths):
        r=read(path);assert r['id'] not in seen;seen.add(r['id'])
        d=reconstruct(r,c);a=r['arms']['faa'];clean=r['arms']['clean'];ell=d['last'];cond=r['condition']
        ident={'condition_id':r['condition_id'],'design':cond['design']['name'],'rule':cond['learner']['rule'],
               'C':cond['C'],'Delta':cond['Delta'],'eta':cond['eta'],'seed':r['seed']}
        row={**ident,'spent':a['spent'],'last_poison_step':ell,'available_clean_steps':None if ell is None else A+H-ell,
             'clean_steps_before_cutoff':None if ell is None else A-ell,
             'q_error_at_last_poison':None if ell is None else float(np.abs(d['q_last']-r['q_star']).max()),
             'q_error_at_cutoff':a['cutoff']['q_error'],'target_at_last_poison':d['target_at_last'],
             'target_at_cutoff':a['cutoff']['target_success'],'q_recovery_from_cutoff':a['events']['q_recovery']}
        for key,t in d['events'].items():
            row[key+'_time_from_last']=t
            row[key+'_censored_full_followup']=None if ell is None else t is None
            row[key+'_restricted_H']=None if ell is None else min(H,H if t is None else t)
            row[key+'_observed_by_H']=None if ell is None else t is not None and t<=H
        for phase,h in [('attack',A),('recovery',H)]:
            for arm,data in [('clean',clean),('faa',a)]:
                assert data['totals'][phase]['updates']==h
                row[phase+'_'+arm+'_reward']=data['totals'][phase]['reward']
                row[phase+'_'+arm+'_goals']=data['totals'][phase]['goals']
            row[phase+'_reward_loss']=clean['totals'][phase]['reward']-a['totals'][phase]['reward']
        row['combined_reward_loss']=row['attack_reward_loss']+row['recovery_reward_loss']
        rows.append(row);groups[r['condition_id']].append(row)
        star=np.array(r['q_star']);end=np.array(a['final']['q']);poisoned=np.array(a['poisoned_entries'])
        if ell is not None:
            for s in range(star.shape[0]):
                for ac in range(star.shape[1]):
                    fv=int(d['state_first'][s]);fu=int(d['first'][s,ac])
                    entry_rows.append({**ident,'state':s,'action':ac,'directly_poisoned':bool(poisoned[s,ac]),
                      'error_at_last':abs(d['q_last'][s,ac]-star[s,ac]),'error_at_cutoff':abs(a['cutoff']['q'][s][ac]-star[s,ac]),
                      'error_at_end':abs(end[s,ac]-star[s,ac]),'first_state_visit_from_last':None if fv<0 else fv,
                      'first_entry_update_from_last':None if fu<0 else fu,
                      'entry_first_update_censored':fu<0,'full_followup_horizon':A+H-ell,
                      'updates_between_last_and_cutoff':int(d['updates_before_cutoff'][s,ac]),
                      'updates_after_cutoff':a['visits']['recovery'][s][ac],
                      'updates_after_last':int(d['updates_before_cutoff'][s,ac])+a['visits']['recovery'][s][ac]})
        if replay and cond['C']==replay_budget:
            prior=representatives.get(r['condition_id'])
            if prior is None or r['seed']<prior['seed']:representatives[r['condition_id']]=r
        if i%100==0:print(f'Audited {i+1}/{len(paths)} records',flush=True)
    write_csv(out/'runs.csv',rows);write_csv(out/'entry_coverage.csv',entry_rows)
    rng=np.random.default_rng(7735);summary=[]
    for cid,rs in groups.items():
        ident={k:rs[0][k] for k in ['condition_id','design','rule','C','Delta','eta']}
        # A single observation never receives a sampling interval; UCB noise not assumed away.
        for metric in ['q_restricted_H','policy_restricted_H','target_loss_restricted_H',
                       'attack_reward_loss','recovery_reward_loss','combined_reward_loss','clean_steps_before_cutoff']:
            selected=[r for r in rs if r[metric] is not None and (metric!='target_loss_restricted_H' or r['target_at_last_poison'])]
            mean,lo,hi=mean_ci([r[metric] for r in selected],rng)
            summary.append({**ident,'metric':metric,'n':len(selected),'mean':mean,'ci_low':lo,'ci_high':hi,
                            'cohort':'target_at_last_poison' if metric=='target_loss_restricted_H' else 'nonzero_poison' if 'restricted' in metric or metric=='clean_steps_before_cutoff' else 'all'})
    write_csv(out/'summary.csv',summary)
    plot_links=[];verification=[]
    for cid,r in representatives.items():
        print(f'Independent replay: {cid}, seed {r["seed"]}',flush=True)
        rep=independent_replay(r,c);d=reconstruct(r,c);ell=d['last']
        if ell is None:continue
        ident={'condition_id':cid,'seed':r['seed']}
        write_csv(out/f'replay_{cid}.csv',[{**ident,**x} for arm in rep.values() for x in arm['steps']])
        q=rep['faa']['q'];counts=rep['faa']['counts'];star=np.array(r['q_star']);end=A+H
        # Check reconstructed last-poison first events against the independent full trajectory.
        fs=[flags(x,star,np.array(r['targets'],bool),c['q_tolerance'],c['faa'].get('ranking_tolerance',1e-10)) for x in q[ell:]]
        for key,t in d['events'].items():assert next((i for i,f in enumerate(fs) if f[key]),None)==t
        verification.append({**ident,'checked':'independent selection, updates, snapshots, rewards, endpoint times','status':'passed'})
        entry=np.unravel_index(np.argmax(np.abs(q[ell]-star)),star.shape);s,ac=entry
        t=np.arange(ell,end+1);errs=np.abs(q[t,s,ac]-star[s,ac]);updates=counts[t,s,ac]-counts[ell,s,ac]
        fig,axs=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
        axs[0,0].plot(t-ell,np.abs(q[t]-star).max(axis=(1,2)));axs[0,0].axvline(A-ell,color='grey',ls=':',label='original cutoff');axs[0,0].axhline(c['q_tolerance'],color='red',ls=':',label='tolerance')
        axs[0,0].set(title='Whole-table error since actual last poison',xlabel='Clean transitions',ylabel='Sup-norm error');axs[0,0].legend(fontsize=7)
        axs[0,1].plot(updates,errs);axs[0,1].scatter(updates[[0,-1]],errs[[0,-1]],s=15)
        axs[0,1].set(title=f'Largest-error entry at last poison: ({s}, {ac})',xlabel='Updates to this entry',ylabel='Absolute error')
        for state in range(len(star)):axs[1,0].plot(t-ell,(counts[t,state]-counts[ell,state]).sum(axis=1),label=f'state {state}')
        axs[1,0].set(title='State visits since actual last poison',xlabel='Clean transitions',ylabel='Visits');axs[1,0].legend(fontsize=7)
        clean_rewards=np.array([x['reward'] for x in rep['clean']['steps']]);attack_rewards=np.array([x['reward'] for x in rep['faa']['steps']])
        axs[1,1].plot(np.arange(1,end+1),np.cumsum(clean_rewards-attack_rewards));axs[1,1].axvline(ell,color='grey',ls=':',label='last poison');axs[1,1].axvline(A,color='red',ls=':',label='cutoff')
        axs[1,1].set(title='Cumulative true reward loss: clean minus FAA',xlabel='Transitions since attack-window start',ylabel='Reward difference');axs[1,1].legend(fontsize=7)
        for ax in axs.flat:ax.grid(alpha=.2)
        co=r['condition'];fig.suptitle(f"{co['design']['name']}; {co['learner']['rule']}; C={co['C']}; seed={r['seed']}\nIndependent representative replay; not an ensemble estimate",fontsize=10)
        filename=f'plots/replay_{cid}.png';fig.savefig(out/filename,dpi=140);plt.close(fig);plot_links.append(filename)
    write_csv(out/'replay_checks.csv',verification)
    lines=['# Questions 3 and 5: raw-record audit','',f"Completed records read: **{len(rows)}/{manifest['expected_jobs']}**. "+('Complete.' if len(rows)==manifest['expected_jobs'] else '**PARTIAL RESULTS.**'),'',
      '## Clock definitions','',
      f'Time zero for the new analysis is the table immediately after the final nonzero poisoned update. No-poison runs have no last-poison clock. Every included run has at least {H} clean transitions after this point; restricted means use this common horizon, avoiding unequal follow-up. Exact first events during the original attack window are reconstructed from logged updates; later events use the saved exact cutoff-relative event times.','',
      'Target-loss means include only runs target-successful immediately after the last poison. This differs from conditioning on success at the original cutoff. Last-poison time and the conditioning event are outcome-dependent; these are descriptive comparisons, not randomized interventions at fixed post-attack states. This report measures first recovery, not permanent recovery or a new confirmation-window endpoint.','',
      '## Question 3: correction delays','',
      '| Design | Rule | C | Nonzero-poison n | Mean last poison | Q RMST from last poison | Q events not seen by common horizon |',
      '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for cid,rs in sorted(groups.items()):
        chosen=[r for r in rs if r['last_poison_step'] is not None];r=rs[0]
        lines.append(f"| {r['design']} | {r['rule']} | {r['C']} | {len(chosen)} | {fmt(float(np.mean([x['last_poison_step'] for x in chosen])) if chosen else None)} | {fmt(float(np.mean([x['q_restricted_H'] for x in chosen])) if chosen else None)} | {sum(not x['q_observed_by_H'] for x in chosen)} |")
    lines+=['','Entry-level first state visits, first corrective-action opportunities, update counts and error magnitudes are in [entry_coverage.csv](entry_coverage.csv). They cover all time after the last poison through the original endpoint; this follow-up length differs between runs and is explicitly recorded. An action update is an opportunity to repair, not a guarantee of improvement.','',
      '## Question 5: environmental reward damage','',
      '| Design | Rule | C | Attack loss | Recovery-window loss | Combined loss |',
      '| --- | --- | ---: | ---: | ---: | ---: |']
    for cid,rs in sorted(groups.items()):
        r=rs[0];means=[float(np.mean([x[k] for x in rs])) for k in ['attack_reward_loss','recovery_reward_loss','combined_reward_loss']]
        lines.append(f"| {r['design']} | {r['rule']} | {r['C']} | "+' | '.join(fmt(x) for x in means)+' |')
    lines+=['','Loss is paired clean minus FAA, using environmental rewards. Negative values are retained. Combined uncertainty is bootstrapped from each run’s combined loss, not obtained by adding interval endpoints. Compare each start condition against its own clean arm. These phase windows remain the original fixed windows; they are not silently moved to the last-poison time.','',
      '## Files and limits','',
      '- [runs.csv](runs.csv): exact last-poison first-event times, horizon flags, errors, phase and combined rewards.',
      '- [summary.csv](summary.csv): marginal 95% percentile bootstrap intervals (1,000 draws); no interval for one observation. Not adjusted for multiple comparisons.',
      '- [entry_coverage.csv](entry_coverage.csv): state/action access and repair opportunities, including zero-update entries.',
      '- [manifest.json](manifest.json) and [audit_settings.json](audit_settings.json): original simulation settings and audit provenance.',
      '- Replays, when requested, independently recompute deterministic-chain selection and Q updates using the recorded poison. They do not independently verify FAA’s navigation optimization or prove general causal claims.',
      '- Full per-update replay CSVs contain bootstrap-target error and before/after entry error; a clean update can inherit an inaccurate successor estimate.',
      '- Only selected replays provide full post-cutoff error-versus-update trajectories. No sampled trace is treated as an exact event time.','',
      f'Independent representative pairs checked: {len(verification)}. Selection: lowest available seed per condition at allocated C={replay_budget}.','']
    for link in plot_links:lines.extend([f'![Representative replay]({link})',''])
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob('*'):
            if p.is_file():z.write(p,Path(out.name)/p.relative_to(out))
    print(f'Upload: {out.with_suffix(".zip").resolve()}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,help='Raw results folder containing manifest.json and records/')
    p.add_argument('--out',required=True,help='Fresh report folder outside raw results')
    p.add_argument('--replay',action='store_true',help='Independently replay lowest seed per condition at chosen budget')
    p.add_argument('--replay-budget',type=float,default=3.)
    args=p.parse_args();analyze(args.input,args.out,args.replay,args.replay_budget)
