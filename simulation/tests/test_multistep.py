import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from qpoison.multistep import RecoveryTracker, read_json, run_job, run_suite, jobs
from qpoison.multistep_analysis import event_summary
from qpoison.mdp import build_mdp
from qpoison.learner import QLearner
from qpoison.faa import greedy_perturbation


def small():
    config=json.loads((Path(__file__).resolve().parents[1]/'configs/multistep_smoke.json').read_text())
    config.update(attack_steps=8,post_steps=25,seeds=2,trace_every=1,confirmation=3)
    config['designs'][0]['initialization']['steps']=11
    return config


class MultiStateTests(unittest.TestCase):
    def test_full_horizon_zero_budget_and_phase_counts(self):
        config=small()
        for job in jobs(config):
            if job['condition']['C']!=0:continue
            r=run_job(config,job)
            self.assertEqual(np.sum(r['initial']['counts']),11)
            for arm in ('clean','faa'):
                x=r['arms'][arm]
                self.assertEqual(np.sum(x['cutoff']['counts']),19)
                self.assertEqual(np.sum(x['final']['counts']),44)
                self.assertEqual(x['totals']['attack']['updates'],8)
                self.assertEqual(x['totals']['recovery']['updates'],25)
                self.assertEqual(np.sum(x['visits']['recovery']),25)
            for key in ('cutoff','final','totals','events','visits','trace'):
                self.assertEqual(r['arms']['clean'][key],r['arms']['faa'][key])

    def test_recurrence_confirmation_and_boundary_events(self):
        tracker=RecoveryTracker(3)
        sequence=[(True,True,True),(False,True,False),(True,False,True),(True,True,False),(True,True,False),(True,True,False)]
        for u,(q,p,t) in enumerate(sequence):tracker.observe(u,q,p,t)
        self.assertEqual(tracker.times,{'target_loss':1,'greedy_recovery':0,'q_recovery':0,
                                       'greedy_confirmation':5,'q_confirmation':4})
        self.assertEqual(tracker.recurred,{'q':True,'greedy':True,'target_loss':True})
        self.assertEqual(tracker.target_steps,1)
        at_zero=RecoveryTracker(1);at_zero.observe(0,True,True,False)
        self.assertTrue(all(x==0 for x in at_zero.times.values()))

    def test_censoring_event_at_horizon_and_empirical_rmst(self):
        rng=np.random.default_rng(0)
        times=[0,2,5,None];s=event_summary(times,5,rng)
        self.assertEqual(s['recovered'],3);self.assertEqual(s['censored'],1)
        self.assertEqual(s['median'],2);self.assertIsNone(s['observed_mean_if_no_censoring'])
        area=sum(sum(t is None or t>u for t in times)/len(times) for u in range(5))
        self.assertEqual(s['restricted_mean'],area)
        self.assertIsNone(event_summary([None,None,2],5,rng)['median'])
        self.assertIsNone(event_summary([],5,rng)['restricted_mean'])

    def test_caps_spend_reconstruction_and_poison_stops(self):
        config=small();config['budgets']=[.2];config['delta_limits']=[.05]
        for job in jobs(config):
            r=run_job(config,job);x=r['arms']['faa'];log=x['attack_log']
            self.assertEqual(len(log),config['attack_steps'])
            self.assertAlmostEqual(sum(abs(row[7]) for row in log),x['spent'])
            self.assertAlmostEqual(sum(x['spending_by_purpose'].values()),x['spent'])
            self.assertLessEqual(x['spent'],.2+1e-10)
            self.assertTrue(all(abs(row[7])<=.05+1e-10 for row in log))
            for row in log:self.assertAlmostEqual(row[14],row[13]+row[8]*row[7])
            if x['attainment_time'] is not None:
                cost=sum(abs(row[7]) for row in log if row[0]<=x['attainment_time'])
                self.assertAlmostEqual(cost,x['attainment_spend'])
            self.assertTrue(all(t['spent']==x['spent'] for t in x['trace'] if t['t']>=config['attack_steps']))

    def test_observation_cutoff_does_not_change_trajectory(self):
        config=small();config['budgets']=[3.];job=next(jobs(config))
        short=run_job(config,job);longconfig=copy.deepcopy(config);longconfig['post_steps']=40
        long=run_job(longconfig,job)
        end=config['attack_steps']+config['post_steps']
        for arm in ('clean','faa'):
            self.assertEqual(short['arms'][arm]['final']['q'],next(t['q'] for t in long['arms'][arm]['trace'] if t['t']==end))
            self.assertEqual(short['arms'][arm]['final']['counts'],next(t['counts'] for t in long['arms'][arm]['trace'] if t['t']==end))

    def test_sweeps_and_first_updates_against_dense_counts(self):
        config=small();config.update(post_steps=500,rules=['epsilon_greedy'],budgets=[3.],seeds=1)
        r=run_job(config,next(jobs(config)))
        for arm in ('clean','faa'):
            data=r['arms'][arm];tr=[x for x in data['trace'] if x['t']>=config['attack_steps']]
            prev=np.array(data['cutoff']['counts']);seen=np.zeros_like(prev,dtype=bool);ends=[]
            first=np.full_like(prev,-1)
            for row in tr[1:]:
                new=np.array(row['counts']);mask=new>prev;u=row['t']-config['attack_steps']
                first[(first<0)&mask]=u;seen|=mask
                if seen.all():ends.append(u);seen[:]=False
                prev=new
            self.assertEqual(first.tolist(),data['first_entry_update'])
            self.assertEqual(ends,[x['u'] for x in data['sweeps']])

    def test_resume_config_and_code_guards(self):
        config=small();config.update(rules=['ucb'],budgets=[0.,3.])
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/'config.json';cfg.write_text(json.dumps(config));out=Path(d)/'run'
            run_suite(cfg,out,limit=1)
            self.assertEqual(len(list((out/'records').glob('*.json.gz'))),1)
            run_suite(cfg,out,resume=True)
            self.assertTrue(read_json(out/'status.json')['complete'])
            with patch('qpoison.multistep.source_hash',return_value={'changed':True}):
                with self.assertRaises(ValueError):run_suite(cfg,out,resume=True)
            config['post_steps']+=1;cfg.write_text(json.dumps(config))
            with self.assertRaises(ValueError):run_suite(cfg,out,resume=True)

    def test_controlled_counts_and_stochastic_ucb_replication(self):
        config=small();config['designs'][0]['initialization']={'mode':'controlled','counts':[[1,100],[2,200],[3,300]]}
        r=run_job(config,next(jobs(config)))
        np.testing.assert_allclose(r['initial']['q'],r['q_star'])
        self.assertEqual(r['initial']['counts'],[[1,100],[2,200],[3,300]])
        config['rules']=['ucb'];config['budgets']=[3.]
        self.assertEqual(len(list(jobs(config))),1)
        config['designs'][0]['environment']['slip']=.1
        self.assertEqual(len(list(jobs(config))),config['seeds'])

    def test_protocol_numerical_example(self):
        env=build_mdp({'kind':'chain','n_states':3,'start':0});q=env.optimal_q(.9)
        np.testing.assert_allclose(q,[[.458,.62],[.458,.8],[.62,1]],atol=1e-10)
        x=QLearner(3,2,{'rule':'epsilon_greedy','alpha':.9},.9,q)
        clean=x.clean_candidate(1,1,-.1,2,False)
        delta=greedy_perturbation(x.q[1],1,[True,False],clean,.9,.01)
        x.update(1,1,-.1,2,False,delta);self.assertAlmostEqual(x.q[1,1],.448)
        x.update(0,1,-.1,1,False);self.assertAlmostEqual(x.q[0,1],.34298)
        x.update(1,1,-.1,2,False);self.assertAlmostEqual(x.q[1,1],.7648)

if __name__=='__main__':unittest.main()
