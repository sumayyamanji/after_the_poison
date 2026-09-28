#!/usr/bin/env python3
"""Controlled terminal-task count sweep, Propositions 3--4.

Python >=3.10. Only plotting needs matplotlib. No qpoison imports.
Counts are POST-intervention. All logarithms are natural.
Threshold decisions use outward-rounded Decimal intervals, not float.
Full integer W and T are written as strings in JSON and exactly in CSV.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal as Dec, Context, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN, localcontext, Inexact
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

ALPHA, GAMMA, BETA, RHO = map(Dec, ('0.9', '0.9', '1', '0.05'))
BASE_COUNTS = [1, 3, 10, 30, 100, 300, 1000]
EXTRA_SMALL_GAP_COUNTS = [3000, 10000]
REGIMES = ['fixed_1', 'matched']
GAPS = ['0.1', '0.5']
ZERO, ONE = Dec(0), Dec(1)


class Intervals:
    """Enclosures built from directed arithmetic and widened sqrt/ln.

    Decimal ln/sqrt are correctly rounded; taking adjacent representable
    numbers encloses their real value. Subsequent arithmetic rounds outward.
    No float enters these comparisons. Dependency may widen an interval but
    cannot shrink it incorrectly. Unresolved comparisons increase precision.
    """
    def __init__(self, precision):
        self.near = Context(prec=precision, rounding=ROUND_HALF_EVEN)
        self.down = Context(prec=precision, rounding=ROUND_FLOOR)
        self.up = Context(prec=precision, rounding=ROUND_CEILING)

    @staticmethod
    def point(x):
        x = Dec(x)
        return x, x

    def sub(self, x, y):
        return self.down.subtract(x[0], y[1]), self.up.subtract(x[1], y[0])

    def mul(self, x, y):
        pairs = [(a, b) for a in x for b in y]
        return (min(self.down.multiply(a, b) for a, b in pairs),
                max(self.up.multiply(a, b) for a, b in pairs))

    def reciprocal_positive(self, x):
        assert x[0] > 0
        return self.down.divide(ONE, x[1]), self.up.divide(ONE, x[0])

    def sqrt(self, x):
        assert x[0] >= 0
        lo, hi = self.near.sqrt(x[0]), self.near.sqrt(x[1])
        return max(ZERO, self.near.next_minus(lo)), self.near.next_plus(hi)

    def ln(self, x):
        assert x[0] > 0
        lo, hi = self.near.ln(x[0]), self.near.ln(x[1])
        return self.near.next_minus(lo), self.near.next_plus(hi)


def score_difference_interval(na, nc, gap, precision):
    """UCB score(action 0) - score(action 1), where gap=Q1-Q0."""
    iv = Intervals(precision)
    common = iv.sqrt(iv.ln(iv.point(1 + na + nc)))
    left = iv.reciprocal_positive(iv.sqrt(iv.point(na)))
    right = iv.reciprocal_positive(iv.sqrt(iv.point(nc)))
    bonus_difference = iv.mul(iv.point(BETA), iv.mul(common, iv.sub(left, right)))
    return iv.sub(bonus_difference, iv.point(gap))


def choose_optimal(na, nc, gap, initial_precision=60, max_precision=4096):
    """Certified comparison; ties favour action 0. Fails rather than guessing."""
    if na == nc:
        # Equal bonuses cancel symbolically, avoiding an unresolved zero interval.
        d = -gap
        return d >= 0, initial_precision, (str(d), str(d))
    precision = max(initial_precision, len(str(na)), len(str(nc)))
    while precision <= max_precision:
        lo, hi = score_difference_interval(na, nc, gap, precision)
        if lo >= 0:
            return True, precision, (str(lo), str(hi))
        if hi < 0:
            return False, precision, (str(lo), str(hi))
        precision *= 2
    raise ArithmeticError('Threshold could not be resolved; increase max precision. No guessed result saved.')


def first_revisit(na, nc, gap, extra_precision=0):
    """Integer doubling + bisection, then certify the two adjacent boundaries.

    With positive gap, the predicate is false while nc+t <= na. Once nc+t
    exceeds na, both positive factors in f(t) increase, so the predicate
    is monotone. This justifies bisection even though f may start negative.
    """
    assert na > 0 and nc > 0 and gap > 0
    with localcontext() as ctx:
        ctx.prec = 50
        exponent = Dec(na) * gap * gap / (BETA * BETA)
        precision = max(60, int(exponent / Dec(10).ln()) + 45) + extra_precision
    evaluations, used = 0, precision

    def predicate(t):
        nonlocal evaluations, used
        result, digits, enclosure = choose_optimal(na, nc + t, gap, precision)
        evaluations += 1
        used = max(used, digits)
        return result, enclosure

    ok, right = predicate(0)
    if ok:
        return 1, dict(precision=used, evaluations=evaluations, left=None, right=right)
    low, high = 0, 1
    while not predicate(high)[0]:
        low, high = high, high * 2
    while high - low > 1:
        mid = (low + high) // 2
        if predicate(mid)[0]:
            high = mid
        else:
            low = mid
    left_ok, left = predicate(high - 1)
    right_ok, right = predicate(high)
    assert not left_ok and right_ok
    assert Dec(left[1]) < 0 and Dec(right[0]) >= 0
    return high + 1, dict(precision=used, evaluations=evaluations, left=left, right=right)


def recover_after_jump(na, nc, gap, W, precision):
    """Jump W-1 unchanged competitor updates, then follow ordinary Q updates.

    Elapsed times/counts stay Python integers even when W has 100+ digits.
    Terminal transitions always have zero bootstrap: gamma is not used.
    """
    counts = [na, nc + W - 1]
    values = [-gap, ZERO]
    elapsed = W - 1
    trace = []
    with localcontext() as ctx:
        ctx.prec = max(80, precision)
        ctx.traps[Inexact] = True  # These finite-decimal value updates must be exact.
        for step in range(10000):
            select0, _, bounds = choose_optimal(counts[0], counts[1], values[1] - values[0], precision)
            action = 0 if select0 else 1
            if step == 0:
                assert action == 0
            before = list(values)
            reward = ONE if action == 0 else ZERO
            values[action] = (ONE - ALPHA) * values[action] + ALPHA * reward
            counts[action] += 1
            elapsed += 1
            error = max(abs(values[0] - ONE), abs(values[1]))
            trace.append(dict(time=str(elapsed), action=action,
                              counts=[str(x) for x in counts],
                              q_before=[str(x) for x in before], q_after=[str(x) for x in values],
                              sup_error=str(error), score_difference_bounds=bounds))
            # Match the dissertation's <= convention; no exact rho tie in this grid.
            if error <= RHO:
                return elapsed, trace
    raise RuntimeError('Post-revisit simulation exceeded its guard. No censored time is treated as recovery.')


def brute_force_float(na, nc, gap, limit):
    """Independent small-case simulation from time 0: no threshold or jump calls.

    Float is used only for this cross-check, never to certify large W.
    """
    values, counts = [-float(gap), 0.0], [na, nc]
    first = None
    smallest_margin = math.inf
    for t in range(1, limit + 1):
        logn = math.log1p(sum(counts))
        scores = [values[i] + float(BETA) * math.sqrt(logn / counts[i]) for i in (0, 1)]
        smallest_margin = min(smallest_margin, abs(scores[0] - scores[1]))
        action = 0 if scores[0] >= scores[1] else 1
        if action == 0 and first is None:
            first = t
        values[action] = 0.1 * values[action] + 0.9 * (1.0 if action == 0 else 0.0)
        counts[action] += 1
        if max(abs(values[0] - 1), abs(values[1])) <= float(RHO):
            return first, t, smallest_margin
    return first, None, smallest_margin


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def dec_log(value):
    with localcontext() as ctx:
        ctx.prec = 50
        return Dec(value).ln()


def calculate(na, regime, gap_string, check_limit):
    gap = Dec(gap_string)
    nc = 1 if regime == 'fixed_1' else na
    W, cert = first_revisit(na, nc, gap)
    T, trace = recover_after_jump(na, nc, gap, W, cert['precision'])
    if T <= check_limit:
        bw, bt, margin = brute_force_float(na, nc, gap, check_limit)
        assert (bw, bt) == (W, T), (na, regime, gap_string, W, T, bw, bt)
        crosscheck = dict(status='passed', first_revisit=bw, q_recovery=bt, minimum_float_score_margin=margin)
    else:
        crosscheck = dict(status='not_run_above_limit', limit=check_limit)
    with localcontext() as ctx:
        ctx.prec = 50
        predicted = Dec(na) * gap ** 2 / BETA ** 2
        logw, logt = dec_log(W), dec_log(T)
        ratio = logw / predicted
        cost = (ONE + gap) / ALPHA
    return dict(n_a=na, n_c=nc, regime=regime, D=gap_string,
                range='requested' if na in BASE_COUNTS else 'small_gap_extension',
                W=str(W), T_rho=str(T), T_minus_W=str(T-W),
                predicted_log_W=str(predicted), observed_log_W=str(logw), log_T_rho=str(logt),
                asymptotic_ratio=str(ratio), ratio_error=str(ratio-ONE),
                intervention_cost=str(cost), boundary_certificate=cert,
                post_revisit_trace=trace, independent_simulation=crosscheck)


def add_slopes(rows):
    for regime in REGIMES:
        for gap in GAPS:
            group = sorted([r for r in rows if r['regime'] == regime and r['D'] == gap], key=lambda r:r['n_a'])
            previous = None
            for r in group:
                r.update(adjacent_slope='', predicted_slope=str(Dec(gap)**2 / BETA**2),
                         slope_error='', relative_slope_error='', slope_from_n_a='')
                if previous:
                    with localcontext() as ctx:
                        ctx.prec = 50
                        slope = (Dec(r['observed_log_W'])-Dec(previous['observed_log_W'])) / (r['n_a']-previous['n_a'])
                        target = Dec(r['predicted_slope'])
                        r.update(adjacent_slope=str(slope), slope_error=str(slope-target),
                                 relative_slope_error=str(slope/target-ONE), slope_from_n_a=previous['n_a'])
                previous = r


def plot_results(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10, 'savefig.dpi':200, 'pdf.fonttype':42})
    colors = {'0.1':'#1764a0', '0.5':'#d95c02'}
    markers = {'fixed_1':'o', 'matched':'s'}
    labels = {'fixed_1':r'$n_c=1$', 'matched':r'$n_c=n_a$'}

    def panel_figure(subset, filename, title):
        fig, axs = plt.subplots(1,2,figsize=(12,4.7), constrained_layout=True)
        for ax, field, panel in zip(axs, ['observed_log_W','log_T_rho'], ['(a)', '(b)']):
            for gap in GAPS:
                for regime in REGIMES:
                    rr=sorted([r for r in subset if r['D']==gap and r['regime']==regime],key=lambda r:r['n_a'])
                    if not rr:continue
                    ax.plot([r['n_a'] for r in rr],[float(r[field]) for r in rr],
                            color=colors[gap],marker=markers[regime],ms=4,
                            ls='-' if regime=='fixed_1' else ':',lw=1.4,
                            markerfacecolor=colors[gap] if regime=='fixed_1' else 'white',
                            label=f'D={gap}, '+labels[regime])
            if field=='observed_log_W':
                for gap in sorted({r['D'] for r in subset}):
                    maximum=max(r['n_a'] for r in subset if r['D']==gap)
                    ax.plot([0,maximum],[0,maximum*float(gap)**2],ls='--',color=colors[gap],alpha=.65,
                            label=f'Leading term: {float(gap)**2:g} n'+r'$_a$')
            ax.set_xlabel(r'Post-attack count $n_a$')
            ax.set_ylabel(r'$\log W$' if field=='observed_log_W' else r'$\log T_\rho$')
            ax.set_title(panel+' '+('First revisit' if field=='observed_log_W' else 'Whole-table Q recovery'))
            ax.grid(alpha=.2)
        axs[0].legend(fontsize=7.5,loc='upper left')
        axs[1].legend(fontsize=8,loc='upper left')
        fig.suptitle(title,fontsize=11)
        for ext in ['png','pdf']:fig.savefig(out/f'{filename}.{ext}')
        plt.close(fig)

    panel_figure([r for r in rows if r['range']=='requested'],'count_scaling',
                 'Terminal UCB count sweep; alpha=0.9, beta=1, rho=0.05; natural logarithms')
    if any(r['range']!='requested' for r in rows):
        panel_figure([r for r in rows if r['D']=='0.1'],'small_gap_extended',
                     'Small-gap extension (D=0.1): larger counts clarify the asymptotic regime')
    fig,axs=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    for ax,gap in zip(axs,GAPS):
        for regime in REGIMES:
            rr=sorted([r for r in rows if r['D']==gap and r['regime']==regime],key=lambda r:r['n_a'])
            ax.plot([r['n_a'] for r in rr],[float(r['asymptotic_ratio']) for r in rr],
                    marker=markers[regime],label=labels[regime])
        ax.axhline(1,color='black',ls='--',lw=1,label='Asymptotic limit 1')
        ax.set(xscale='log',yscale='log',xlabel=r'$n_a$',ylabel=r'$\log W/(n_a D^2/\beta^2)$',title=f'D={gap}')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    for ext in ['png','pdf']:fig.savefig(out/f'asymptotic_ratio.{ext}')
    plt.close(fig)


def write_reports(rows, out, metadata):
    fields=['n_a','n_c','regime','D','range','W','T_rho','T_minus_W','predicted_log_W','observed_log_W',
            'log_T_rho','asymptotic_ratio','ratio_error','slope_from_n_a','predicted_slope','adjacent_slope',
            'slope_error','relative_slope_error','intervention_cost']
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    def fmt(x):return f'{float(x):.8g}'
    lines=['# UCB count-scaling results','',
           'All counts are post-attack. Q starts at (-D, 0), with true values (1, 0).',
           'Every event time is finite and computed, not censored. W and T in the CSV are full integers.',
           'Large values printed below use scientific notation for readability; W and T may look equal after rounding although T-W=1.',
           'Initial tables and counts are prescribed; this sweep does not measure whether on-policy FAA can create every configuration.', '',
           '| n_a | n_c regime | D | W | T_rho | predicted log W | computed log W | ratio | adjacent slope | slope error |',
           '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        display=lambda v: v if len(v)<14 else f'{Dec(v):.7E}'
        lines.append('| '+' | '.join([str(r['n_a']),r['regime'],r['D'],display(r['W']),display(r['T_rho']),
                                      fmt(r['predicted_log_W']),fmt(r['observed_log_W']),fmt(r['asymptotic_ratio']),
                                      fmt(r['adjacent_slope']) if r['adjacent_slope'] else '—',
                                      fmt(r['slope_error']) if r['slope_error'] else '—'])+' |')
    checks=sum(r['independent_simulation']['status']=='passed' for r in rows)
    differences=sorted({int(r['T_minus_W']) for r in rows})
    lines += ['',f'Independent step-by-step checks passed in {checks}/{len(rows)} conditions; others exceed the declared check limit.',
              f'Every integer boundary was certified. Observed T_rho - W values: {differences}.',
              '', '## How to read the comparison',
              'The proposition predicts the ratio tends to 1. It does not assert a straight line at small counts.',
              '`adjacent_slope` uses this count and the preceding tested count within the same gap/regime.',
              '`slope_error` = adjacent_slope - D^2/beta^2; `ratio_error` = log(W)/(n_a D^2/beta^2) - 1.',
              'The first row of each series has no adjacent slope. This is a deterministic numerical study, not a statistical test.',
              '', '## Figures',
              '[Requested-range scaling](count_scaling.png) · [Vector PDF](count_scaling.pdf)',
              '[Asymptotic ratios](asymptotic_ratio.png) · [Vector PDF](asymptotic_ratio.pdf)']
    if any(r['range']!='requested' for r in rows):
        lines += ['[Small-gap extended range](small_gap_extended.png) · [Vector PDF](small_gap_extended.pdf)']
    lines += ['', 'No confidence intervals are appropriate: there is no seed randomness in this design.',
              'The full recovery simulation uses the exact counts after the skipped constant-value waiting period.',
              'Gamma=0.9 is recorded for consistency but terminal updates have zero bootstrap.',
              '',f"Numerical computation and verification time: {metadata['elapsed_seconds']:.2f} seconds (machine-dependent; excludes plotting)."]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # These paragraphs are generated from the actual results, not assumed in advance.
    lookup={(r['D'],r['regime'],r['n_a']):r for r in rows}
    def pair(gap,n,field):return ' and '.join(f"{float(lookup[(gap,regime,n)][field]):.8g}" for regime in REGIMES)
    method=(f'To examine the quantitative count dependence in Proposition 4, we used the two-action terminal task '
            f'with rewards (1, 0), learning rate 0.9, UCB coefficient 1 and Q-error tolerance 0.05. '
            f'We directly prescribed the post-attack table (-D, 0), rather than generating it through a natural FAA trajectory, used gaps D=0.1 and D=0.5, and varied the post-attack '
            f'count of the demoted action over 1, 3, 10, 30, 100, 300 and 1000. The competitor count was either '
            f'fixed at 1 or matched to the demoted action. '
            + ('For D=0.1, we additionally tested counts 3000 and 10000. ' if ('0.1','fixed_1',10000) in lookup else '')+
            f'We evaluated the exact first-revisit condition using integer bracketing and bisection, with outward-rounded '
            f'arbitrary-precision interval comparisons certifying the adjacent integer boundaries. We then advanced '
            f'the unchanged competitor selections in one jump and simulated subsequent clean updates to Q recovery. '
            f'An independent ordinary step-by-step implementation agreed on both event times in all {checks} conditions '
            f'within the {metadata["check_limit"]}-step verification limit. This is a deterministic numerical examination '
            f'of the exact condition, supplemented by implementation checks; it is not independent statistical evidence for the theorem.')
    results=(f'The computed curves approach the leading prediction log(W)=n_a D^2, but the approximation is not accurate '
             f'uniformly across the tested counts. For D=0.5, the adjacent slopes from n_a=300 to 1000 were '
             f'{pair("0.5",1000,"adjacent_slope")}, compared with the predicted slope 0.25 '
             f'(fixed and matched competitor counts, respectively). For D=0.1, the corresponding slopes were '
             f'{pair("0.1",1000,"adjacent_slope")}, compared with 0.01, and the ratios log(W)/(n_a D^2) '
             f'at n_a=1000 were {pair("0.1",1000,"asymptotic_ratio")}. ')
    if ('0.1','fixed_1',10000) in lookup:
        results+=(f'Extending this gap to n_a=10000 gave ratios {pair("0.1",10000,"asymptotic_ratio")} (to eight significant figures) '
                  f'and adjacent slopes over 3000--10000 of {pair("0.1",10000,"adjacent_slope")}. ')
    results+=('These finite-range calculations support the asymptotic prediction while showing appreciable corrections at smaller counts; '
              'they do not establish its limit by experiment. ')
    if differences==[1]:
        results+=('In every tested condition, the second corrective visit occurred immediately after the first, so T_rho=W+1. '
                  'Consequently, the two logarithmic recovery curves nearly coincide at large counts; this is a property of these parameters, '
                  'not a general first-revisit/recovery equivalence.')
    else:
        results+=f'The observed differences T_rho-W were {differences}; full recovery must therefore be distinguished from first revisit.'
    (out/'SECTION_5_2_INSERT.md').write_text(method+'\n\n'+results+'\n',encoding='utf-8')
    def latex(s):
        import re
        mapping = {
            'log(W)/(n_a D^2)': r'$\log W/(n_aD^2)$',
            'log(W)=n_a D^2': r'$\log W=n_aD^2$',
            'T_rho=W+1': r'$T_\rho=W+1$',
            '(-D, 0)': r'$(-D,0)$',
            'n_a': r'$n_a$', 'T_rho': r'$T_\rho$',
            'D=0.1': r'$D=0.1$', 'D=0.5': r'$D=0.5$',
        }
        pattern = '|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True))
        return re.sub(pattern, lambda m:mapping[m.group()], s)

    (out/'SECTION_5_2_INSERT.tex').write_text('% Insert near the end of terminal-task validation, Section 5.2.\n'+latex(method)+'\n\n'+latex(results)+'\n',encoding='utf-8')
    print('\n'.join(lines[:len(rows)+9]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results'/'ucb_count_sweep')
    parser.add_argument('--base-only',action='store_true',help='Omit the extra D=0.1 counts 3000 and 10000.')
    parser.add_argument('--check-limit',type=int,default=100000,help='Independent simulation limit; 0 skips these checks.')
    parser.add_argument('--resume',action='store_true',help='Reuse matching per-condition checkpoints from this exact script version.')
    parser.add_argument('--no-plots',action='store_true',help='Use only the Python standard library; skip matplotlib outputs.')
    args=parser.parse_args()
    if args.check_limit<0:parser.error('--check-limit must be nonnegative')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    records=out/'records';records.mkdir(exist_ok=True)
    code_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    settings=dict(alpha=str(ALPHA),gamma=str(GAMMA),beta=str(BETA),rho=str(RHO),true_rewards=['1','0'],
                  counts_are='post_attack',base_only=args.base_only,check_limit=args.check_limit,
                  code_sha256=code_hash)
    started=time.perf_counter();rows=[]
    for gap in GAPS:
        counts=BASE_COUNTS + (EXTRA_SMALL_GAP_COUNTS if gap=='0.1' and not args.base_only else [])
        for regime in REGIMES:
            for na in counts:
                checkpoint=records/f'D{gap.replace(".","p")}_{regime}_n{na}.json'
                saved=json.loads(checkpoint.read_text()) if args.resume and checkpoint.exists() else None
                if saved and saved.get('settings')==settings:
                    result=saved['result'];status='resumed'
                else:
                    result=calculate(na,regime,gap,args.check_limit)
                    atomic_json(checkpoint,dict(settings=settings,result=result));status='computed'
                rows.append(result)
                print(f'{status}: D={gap}, {regime}, n_a={na}; W has {len(result["W"])} digits; T-W={result["T_minus_W"]}',flush=True)
    add_slopes(rows)
    metadata=dict(settings,python=sys.version,platform=platform.platform(),conditions=len(rows),
                  elapsed_seconds=time.perf_counter()-started,check_limit=args.check_limit,
                  numerical_method='directed Decimal intervals; adjacent integer boundary certificates',
                  no_censoring=True,plots_requested=not args.no_plots)
    atomic_json(out/'metadata.json',metadata)
    write_reports(rows,out,metadata)
    if not args.no_plots:
        plot_results(rows,out)
    print(f'\nSaved results to {out}')


if __name__=='__main__':
    main()
