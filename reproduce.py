#!/usr/bin/env python3
"""One entry point for plotting, archive checks, reanalysis and fresh simulations."""
from pathlib import Path
import argparse,csv,gzip,hashlib,importlib.util,json,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent
EXPERIMENTS=['controlled','start0','terminal_validation']
def run(args,cwd=None):
    print('Running:', ' '.join(map(str,args)),flush=True)
    completed=subprocess.run([str(x) for x in args],cwd=cwd or ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    print(completed.stdout,end="",flush=True)
    completed.check_returncode()
def prepare(tag):
    out=ROOT/'outputs/raw'/tag;out.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/f'manifests/{tag}.json';dest=out/'manifest.json'
    if dest.exists() and dest.read_bytes()!=manifest.read_bytes():raise ValueError('Different manifest in '+str(out))
    shutil.copy2(manifest,dest);rec=out/'records';rec.mkdir(exist_ok=True)
    archive=ROOT/f'raw_archives/{tag}_records.zip'
    if not archive.exists():raise FileNotFoundError(f'{archive}: use the full ZIP or place its raw_archives folder here.')
    with zipfile.ZipFile(archive) as z:
        seen=set()
        for name in z.namelist():
            if not name.endswith(('.json.gz','.json')):continue
            base=Path(name).name
            if base in seen:raise ValueError('Duplicate filename '+base)
            seen.add(base);target=rec/base;data=z.read(name)
            if target.exists():
                if target.read_bytes()!=data:raise ValueError('Existing record differs: '+str(target))
            else:target.write_bytes(data)
    print('Prepared:',tag,len(seen),'records');return out

def figures(out,inputs=None,latex=False):
    if out.exists() and any(out.iterdir()):raise ValueError('Choose an empty figure output directory.')
    shutil.copytree(ROOT/'publication',out,dirs_exist_ok=True)
    if inputs:
        for name in ['COMBINED_CONDITIONS.csv','S0_runs.csv','S2_runs.csv','ucb_state_access.csv','ucb_action_access.csv']:
            shutil.copy2(inputs/name,out/'data'/name)
    run([sys.executable,out/'make_figures.py'])
    run([sys.executable,out/'tools/make_missing_figures.py'])
    run([sys.executable,out/'tools/reexport_replay_figures.py'])
    spec=importlib.util.spec_from_file_location('count_plot',out/'tools/ucb_count_sweep.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    rows=[json.loads(f.read_text())['result'] for f in sorted((out/'data/ucb_count_sweep/records').glob('*.json'))]
    assert len(rows)==32;mod.add_slopes(rows);mod.plot_results(rows,out/'data/ucb_count_sweep')
    for ext in ['pdf','png']:
        shutil.copy2(out/'data/ucb_count_sweep'/('asymptotic_ratio.'+ext),out/'figures'/('ucb_count_ratio.'+ext))
    if latex:
        # The dissertation uses this TikZ source. The Python schematic is an alternative export.
        run(['pdflatex','-interaction=nonstopmode','-halt-on-error','figure3_1.tex'],cwd=out)
        shutil.copy2(out/'figure3_1.pdf',out/'figures/chain_reset_timeline_tikz.pdf')
    print('Figures saved:',out/'figures')

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    v=s.add_parser('verify');v.add_argument('--replay',action='store_true')
    f=s.add_parser('figures');f.add_argument('--out',type=Path,default=ROOT/'outputs/figure_rebuild');f.add_argument('--inputs',type=Path);f.add_argument('--latex',action='store_true')
    q=s.add_parser('prepare');q.add_argument('--experiment',choices=EXPERIMENTS+['all'],default='all')
    r=s.add_parser('reanalyse');r.add_argument('--experiment',choices=EXPERIMENTS+['all'],default='all');r.add_argument('--out',type=Path,default=ROOT/'outputs/reanalysis')
    t=s.add_parser('rerun');t.add_argument('--experiment',choices=EXPERIMENTS,required=True);t.add_argument('--out',type=Path);t.add_argument('--resume',action='store_true');t.add_argument('--dry-run',action='store_true');t.add_argument('--limit',type=int)
    c=s.add_parser('sweep');c.add_argument('--out',type=Path,default=ROOT/'outputs/count_sweep');c.add_argument('--resume',action='store_true')
    a=p.parse_args()
    if a.command=='verify':
        args=[sys.executable,ROOT/'verify_records.py']+(['--replay'] if a.replay else []);run(args)
    elif a.command=='figures':figures(a.out.resolve(),a.inputs.resolve() if a.inputs else None,a.latex)
    elif a.command in ['prepare','reanalyse']:
        tags=EXPERIMENTS if a.experiment=='all' else [a.experiment]
        for tag in tags:
            raw=prepare(tag)
            if a.command=='reanalyse':
                out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
                if tag=='terminal_validation':
                    run([sys.executable,ROOT/'simulation/analyze_persistence.py','--input',raw,'--max-plots','0'])
                    dest=out/tag
                    if dest.exists():raise ValueError('Choose a fresh reanalysis output.')
                    shutil.copytree(raw/'analysis',dest)
                else:
                    run([sys.executable,ROOT/'simulation/analyze_multistep.py','--input',raw,'--out',out/(tag+'_original')])
                    run([sys.executable,ROOT/'simulation/audit_multistep.py','--input',raw,'--out',out/(tag+'_audit'),'--replay'])
    elif a.command=='rerun':
        tag=a.experiment;script='run_persistence.py' if tag=='terminal_validation' else 'run_multistep.py'
        out=(a.out or ROOT/'outputs/fresh_simulations'/tag).resolve()
        protected=[ROOT/'publication',ROOT/'saved_reports',ROOT/'raw_archives']
        if any(out==x or x in out.parents for x in protected):raise ValueError('Use a separate output directory.')
        args=[sys.executable,ROOT/'simulation'/script,'--config',ROOT/'simulation/configs'/f'{tag}.json','--out',out]
        if a.resume:args+=['--resume']
        if a.dry_run:args+=['--dry-run']
        if a.limit is not None:args+=['--limit',str(a.limit)]
        run(args)
    elif a.command=='sweep':
        args=[sys.executable,ROOT/'publication/tools/ucb_count_sweep.py','--output',a.out.resolve()]
        if a.resume:args+=['--resume']
        run(args)
if __name__=='__main__':main()
