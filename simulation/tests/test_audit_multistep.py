"""Boundary and corruption-detection checks for the raw-record audit add-on."""
import copy
import json
from pathlib import Path
import unittest
import numpy as np
from audit_multistep import reconstruct, independent_replay, flags
from qpoison.multistep import jobs, run_job


def config():
    c=json.loads((Path(__file__).resolve().parents[1]/'configs/multistep_smoke.json').read_text())
    c.update(attack_steps=30,post_steps=40,seeds=1,confirmation=3,budgets=[0.,3.])
    c['designs'][0]['initialization']={'mode':'controlled','counts':1}
    c['designs'][0]['environment']['start']=0
    return c


class AuditTests(unittest.TestCase):
    def test_no_poison_has_no_invented_clock(self):
        c=config();j=next(jobs(c));r=run_job(c,j);d=reconstruct(r,c)
        self.assertIsNone(d['last']);self.assertIsNone(d['q_last'])
        self.assertTrue(all(t is None for t in d['events'].values()))

    def test_reconstruction_rejects_altered_logged_update(self):
        c=config();c['budgets']=[3.];r=run_job(c,next(jobs(c)))
        reconstruct(r,c)
        bad=copy.deepcopy(r);bad['arms']['faa']['attack_log'][0][-1]+=.1
        with self.assertRaises(AssertionError):reconstruct(bad,c)

    def test_independent_full_replay_and_last_clock_all_rules(self):
        c=config();c['budgets']=[3.]
        for j in jobs(c):
            r=run_job(c,j);d=reconstruct(r,c);replay=independent_replay(r,c)
            ell=d['last'];q=replay['faa']['q'];star=np.array(r['q_star']);targets=np.array(r['targets'],bool)
            fs=[flags(x,star,targets,c['q_tolerance'],1e-10) for x in q[ell:]]
            for key,actual in d['events'].items():
                expected=next((t for t,f in enumerate(fs) if f[key]),None)
                self.assertEqual(expected,actual)
            first=np.full_like(np.array(r['initial']['counts']),-1)
            for x in replay['faa']['steps']:
                if x['step']>ell and first[x['state'],x['action']]<0:
                    first[x['state'],x['action']]=x['step']-ell
            np.testing.assert_array_equal(first,d['first'])

    def test_replay_rejects_changed_action_log(self):
        c=config();c['budgets']=[3.];r=run_job(c,next(jobs(c)))
        r['arms']['faa']['attack_log'][0][2]=1-r['arms']['faa']['attack_log'][0][2]
        with self.assertRaises(AssertionError):independent_replay(r,c)

if __name__=='__main__':unittest.main()
