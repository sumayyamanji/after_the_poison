"""Re-export Figures 5.5/5.6 from unchanged replay records; no new simulation."""
from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'legend.fontsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'pdf.fonttype':42,'savefig.dpi':300})
star=np.array([[.458,.620],[.458,.800],[.620,1.]])
checks=[]
for stem,start,count,title in [('ucb_state_access',2,1,'Delayed return to the targeted state'),('ucb_action_access',0,100,'State revisited, one action left unupdated')]:
 rows=list(csv.DictReader((ROOT/'data'/f'{stem}.csv').open())); arms={k:[x for x in rows if x['arm']==k] for k in ['clean','faa']}; a=arms['faa']; n=len(a)
 ell=max(int(x['step']) for x in a if float(x['delta'])!=0)
 q=np.empty((n+1,3,2));q[0]=star; counts=np.zeros((n+1,3,2),int)
 for i,x in enumerate(a,1):
  assert int(x['step'])==i
  s,ac=int(x['state']),int(x['action']);assert abs(q[i-1,s,ac]-float(x['q_before']))<1e-10
  q[i]=q[i-1];q[i,s,ac]=float(x['q_after']);counts[i]=counts[i-1];counts[i,s,ac]+=1
  assert abs(np.abs(q[i]-star).max()-float(x['sup_error_after']))<1e-10
 entry=np.unravel_index(np.argmax(abs(q[ell]-star)),star.shape);assert entry==(0,1)
 t=np.arange(ell,n+1);x=t-ell;err=abs(q[t]-star).max(axis=(1,2));u=counts[t,0,1]-counts[ell,0,1];e=abs(q[t,0,1]-star[0,1])
 rewards={k:np.array([float(v['reward']) for v in vls]) for k,vls in arms.items()};loss=np.cumsum(rewards['clean']-rewards['faa'])
 fig,axs=plt.subplots(2,2,figsize=(6.14,6.35),layout='constrained')
 fig.suptitle(title+f'\nUCB-style; start/reset S{start}; initial counts {count}; budget 3',fontsize=10)
 ax=axs[0,0];ax.plot(x,err);ax.axvline(500-ell,color='grey',ls=':',label='Attack period ends');ax.axhline(.05,color='#b22',ls=':',label='Tolerance 0.05');ax.set(title='(a) Largest Q-error',xlabel='Clean transitions since\nlast reward change',ylabel='Largest absolute error');ax.legend(loc='best')
 ax=axs[0,1];ax.plot(u,e);ax.scatter(u[[0,-1]],e[[0,-1]],s=12);ax.set(title='(b) Error in Q(S0, Right)',xlabel='Updates to (S0, Right)',ylabel='Absolute error')
 ax=axs[1,0]
 for s in range(3):ax.plot(x,(counts[t,s]-counts[ell,s]).sum(axis=1),label=f'S{s}')
 ax.set(title='(c) State visits',xlabel='Clean transitions since\nlast reward change',ylabel='Cumulative visits');ax.legend(loc='best')
 ax=axs[1,1];ax.plot(np.arange(1,n+1),loss,linewidth=.9);ax.axvline(ell,color='grey',ls=':',label='Last reward change');ax.axvline(500,color='#b22',ls=':',label='Attack period ends');ax.set(title='(d) Actual reward difference',xlabel='Transitions since\nattack period began',ylabel='Clean minus attacked reward');ax.legend(loc='best')
 for ax in axs.flat:ax.grid(alpha=.2)
 fig.savefig(ROOT/'figures'/f'{stem}.pdf');fig.savefig(ROOT/'figures'/f'{stem}_readable.png');plt.close(fig)
 checks.append({'figure':stem,'last_changed_reward':ell,'clean_followup':n-ell,'entry':list(map(int,entry)),'S0_updates':(counts[n,0]-counts[ell,0]).tolist(),'final_error':float(err[-1]),'combined_loss':float(loss[-1]),'series_source':'unchanged replay CSV; q_before and sup_error_after checked at every transition'})
(ROOT/'figures/reexport_checks.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks,indent=2))
