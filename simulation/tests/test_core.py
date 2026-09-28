import tempfile
import unittest
from pathlib import Path
import numpy as np

from qpoison.mdp import build_mdp, build_targets
from qpoison.learner import QLearner
from qpoison.faa import Budget, FAA, greedy_perturbation, margins
from qpoison.experiment import run_one
from qpoison.analysis import wilson


class CoreTests(unittest.TestCase):
    def learner(self, rule="epsilon_greedy", **kwargs):
        return QLearner(2, 2, {"rule": rule, "alpha": .5, **kwargs}, .9)

    def test_update_terminal_and_bootstrap(self):
        q = self.learner()
        q.q[:] = [[2, 0], [3, 4]]
        q.update(0, 0, 1, 1, False, delta=.2)
        self.assertAlmostEqual(q.q[0, 0], .5*2+.5*(1+.2+.9*4))
        self.assertEqual(q.counts[0, 0], 1)
        before = q.q[0, 0]
        q.update(0, 0, 1, -1, True)
        self.assertAlmostEqual(q.q[0, 0], .5*before+.5)

    def test_action_probabilities_and_ucb_counts(self):
        eps = self.learner(epsilon=.2)
        eps.q[0] = [0, 1]
        np.testing.assert_allclose(eps.probabilities(0), [.1,.9])
        soft = self.learner("softmax", temperature=.5)
        soft.q[0] = [1000, 1001]
        p = soft.probabilities(0)
        self.assertAlmostEqual(p[1]/p[0], np.exp(2))
        ucb = self.learner("ucb", beta=1)
        self.assertEqual(ucb.probabilities(0).argmax(), 0)
        ucb.counts[0, 0] = 100
        self.assertEqual(ucb.probabilities(0).argmax(), 1)
        ucb.counts[0, 1] = 1
        self.assertEqual(ucb.probabilities(0).argmax(), 1)

    def test_per_pair_schedule(self):
        learner = self.learner(alpha_schedule="per_visit", omega=.75)
        self.assertEqual(learner.learning_rate(0,0), 1)
        learner.counts[0,0] = 15
        self.assertAlmostEqual(learner.learning_rate(0,0), 16**(-.75))
        self.assertEqual(learner.learning_rate(1,0), 1)

    def test_budget_both_constraints_and_exhaustion(self):
        budget = Budget(.3, .5)
        first = budget.apply(10, "teaching", 0)
        second = budget.apply(-10, "teaching", 0)
        third = budget.apply(10, "teaching", 0)
        self.assertAlmostEqual(first.delta, .3)
        self.assertAlmostEqual(second.delta, -.2)
        self.assertEqual(third.delta, 0)
        self.assertTrue(first.capped_by_delta)
        self.assertTrue(second.capped_by_budget)
        self.assertAlmostEqual(budget.spent, .5)

    def test_faa_corrected_margin_and_printed_failure(self):
        row = np.array([0., 1.])
        desired = np.array([True, False])
        correction = greedy_perturbation(row, 1, desired, 1., .5, .1)
        self.assertAlmostEqual(1+.5*correction, -.1)
        printed = greedy_perturbation(row, 1, desired, 1., .5, .1, "paper_printed")
        self.assertAlmostEqual(1+.5*printed, .1)
        promotion = greedy_perturbation(row, 0, desired, 0., .5, .1)
        self.assertAlmostEqual(.5*promotion, 1.1)

    def test_value_and_navigation_models(self):
        env = build_mdp({"kind":"chain", "n_states":3})
        q = env.optimal_q(.9)
        np.testing.assert_array_equal(q.argmax(axis=1), [1,1,1])
        self.assertAlmostEqual(q[-1,1], 1)
        nav, distance = env.navigation_policy(0,.1)
        np.testing.assert_array_equal(nav[1:], [0,0])
        self.assertGreater(distance[env.start], 0)
        np.testing.assert_allclose(env.navigation_P.sum(axis=2), 1)
        for goal in range(env.n_states):
            nav, distance = env.navigation_policy(goal, .1)
            expected = 1 + .9*env.navigation_P[np.arange(env.n_states),nav]@distance + .1*env.navigation_P.mean(axis=1)@distance
            keep = np.arange(env.n_states) != goal
            np.testing.assert_allclose(distance[keep], expected[keep], atol=1e-8)

    def test_stochastic_model_matches_sampling(self):
        env = build_mdp({"kind":"chain", "n_states":2, "slip":.4})
        rng = np.random.default_rng(123)
        draws = [env.step(1,1,rng) for _ in range(20000)]
        self.assertAlmostEqual(np.mean([x[2] for x in draws]), .8, delta=.015)

    def test_pathwise_shadow_bound(self):
        rng = np.random.default_rng(10)
        env = build_mdp({"kind":"chain", "n_states":4,"slip":.3})
        for rule in ["epsilon_greedy", "softmax", "ucb"]:
            learner = QLearner(4,2,{"rule":rule,"alpha":.4},.9)
            shadow = QLearner(4,2,{"rule":rule,"alpha":.4},.9)
            state, expenditure = env.start, 0.
            for _ in range(200):
                action = learner.select(state,rng)
                successor,reward,done = env.step(state,action,rng)
                delta = rng.uniform(-.2,.2)
                expenditure += abs(delta)
                learner.update(state,action,reward,successor,done,delta)
                shadow.update(state,action,reward,successor,done)
                difference = np.max(np.abs(learner.q-shadow.q))
                self.assertLessEqual(difference, min(.2/(1-.9),.4*expenditure)+1e-10)
                state = env.start if done else successor

    def test_clean_sweep_contraction(self):
        env = build_mdp({"kind":"chain","n_states":4})
        qstar = env.optimal_q(.9)
        learner = QLearner(4,2,{"rule":"epsilon_greedy","alpha":.4},.9,qstar+3)
        rng=np.random.default_rng(0)
        for _ in range(5):
            error=np.max(np.abs(learner.q-qstar))
            for s,a in rng.permutation([(s,a) for s in range(4) for a in range(2)]):
                successor,reward,done=env.step(s,a,rng)
                learner.update(s,a,reward,successor,done)
            self.assertLessEqual(np.max(np.abs(learner.q-qstar)), (1-.4*(1-.9))*error+1e-10)

    def test_exact_single_state_teaching_budget(self):
        env=build_mdp({"kind":"one_state","rewards":[1,0]})
        targets=build_targets(env,"suboptimal_action")
        for action in [0,1]:
            learner=QLearner(1,2,{"rule":"ucb","alpha":.5},.9,env.optimal_q(.9))
            faa=FAA(env,targets,{"eta":.1},10,10)
            decision=faa.decide(learner,0,action,env.R[0,action],-1,True)
            self.assertAlmostEqual(abs(decision.delta), (1+.1)/.5)
            learner.update(0,action,env.R[0,action],-1,True,decision.delta)
            self.assertGreaterEqual(margins(learner.q,targets)[0],.1-1e-10)

    def test_runner_reproducibility_and_censoring(self):
        config={"experiment":"controlled_recovery","gamma":.9,"post_steps":8,
                "log_every":1,"eval_every":4,"q_tolerance":.01,"recovery_window":3}
        job={"scenario":{"name":"test","environment":{"kind":"one_state"},
                         "targets":"suboptimal_action","initialization":{"distortion":2,"counts":[100,100]}},
             "learner":{"name":"ucb","rule":"ucb","alpha":.9,"beta":.1},
             "seed":3,"attack":"controlled_initialization","delta":None,"budget":None}
        with tempfile.TemporaryDirectory() as directory:
            first=run_one(config,job,Path(directory)/"a")
            second=run_one(config,job,Path(directory)/"b")
            self.assertEqual(first,second)
            self.assertTrue(first["recovery_censored"])
            self.assertIsNone(first["recovery_confirmation_steps"])
            self.assertEqual(first["recovery_time_capped"],8)

    def test_wilson_retains_uncertainty_at_extremes(self):
        lo,hi=wilson(0,10)
        self.assertAlmostEqual(lo,0)
        self.assertGreater(hi,0)
        lo,hi=wilson(10,10)
        self.assertLess(lo,1)
        self.assertAlmostEqual(hi,1)


if __name__ == "__main__":
    unittest.main()
