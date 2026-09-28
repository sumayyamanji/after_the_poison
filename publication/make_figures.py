from pathlib import Path
import csv,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'data'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':180})
colors={'epsilon_greedy':'#2166ac','softmax':'#d66000','ucb':'#278548'}
labels={'epsilon_greedy':'epsilon-greedy','softmax':'softmax','ucb':'UCB-style'}
rows=list(csv.DictReader((SRC/'COMBINED_CONDITIONS.csv').open()))
fig,axs=plt.subplots(1,2,figsize=(10,3.8),sharey=True,constrained_layout=True)
for ax,start in zip(axs,['S0','S2']):
 for rule in colors:
  rs=sorted([r for r in rows if r['start']==start and r['counts']=='1' and r['rule']==rule],key=lambda r:float(r['C']))
  x=[float(r['C']) for r in rs];n=[int(r['n']) for r in rs]
  ax.plot(x,[int(r['attained'])/nn for r,nn in zip(rs,n)],'o-',color=colors[rule],label=labels[rule]+': attained')
  ax.plot(x,[int(r['target_at_cutoff'])/nn for r,nn in zip(rs,n)],'s--',color=colors[rule],label=labels[rule]+': retained at 500')
 ax.set(title=f'Start {start}; initial counts 1',xlabel='Allocated budget C',ylim=(-.03,1.05),xticks=[1,3,10]);ax.grid(alpha=.18)
axs[0].set_ylabel('Fraction of runs');axs[1].legend(fontsize=7,loc='center right')
fig.savefig(ROOT/'figures/attainment_retention.png');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,3.8),sharey=True,constrained_layout=True)
for ax,start in zip(axs,['S0','S2']):
 rr=list(csv.DictReader((ROOT/f'data/{start}_runs.csv').open()))
 for rule in colors:
  r=[r for r in rr if 'counts1_' in r['design'] and r['C']=='3.0' and r['rule']==rule]
  t=np.array([float(x['q_time_from_last']) if x['q_time_from_last'] else np.inf for x in r]);xx=np.unique(np.r_[0,t[np.isfinite(t)&(t<=5000)],5000])
  ax.step(xx,[(t>v).mean() for v in xx],where='post',color=colors[rule],label=f'{labels[rule]} (n={len(r)})')
 ax.set(xscale='symlog',xlim=(0,5000),ylim=(-.02,1.04),title=f'Start {start}; C=3; initial counts 1',xlabel='Clean transitions after last poisoning');ax.grid(alpha=.18);ax.legend(fontsize=8)
axs[0].set_ylabel('Fraction not yet Q-recovered')
fig.savefig(ROOT/'figures/q_survival.png');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(10,4),sharey=False,constrained_layout=True)
for ax,start in zip(axs,['S0','S2']):
 for j,rule in enumerate(colors):
  r=next(r for r in rows if r['start']==start and r['counts']=='1' and r['rule']==rule and r['C']=='3.0')
  for k,key in enumerate(['attack_reward_loss','recovery_reward_loss','combined_reward_loss']):
   x=k+(j-1)*.2;y=float(r[key+'_mean']);lo=r[key+'_ci_low'];hi=r[key+'_ci_high']
   ax.scatter(x,y,color=colors[rule],label=labels[rule] if k==0 else None,zorder=3)
   if lo:ax.errorbar(x,y,yerr=[[max(0,y-float(lo))],[max(0,float(hi)-y)]],color=colors[rule],capsize=3)
 ax.axhline(0,color='grey',lw=.8);ax.set(title=f'Start {start}; C=3; initial counts 1',xticks=[0,1,2],xticklabels=['Attack window','Recovery window','Combined'],ylabel='Clean minus attacked reward');ax.grid(axis='y',alpha=.18);ax.legend(fontsize=8)
fig.savefig(ROOT/'figures/reward_loss.png');plt.close(fig)
print('Aggregate figures regenerated from bundled saved data; no new simulations.')
