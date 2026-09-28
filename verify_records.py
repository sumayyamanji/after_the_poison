"""Check archived raw jobs against manifests, code hashes and saved report rows."""
from pathlib import Path
import csv,gzip,hashlib,json,math,sys,zipfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'simulation'))
from qpoison.multistep import jobs as multistep_jobs
from qpoison.persistence import jobs as terminal_jobs

def readcsv(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def equal(value,text):
    if value is None:return text==''
    if isinstance(value,bool):return text==str(value)
    if isinstance(value,(int,float)):return math.isclose(float(text),value,rel_tol=1e-10,abs_tol=1e-9)
    return str(value)==text

def verify(replay=False):
    result={};representatives=[]
    for tag in ['controlled','start0']:
        m=json.loads((ROOT/f'manifests/{tag}.json').read_text());cfg=m['config'];expected={x['id']:x for x in multistep_jobs(cfg)}
        assert len(expected)==m['expected_jobs']==3606
        for name,digest in m['source_hashes'].items():
            assert hashlib.sha256((ROOT/'simulation/qpoison'/name).read_bytes()).hexdigest()==digest,name
        original={(r['condition_id'],r['seed'],r['arm']):r for r in readcsv(ROOT/f'saved_reports/{tag}_original/runs.csv')}
        audit={(r['condition_id'],r['seed']):r for r in readcsv(ROOT/f'saved_reports/{tag}_audit/runs.csv')}
        seen=set();reps={};checked=0
        with zipfile.ZipFile(ROOT/f'raw_archives/{tag}_records.zip') as z:
            for name in sorted(n for n in z.namelist() if n.endswith('.json.gz')):
                r=json.loads(gzip.decompress(z.read(name)));rid=r['id'];assert rid not in seen;seen.add(rid)
                j=expected[rid];assert r['condition']==j['condition'] and r['seed']==j['seed']
                for arm,a in r['arms'].items():
                    saved=original[(r['condition_id'],str(r['seed']),arm)]
                    checks={'spent':a['spent'],'attainment_time':a['attainment_time'],'attainment_spend':a['attainment_spend'],
                       'cutoff_q_error':a['cutoff']['q_error'],'final_q_error':a['final']['q_error'],
                       'target_at_cutoff':a['cutoff']['target_success'],'last_nonzero_poison_step':a['last_nonzero_poison_step'],**a['events']}
                    for phase in ['attack','recovery']:
                        checks.update({phase+'_'+k:v for k,v in a['totals'][phase].items()})
                    for k,v in checks.items():assert equal(v,saved[k]),(tag,rid,arm,k,v,saved[k])
                    checked+=1
                a=r['arms']['faa'];clean=r['arms']['clean'];saved=audit[(r['condition_id'],str(r['seed']))]
                for key,val in [('spent',a['spent']),('last_poison_step',a['last_nonzero_poison_step']),('target_at_cutoff',a['cutoff']['target_success'])]:
                    assert equal(val,saved[key]),(rid,key)
                for phase in ['attack','recovery']:
                    loss=clean['totals'][phase]['reward']-a['totals'][phase]['reward']
                    assert equal(loss,saved[phase+'_reward_loss'])
                cols={k:i for i,k in enumerate(r['attack_log_columns'])};log=a['attack_log'];assert len(log)==cfg['attack_steps']
                assert [x[cols['step']] for x in log]==list(range(1,cfg['attack_steps']+1))
                ds=[x[cols['delta']] for x in log]
                assert max(map(abs,ds))<=r['condition']['Delta']+1e-9
                assert sum(map(abs,ds))<=r['condition']['C']+1e-8
                assert math.isclose(sum(map(abs,ds)),a['spent'],abs_tol=1e-8)
                assert max((i for i,d in enumerate(ds,1) if d!=0),default=None)==a['last_nonzero_poison_step']
                if replay and r['condition']['C']==3:
                    prior=reps.get(r['condition_id'])
                    if prior is None or r['seed']<prior['seed']:reps[r['condition_id']]=r
        assert seen==set(expected);assert len(audit)==len(seen);assert len(original)==checked
        count=0
        if replay:
            from audit_multistep import independent_replay,reconstruct
            for cid,r in sorted(reps.items()):
                d=reconstruct(r,cfg);independent_replay(r,cfg)
                saved=audit[(cid,str(r['seed']))]
                for event,t in d['events'].items():assert equal(t,saved[event+'_time_from_last']),(tag,cid,event)
                count+=1;print('Independent replay passed:',tag,cid,flush=True)
        result[tag]={'expected':len(expected),'valid_unique_records':len(seen),'matched_original_arm_rows':checked,
                     'core_code_hashes_match':True,'budget_logs_checked':True,'independent_replays':count}
        print(tag,result[tag],flush=True)
    m=json.loads((ROOT/'manifests/terminal_validation.json').read_text());cfg=m['config']
    digest=hashlib.sha256(b''.join((ROOT/'simulation/qpoison'/n).read_bytes() for n in ['persistence.py','learner.py','faa.py','mdp.py'])).hexdigest()
    assert digest==m['simulation_code_hash'];expected={x['id']:x for x in terminal_jobs(cfg)}
    seen=set();complete=skipped=0
    saved={(r['job_id'],r['arm']):r for r in readcsv(ROOT/'saved_reports/terminal_validation/runs.csv')}
    with zipfile.ZipFile(ROOT/'raw_archives/terminal_validation_records.zip') as z:
        for name in sorted(n for n in z.namelist() if n.endswith('.json')):
            r=json.loads(z.read(name));assert r['id'] not in seen;seen.add(r['id'])
            assert r['condition']==expected[r['id']]['condition']
            if r['status']=='complete':
                complete+=1
                for a in r['paired']:
                    s=saved[(r['id'],a['arm'])]
                    for k,v in a['times'].items():assert equal(v,s[k]),(r['id'],k)
                    assert equal(a['spent'],s['spent'])
            else:skipped+=1
    assert seen==set(expected);assert complete==2402 and skipped==2
    # The terminal figure uses the exact saved summary and survival exports.
    for f in ['summary.csv','survival.csv']:
        assert (ROOT/'saved_reports/terminal_validation'/f).read_bytes()==(ROOT/'publication/data'/('terminal_'+f)).read_bytes()
    result['terminal_validation']={'expected':len(expected),'completed_pairs':complete,'skipped_impossible_branches':skipped,'code_hash_matches':True,'events_match_saved_export':True}
    result['scope']='Archive identity, completeness, report alignment and budgets verified; optional selected replay independently checks learner dynamics. Not a fresh full simulation rerun or independent FAA planner verification.'
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--replay',action='store_true');p.add_argument('--out',type=Path,default=ROOT/'outputs/record_verification.json');a=p.parse_args()
    result=verify(a.replay);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(a.out)
