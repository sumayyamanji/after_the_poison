"""Rebuild thesis chain plotting CSVs from original/audit report exports."""
from pathlib import Path
import csv,collections,json,shutil,argparse
ROOT=Path(__file__).resolve().parent

def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def num(x):return float(x) if x!='' else None
def rebuild(reports,out):
    out.mkdir(parents=True,exist_ok=True);combined=[]
    for start,tag in [('S0','start0'),('S2','controlled')]:
        runs=rows(reports/f'{tag}_audit/runs.csv');summary=rows(reports/f'{tag}_audit/summary.csv')
        original={(r['condition_id'],r['seed']):r for r in rows(reports/f'{tag}_original/runs.csv') if r['arm']=='faa'}
        assert len(runs)==len(original)==3606
        groups=collections.defaultdict(list)
        for r in runs:groups[r['condition_id']].append(r)
        for cid,rs in groups.items():
            r=rs[0];old=[original[(cid,x['seed'])] for x in rs]
            row=dict(start=start,counts=100 if 'counts100_' in r['design'] else 1,rule=r['rule'],C=float(r['C']),n=len(rs),
               attained=sum(x['attainment_time']!='' for x in old),target_at_last=sum(x['target_at_last_poison']=='True' for x in rs),
               target_at_cutoff=sum(x['target_at_cutoff']=='True' for x in rs),spent_mean=sum(float(x['spent']) for x in rs)/len(rs),
               last_poison_mean=sum(float(x['last_poison_step']) for x in rs)/len(rs),q_censored_H=sum(x['q_observed_by_H']=='False' for x in rs))
            for metric in ['q_restricted_H','policy_restricted_H','target_loss_restricted_H','attack_reward_loss','recovery_reward_loss','combined_reward_loss']:
                sr=next(x for x in summary if x['condition_id']==cid and x['metric']==metric)
                for k in ['mean','ci_low','ci_high']:row[metric+'_'+k]=num(sr[k])
                row[metric+'_n']=int(sr['n'])
            combined.append(row)
        shutil.copy2(reports/f'{tag}_audit/runs.csv',out/f'{start}_runs.csv')
    combined.sort(key=lambda x:(x['C'],x['counts'],x['rule'],x['start']))
    with (out/'COMBINED_CONDITIONS.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(combined[0]));w.writeheader();w.writerows(combined)
    for tag,cid,stem in [('controlled','cd120c9fc60950b6','ucb_state_access'),('start0','ff53513639bde55f','ucb_action_access')]:
        shutil.copy2(reports/f'{tag}_audit/replay_{cid}.csv',out/(stem+'.csv'))
    print('Rebuilt 36 chain condition rows and selected replay inputs:',out)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reports',type=Path,default=ROOT/'saved_reports');p.add_argument('--out',type=Path,default=ROOT/'outputs/rebuilt_inputs');a=p.parse_args();rebuild(a.reports,a.out)
