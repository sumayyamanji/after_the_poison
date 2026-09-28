import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from qpoison.persistence import jobs, run_job, run_suite
from qpoison.persistence_theory import predict, geometric_sum
from qpoison.persistence_analysis import empirical_survival

ROOT=Path(__file__).resolve().parents[1]


class PersistenceTests(unittest.TestCase):
    def config(self):
        return json.loads((ROOT/'configs/persistence_smoke.json').read_text())

    def test_geometric_sum_against_closed_two_stage_distribution(self):
        p=.2; horizon=20
        s,m,v=geometric_sum([p,p],horizon)
        # P(two successes have not occurred)=P(0 successes)+P(1 success).
        expected=[1.] + [(1-p)**t+t*p*(1-p)**(t-1) for t in range(1,horizon+1)]
        np.testing.assert_allclose(s,expected,atol=1e-14)
        self.assertAlmostEqual(m,10)
        self.assertAlmostEqual(v,40)
        shifted,_,_=geometric_sum([p,p],horizon,3)
        np.testing.assert_allclose(shifted[3:],s[:-3])

    def test_exact_pilot_means_and_confirmation_offset(self):
        spec=self.config()['learner_defaults']
        for eta in [.01,1.]:
            eps=predict([-eta,0],[101,100],[1,0],0,{**spec,'rule':'epsilon_greedy'},2000,.05,20)
            self.assertAlmostEqual(eps['summaries']['q_confirmation']['mean'],20+1/.95+19)
            soft=predict([-eta,0],[101,100],[1,0],0,{**spec,'rule':'softmax'},2000,.05,20)
            expected=1+np.exp(eta/.2)+1+np.exp(((1+eta)*.1-1)/.2)+19
            self.assertAlmostEqual(soft['summaries']['q_confirmation']['mean'],expected)
            self.assertAlmostEqual(soft['summaries']['q_confirmation']['mean']-soft['summaries']['q_recovery']['mean'],19)

    def test_promotion_uses_opposite_probability_and_ties(self):
        spec={**self.config()['learner_defaults'],'rule':'epsilon_greedy'}
        demote=predict([-1,0],[101,100],[1,0],0,spec,100,.05,20)
        promote=predict([1,2],[100,101],[1,0],1,spec,100,.05,20)
        self.assertAlmostEqual(demote['summaries']['first_revisit']['mean'],20)
        self.assertAlmostEqual(promote['summaries']['first_revisit']['mean'],1/.95)
        tie=predict([0,0],[10,10],[1,0],0,spec,100,.05,20)
        self.assertEqual(tie['summaries']['greedy_recovery']['mean'],0)
        self.assertAlmostEqual(tie['summaries']['first_revisit']['mean'],1/.95)

    def test_ucb_predictions_match_independent_learner_runner(self):
        config=self.config();config['horizon']=2000
        for job in jobs(config):
            if job['condition']['learner']['rule']!='ucb' or job['condition']['mode']!='controlled':continue
            record=run_job(config,job)
            if record['status']=='skipped':continue
            for row in record['paired']:
                theory=predict(row['post_q'],row['post_counts'],config['rewards'],row['intervention_action'],
                               job['condition']['learner'],config['horizon'],config['q_tolerance'],config['confirmation_window'])
                for metric,time in row['times'].items():
                    self.assertEqual(time,theory['summaries'][metric]['exact_time_within_horizon'])

    def test_cap_failure_is_logged_not_assumed_success(self):
        config=self.config();job=next(jobs(config))
        job['condition'].update(eta=1.,C=.2,Delta=.1)
        record=run_job(config,job);attack=record['paired'][1]
        self.assertAlmostEqual(attack['spent'],.1)
        self.assertTrue(attack['clipped_by_delta'])
        self.assertFalse(attack['attained_target'])
        self.assertAlmostEqual(attack['post_q'][0],.91)
        job['condition'].update(C=.05,Delta=3.)
        attack=run_job(config,job)['paired'][1]
        self.assertTrue(attack['clipped_by_budget'])
        self.assertAlmostEqual(attack['spent'],.05)

    def test_warmup_counts_persist_and_controls_share_initial_state(self):
        config=self.config()
        job=next(j for j in jobs(config) if j['condition']['mode']=='warmup')
        record=run_job(config,job)
        clean,attack=record['paired']
        self.assertEqual(sum(attack['pre_counts']),100)
        self.assertEqual(sum(attack['post_counts']),101)
        self.assertEqual(clean['pre_q'],attack['pre_q'])
        self.assertEqual(clean['pre_counts'],attack['pre_counts'])
        self.assertEqual(clean['intervention_action'],attack['intervention_action'])
        self.assertFalse(attack['conditional_action_experiment'])

    def test_impossible_ucb_promotion_is_skipped(self):
        config=self.config()
        job=next(j for j in jobs(config) if j['condition']['learner']['rule']=='ucb' and j['condition']['branch_request']=='promotion')
        self.assertEqual(run_job(config,job)['status'],'skipped')

    def test_censoring_restricted_mean_and_time_zero(self):
        survival=empirical_survival([0,2,None],5)
        np.testing.assert_allclose(survival,[2/3,2/3,1/3,1/3,1/3,1/3])
        self.assertAlmostEqual(survival[:-1].sum(),7/3)
        self.assertGreater(survival[-1],0)

    def test_resume_and_configuration_guard(self):
        config=self.config();config['horizon']=30
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            configpath=Path(directory)/'config.json';configpath.write_text(json.dumps(config))
            out=Path(directory)/'results'
            run_suite(configpath,out,limit=1)
            first=next((out/'records').glob('*.json'));before=first.read_bytes()
            run_suite(configpath,out,resume=True,limit=1)
            self.assertEqual(len(list((out/'records').glob('*.json'))),2)
            self.assertEqual(first.read_bytes(),before)
            config['horizon']=31;configpath.write_text(json.dumps(config))
            with self.assertRaises(ValueError):run_suite(configpath,out,resume=True)

    def test_diminishing_alpha_not_given_constant_alpha_prediction(self):
        spec={**self.config()['learner_defaults'],'rule':'softmax','alpha_schedule':'per_visit'}
        self.assertIsNone(predict([-1,0],[100,100],[1,0],0,spec,20,.05,20))

if __name__=='__main__':unittest.main()
