"""Build a portable Markdown report and named PNGs from existing analysis outputs.
No simulations are run. Python 3.10+, numpy and matplotlib (existing requirements).
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

METRICS=['first_revisit','greedy_recovery','q_recovery','q_confirmation']
LABELS={'epsilon_greedy':'epsilon-greedy','softmax':'softmax','ucb':'UCB-style'}
COLORS={'epsilon_greedy':'C0','softmax':'C1','ucb':'C2'}

def read_csv(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def number(v):
    return float(v) if v not in ('',None) else None

def fmt(v):
    n=number(v)
    return 'not observed / unavailable' if n is None else f'{n:,.2f}'.rstrip('0').rstrip('.')

def token(s):return re.sub(r'[^a-zA-Z0-9_-]+','_',str(s)).strip('_')

def group(r):
    return (r['design'],r['mode'],r['eta'],r['C'],r['Delta'],r['branch_request'],r['branch'])

def initialization(r):
    return json.loads(r['initialization'])

def md_table(head,rows):
    return '\n'.join(['| '+' | '.join(head)+' |','| '+' | '.join(['---']*len(head))+' |']+
                     ['| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows])+'\n'

def build(source,out,focus=1000,zoom=200):
    source=Path(source).resolve();out=Path(out).resolve()
    if out==source or source in out.parents:raise ValueError('Choose an output folder outside the analysis folder')
    if out.exists() and any(out.iterdir()):raise ValueError('Choose a new empty output directory to avoid stale report images')
    summary=read_csv(source/'summary.csv')
    if not summary:raise ValueError('Empty summary')
    out.mkdir(parents=True,exist_ok=True);(out/'plots').mkdir();(out/'data').mkdir()
    shutil.copy2(source/'summary.csv',out/'data/summary.csv')
    if (source/'README.md').exists():shutil.copy2(source/'README.md',out/'data/analysis_status.md')
    manifest_path=source.parent/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if manifest: (out/'data/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    Hs=set(int(r['horizon']) for r in summary)
    if len(Hs)!=1:raise ValueError('Mixed observation horizons')
    H=Hs.pop();faa=[r for r in summary if r['arm']=='faa' and r['metric']=='q_recovery']
    completed=sum(int(r['n']) for r in faa)
    expected=manifest['job_count'] if manifest else None
    if expected is None and (source/'README.md').exists():
        match=re.search(r'Expected jobs:\s*(\d+)',(source/'README.md').read_text())
        if match:expected=int(match[1])
    header=['# Reward-poisoning experiment report',
        f'Generated UTC: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
        '## What we ran',
        'One deterministic decision state with two terminal actions. A clean online warm-up (or explicitly controlled initialization) is followed by one corrected FAA reward intervention, then clean learning. Demotion and promotion are reported separately, with paired clean controls. This is not a multi-state FAA navigation experiment.',
        f'Completed pairs represented: **{completed:,}**. Expected jobs: **{expected if expected is not None else "not supplied"}**. Observation horizon: **{H:,} clean steps**. Check completion within each condition before comparing partial runs.',
        'Each survival time is a first-event time. Q recovery and the additional confirmation window are distinct. Censored observations remain in restricted means; they are never assigned an actual recovery time at the cutoff.',
        '## Settings and provenance']
    if manifest:
        header += ['The exact supplied manifest is [saved here](data/manifest.json).',
                   '```json\n'+json.dumps(manifest['config'],indent=2)+'\n```']
    else:
        header += ['No experiment manifest was provided. The summary identifies margins, caps, initialization and horizon, but does not fully identify learning/exploration parameters. Preserve the original manifest when writing up; this report does not infer missing settings.']
    header += ['Source: [complete summary](data/summary.csv). All figures below are rebuilt from the supplied data, not copied from older PNGs.',
               '## How to read the results',
               '- First revisit: first clean selection of the intervention action.\n- Greedy recovery: first restoration of the genuinely optimal greedy action, using the code tie rule.\n- Q recovery: first Q-error within the configured tolerance.\n- Q confirmation: the configured consecutive-observation window is completed.\n- Restricted mean: mean min(event time, horizon). It is not a full recovery-time estimate when censoring occurs.\n- Target attainment: the post-intervention target ordering was achieved; accurate-value damage can exist even when attainment fails.\n- Promotion or demotion labels in clean controls refer to the paired intervention action; no poisoning is applied to those controls.',
               '## Findings and limitations to retain',
               'Use the matched-condition tables below to state findings. A large recovery time does not by itself establish reward loss, and a one-state comparison does not establish a universal ranking. Actual warm-up changes both values and counts. Identical results across settings can reflect identical Q-values and shared random streams. UCB runs are deterministic in this task; duplicate seeds would not add evidence. Rare natural promotion branches may have too few observations for a reliable comparison.']
    # Human-readable focal comparison without silently pooling branches or conditions.
    focal=[r for r in faa if r['mode']=='warmup' and initialization(r).get('steps')==focus
           and r['branch']=='demotion']
    if focal:
        header += [f'## Focal results: demotion after {focus} warm-up steps',
                   'These are Q-accuracy recovery times, without the extra confirmation window. Budget is an allowance; the spend column is what was actually used. Read success rate alongside recovery, since failure to attain a target is not immediate repair of a successful attack.',
                   md_table(['Rule','Margin','C / Delta','n','Attainment','Mean spend','Restricted Q-recovery mean','Censored'],
                   [[LABELS[r['rule']],r['eta'],r['C']+' / '+r['Delta'],r['n'],
                     f"{100*float(r['attainment_rate']):.1f}%",fmt(r['spent_mean']),fmt(r['restricted_mean']),r['censored']]
                    for r in sorted(focal,key=lambda x:(float(x['C']),float(x['eta']),x['rule']))])]
        for r in focal:
            if int(r['censored']):
                header += [f"**Unfinished recovery:** {LABELS[r['rule']]}, margin {r['eta']}, C={r['C']}: "
                           f"{r['censored']} of {r['n']} runs had not reached Q-accuracy by {H} steps. The capped value is not their actual recovery time."]
    groups=defaultdict(list)
    for r in faa:groups[group(r)].append(r)
    # Exact empirical survival from raw event times, only if counts match this summary.
    raw=None;raw_groups=defaultdict(list);raw_warning='No runs.csv supplied: no survival curves are reconstructed from summary means.'
    if (source/'runs.csv').exists():
        raw=read_csv(source/'runs.csv')
        for r in raw:raw_groups[(r['condition_id'],r['branch'],r['arm'])].append(r)
        wanted={(r['condition_id'],r['branch'],r['arm']):int(r['n']) for r in summary}
        if set(raw_groups)!=set(wanted) or any(len(raw_groups[k])!=n for k,n in wanted.items()):
            raw=None;raw_warning='runs.csv counts do not match summary.csv. Survival figures omitted to prevent mixing stale snapshots.'
        else:raw_warning='Survival figures use all raw event times in runs.csv, not the coarsely sampled survival CSV.'
    header += ['## Figures',raw_warning,
               f'Trend figures compare warm-up lengths within a fixed margin, budget, cap and branch. Survival panels, when available, focus on {focus} warm-up steps and include both a full view and a 0–{zoom}-step zoom. PNG filenames describe their settings.']
    sections=[];index=[]
    for g,rows in sorted(groups.items()):
        design,mode,eta,C,Delta,request,branch=g
        stem=f'{token(design)}_eta{token(eta)}_budget{token(C)}_cap{token(Delta)}_{token(request)}_{branch}'
        title=f'{design}; margin {eta}; C={C}; Delta={Delta}; {branch}; selection={request}'
        sections += ['## '+title]
        if mode=='warmup':
            fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
            for rule in ['epsilon_greedy','softmax','ucb']:
                rr=sorted([r for r in rows if r['rule']==rule],key=lambda r:initialization(r)['steps'])
                if not rr:continue
                xx=[initialization(r)['steps'] for r in rr]
                yy=[float(r['restricted_mean']) for r in rr]
                axes[0].plot(xx,yy,'o-',label=LABELS[rule],color=COLORS[rule])
                for x,y,r in zip(xx,yy,rr):
                    lo=number(r['restricted_mean_ci_low']);hi=number(r['restricted_mean_ci_high'])
                    if lo is not None and hi is not None:
                        axes[0].vlines(x,lo,hi,color=COLORS[rule],linewidth=2)
                    if int(r['censored']):axes[0].scatter([x],[y],marker='^',s=90,facecolors='none',edgecolors=COLORS[rule])
                axes[1].plot(xx,[float(r['attainment_rate']) for r in rr],'o-',color=COLORS[rule],label=LABELS[rule])
            axes[0].set_yscale('symlog',linthresh=1)
            axes[0].set(ylabel=f'Restricted mean Q-recovery time\n(symlog scale; horizon {H})',title='Q recovery; triangles mark censoring')
            axes[1].set(ylabel='Fraction attaining target ordering',ylim=(-.03,1.03),title='Immediate attack success')
            for ax in axes:
                ax.set_xscale('symlog',linthresh=100);ax.set_xlim(left=0,right=max(initialization(r)['steps'] for r in rows) or 1);ax.set_xlabel('Clean warm-up steps (symlog scale)');ax.legend(fontsize=8);ax.grid(alpha=.2)
            fig.suptitle(title,fontsize=10)
            filename=stem+'_warmup.png';fig.savefig(out/'plots'/filename,dpi=150);plt.close(fig)
            sections += [f'[Open warm-up comparison](plots/{filename})',f'![{title}](plots/{filename})']
            index.append([filename,title,'Q recovery and attainment','warm-up length'])
        # Four metric rows per rule and initialization, with clean baseline + paired differences.
        table=[]
        for r in sorted(rows,key=lambda r:(json.dumps(initialization(r),sort_keys=True),r['rule'])):
            related=[s for s in summary if s['condition_id']==r['condition_id'] and s['branch']==branch]
            for metric in METRICS:
                a=next(s for s in related if s['arm']=='faa' and s['metric']==metric)
                b=next(s for s in related if s['arm']=='clean' and s['metric']==metric)
                ci=(f"[{fmt(a['restricted_mean_ci_low'])}, {fmt(a['restricted_mean_ci_high'])}]"
                    if a['restricted_mean_ci_low'] else 'not estimated')
                table.append([json.dumps(initialization(a),sort_keys=True),LABELS[a['rule']],metric,a['n'],
                    fmt(b['restricted_mean']),fmt(a['restricted_mean']),ci,
                    f"{fmt(a['median'])}; {fmt(a['q25'])}–{fmt(a['q75'])}",a['censored'],
                    fmt(a['paired_faa_minus_clean_restricted_mean'])])
        sections += [md_table(['Initialization','Rule','Metric','n','Clean restricted mean','FAA restricted mean','FAA 95% CI','Median; Q25–Q75','Censored','Paired FAA − clean'],table)]
        sections += [md_table(['Initialization','Rule','n','Target attainment','Spend min–max','Clipped','Pre-attack Q-error','Mean counts: optimal / other'],[
            [json.dumps(initialization(r),sort_keys=True),LABELS[r['rule']],r['n'],f"{100*float(r['attainment_rate']):.1f}%",
             f"{fmt(r['spent_min'])}–{fmt(r['spent_max'])}",r['clipped_count'],fmt(r['pre_q_error_mean']),
             f"{fmt(r['pre_count_optimal_mean'])} / {fmt(r['pre_count_other_mean'])}"] for r in rows])]
        small=[f"{LABELS[r['rule']]} {initialization(r)}: n={r['n']}" for r in rows if r['rule']!='ucb' and int(r['n'])<30]
        if small:sections+=['**Small branch samples:** '+ '; '.join(small)+'. Interpret their means cautiously.']
        if raw is not None:
            chosen=[r for r in rows if mode=='warmup' and initialization(r).get('steps')==focus]
            if chosen:
                for window,xmax in [('full',H),('zoom',min(zoom,H))]:
                    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
                    for ax,metric in zip(axes.flat,METRICS):
                        for r in chosen:
                            for arm,style in [('faa','-'),('clean',':')]:
                                rr=raw_groups[(r['condition_id'],branch,arm)]
                                times=np.array([H+1 if x[metric]=='' else int(x[metric]) for x in rr])
                                survival=1-np.cumsum(np.bincount(times,minlength=H+2)[:H+1])/len(times)
                                ax.step(np.arange(H+1),survival,where='post',color=COLORS[r['rule']],linestyle=style,
                                    label=f"{LABELS[r['rule']]} {arm}, n={len(rr)}")
                        ax.set(title=metric.replace('_',' '),xlabel='Clean steps after intervention',ylabel='Fraction with event not yet observed',xlim=(0,xmax),ylim=(-.02,1.02));ax.legend(fontsize=6);ax.grid(alpha=.2)
                    fig.suptitle(title+f'; warm-up={focus}',fontsize=10)
                    filename=stem+f'_steps{focus}_survival_{window}.png'
                    fig.savefig(out/'plots'/filename,dpi=150);plt.close(fig)
                    sections += [f'[Open matched survival comparison ({window})](plots/{filename})']
                    index.append([filename,title,'Four event definitions',f'warm-up={focus}; {window}'])
    header += [md_table(['PNG','Condition','Measurements','View'],[[f'[{a}](plots/{a})',b,c,d] for a,b,c,d in index])]
    footer=['## What is not measured here',
        'No comparable fixed-horizon reward-loss estimate is produced by this recovery runner: it can stop after all recovery events are observed. Do not compare wrong_action_steps_observed as if every trajectory had the same length. Multi-state coverage, navigation, error propagation and repeated FAA expenditure require the separate multi-state experiments.',
        '## Reproduction and next step',
        'Keep this report folder together: the Markdown uses relative links to plots/ and data/. Upload the ZIP containing the entire folder, rather than selecting opaque PNG filenames individually. Finish incomplete conditions before interpreting their comparison. For a completed warm-up sweep, the next experiment is a small chain testing state visitation and bootstrapping; this report alone does not establish multi-state recovery rates.',
        '## References and theory',
        'The project THEORY.md states assumptions and proofs. FAA background: [Zhang et al. (2020)](https://arxiv.org/abs/2003.12613). This code uses its documented corrected demotion sign and does not claim an identical reproduction of unpublished author code.']
    (out/'REPORT.md').write_text('\n\n'.join(header+sections+footer)+'\n',encoding='utf-8')
    # Preserve source checksums without copying large per-run data into the report.
    hashes={}
    for name in ['summary.csv','runs.csv','README.md']:
        p=source/name
        if p.exists():hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'data/source_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,Path(out.name)/p.relative_to(out))
    print(f'Report: {out / "REPORT.md"}\nUpload package: {archive}\nCompleted pairs: {completed}; plots: {len(index)}')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,help='Analysis folder containing summary.csv and preferably runs.csv')
    p.add_argument('--out',required=True,help='New report directory, outside the analysis folder')
    p.add_argument('--focus-warmup',type=int,default=1000)
    p.add_argument('--zoom',type=int,default=200)
    a=p.parse_args()
    if a.zoom<=0 or a.focus_warmup<0:p.error('Require positive zoom and nonnegative warm-up')
    build(a.input,a.out,a.focus_warmup,a.zoom)
