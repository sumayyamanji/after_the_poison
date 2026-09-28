#!/usr/bin/env python3
"""Draw the environment schematic and terminal theory/observation overlay.

Run from any directory: python tools/make_missing_figures.py
Requires numpy and matplotlib. No experiments are run or raw records changed.
Theory is evaluated from the stated terminal equations and checked against the
saved theory columns. Observations are plotted only at their saved checkpoints.
"""
from pathlib import Path
import csv
import json
import hashlib
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.path import Path as MPath
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'figures'
OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':11,
                     'axes.labelsize':10.5,'xtick.labelsize':9,'ytick.labelsize':9,
                     'pdf.fonttype':42,'ps.fonttype':42,'savefig.facecolor':'white'})
INK='#243346'; BLUE='#0072B2'; ORANGE='#D55E00'; GREEN='#008763'; PURPLE='#7954A1'

def save(fig,stem):
    for ext in ('pdf','png'):
        fig.savefig(OUT/f'{stem}.{ext}',dpi=240,bbox_inches='tight',pad_inches=.10)
    plt.close(fig)

def box(ax,x,y,w,h,label,fill='#EFF3F7',edge=INK,fontsize=11):
    ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=.025,rounding_size=.10',
                              facecolor=fill,edgecolor=edge,linewidth=1.2,zorder=3))
    ax.text(x,y,label,ha='center',va='center',fontsize=fontsize,color=INK,zorder=4)

def arrow(ax,start,end,color=INK,rad=0,style='-',lw=1.5):
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=12,
                                connectionstyle=f'arc3,rad={rad}',color=color,
                                linewidth=lw,linestyle=style,zorder=2))

def environment():
    fig=plt.figure(figsize=(8.6,7.3))
    gs=fig.add_gridspec(3,1,height_ratios=[2.4,1.2,2.5],hspace=.23)
    a,b,c=[fig.add_subplot(gs[i]) for i in range(3)]
    for ax in (a,b,c):ax.set_xlim(0,10);ax.axis('off')
    a.set_ylim(0,3.2);b.set_ylim(0,1.65);c.set_ylim(0,3.3)
    a.text(0,3.1,'(a) The chain and the attacker\'s target',fontweight='bold',color=INK)
    xs=[1.15,3.70,6.25,8.80];y=1.93;w=1.06;h=.67
    for i,x in enumerate(xs):box(a,x,y,w,h,['S0','S1','S2','Goal'][i],fill='#E5F3EA' if i==3 else '#EFF3F7')
    for i in range(3):
        l,r=xs[i]+w/2+.06,xs[i+1]-w/2-.06
        arrow(a,(l,y+.15),(r,y+.15),BLUE,rad=-.32)
        a.text((l+r)/2,2.57,'Right / '+('+1' if i==2 else '−0.1'),ha='center',fontsize=10,color=BLUE)
    for i in (1,2):
        l,r=xs[i-1]+w/2+.06,xs[i]-w/2-.06
        arrow(a,(r,y-.15),(l,y-.15),ORANGE,rad=-.32)
        a.text((l+r)/2,1.30,'Left / −0.1',ha='center',fontsize=10,color=ORANGE)
    # S0 self-loop stays separate from the S1 -> S0 edge.
    verts=[(.75,1.59),(.15,.87),(1.80,.87),(1.53,1.58)]
    path=MPath(verts,[MPath.MOVETO,MPath.CURVE4,MPath.CURVE4,MPath.CURVE4])
    a.add_patch(FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=12,color=ORANGE,lw=1.5))
    a.text(1.00,.78,'Left: stay at S0 / −0.1',ha='center',fontsize=9.5,color=ORANGE)
    a.text(8.80,1.22,'Episode ends',ha='center',fontsize=10,color=GREEN)
    a.text(.12,.10,r"Attacker's target: $Q(\mathrm{S0},\mathrm{Left})>Q(\mathrm{S0},\mathrm{Right})$",
           color=PURPLE,fontsize=11)
    b.text(0,1.57,'(b) Two alternative reset rules',fontweight='bold',color=INK)
    for off,dest,title in [(0,'S0','Start at the targeted state'),(5.20,'S2','Start near the goal')]:
        b.text(off+.10,1.14,title,fontsize=10,color=INK)
        box(b,off+.72,.56,1.0,.57,'Goal',fill='#E5F3EA',fontsize=10)
        box(b,off+3.75,.56,1.0,.57,dest,fontsize=10)
        arrow(b,(off+1.31,.56),(off+3.16,.56),PURPLE,style='--')
        b.text(off+2.23,.76,'New episode',ha='center',fontsize=9.5,color=PURPLE)
    b.text(.10,-.04,'A reset starts a new episode; it adds no future-value term to the terminal update.',fontsize=9.3,color=INK)
    c.text(0,3.12,'(c) Allowed attack period and measurement clocks',fontweight='bold',color=INK)
    x0,xc,xe=.18,4.45,9.80;yl,yh=1.57,2.35;last=2.95
    c.add_patch(Rectangle((x0,yl),xc-x0,yh-yl,facecolor='#E4EFF8',edgecolor=BLUE,lw=1.2))
    c.add_patch(Rectangle((xc,yl),xe-xc,yh-yl,facecolor='#E5F3EA',edgecolor=GREEN,lw=1.2))
    c.text((x0+xc)/2,2.02,'Reward changes allowed',ha='center',va='center',fontsize=10.5,color=INK)
    c.text((xc+xe)/2,2.02,'Only unmodified rewards',ha='center',va='center',fontsize=10.5,color=INK)
    c.text((x0+xc)/2,1.77,'500 steps',ha='center',va='center',fontsize=10,color=INK)
    c.text((xc+xe)/2,1.77,'5,000 further steps',ha='center',va='center',fontsize=10,color=INK)
    for x,label in [(x0,'0'),(xc,'500'),(xe,'5,500')]:
        c.plot([x,x],[yl-.08,yl],color=INK,lw=1)
        c.text(x,yl-.13,label,ha='center',va='top',fontsize=10,color=INK)
    c.text(9.8,1.08,'Environment step',ha='right',fontsize=9.5,color=INK)
    c.plot([last,last],[2.64,2.36],color=PURPLE,lw=1.5)
    c.scatter([last],[2.36],color=PURPLE,marker='v',s=28,zorder=4)
    c.text(last,2.70,'Example last reward change',ha='center',fontsize=10,color=PURPLE)
    c.annotate('Recovery times start just after this update.',xy=(last,yl),xytext=(.15,.64),
               fontsize=10,color=PURPLE,arrowprops={'arrowstyle':'->','color':PURPLE,'lw':1.1},
               ha='left',va='center')
    c.text(.15,.09,'Schematic timing, not to scale. The last change can precede step 500 without exhausting the budget.',
           fontsize=9.3,color=INK)
    save(fig,'chain_reset_timeline')

def readcsv(name):
    with (ROOT/'data'/name).open(newline='') as f:return list(csv.DictReader(f))

def stochastic_survival(rule,D,H):
    # g=1, alpha=.9, epsilon=.1, tau=.2, rho=.05. Both gaps need two repairs.
    if rule=='epsilon_greedy':p0,p1=.05,.95
    else:p0,p1=1/(1+math.exp(D/.2)),1/(1+math.exp((.1*(1+D)-1)/.2))
    state=np.array([1.,0.,0.]);surv=np.empty(H+1);surv[0]=1.
    for t in range(1,H+1):
        state=np.array([state[0]*(1-p0),state[1]*(1-p1)+state[0]*p0,state[2]+state[1]*p1])
        surv[t]=max(0.,1-state[2])
    first=(1-p0)**np.arange(H+1)
    confirm=np.ones(H+1);confirm[19:]=surv[:H+1-19]
    return {'first_revisit':first,'q_confirmation':confirm}, {'first_revisit':1/p0,'q_confirmation':1/p0+1/p1+19}

def terminal():
    summaries=readcsv('terminal_summary.csv');values=readcsv('terminal_survival.csv')
    meta={(float(x['eta']),x['rule'],x['metric']):x for x in summaries
          if x['branch']=='demotion' and x['arm']=='faa' and x['metric'] in ('first_revisit','q_confirmation')}
    grouped={}
    for x in values:
        if x['branch']=='demotion' and x['arm']=='faa':
            grouped.setdefault((x['condition_id'],x['metric']),[]).append(x)
    H=2000;t=np.arange(H+1);checks=[]
    fig,axs=plt.subplots(2,2,figsize=(8.6,6.7),sharex=True,sharey=True)
    fig.subplots_adjust(left=.09,right=.98,bottom=.14,top=.86,hspace=.30,wspace=.13)
    colors={'epsilon_greedy':BLUE,'softmax':ORANGE,'ucb':GREEN}
    markers={'epsilon_greedy':'o','softmax':'s','ucb':'D'}
    metrics=['first_revisit','q_confirmation']
    for row,D in enumerate([.01,1.]):
        stochastic={rule:stochastic_survival(rule,D,H) for rule in ['epsilon_greedy','softmax']}
        # Exact UCB score condition before first revisit, post-attack counts (101,100).
        f=np.sqrt(np.log(1+201+t))*(1/np.sqrt(101)-1/np.sqrt(100+t))
        crossed=np.flatnonzero(f>=D)
        W=int(crossed[0]+1) if crossed.size else None
        if W is not None:
            assert W==12
            # At W the optimal value becomes .9-.1D. Confirm next choice from exact scores.
            q=np.array([.9-.1*D,0.]);counts=np.array([102,100+W-1])
            scores=q+np.sqrt(np.log(1+counts.sum())/counts)
            assert np.argmax(scores)==0
            assert .01*(1+D)<=.05 < .1*(1+D)
        for col,metric in enumerate(metrics):
            ax=axs[row,col]
            for rule in ['epsilon_greedy','softmax','ucb']:
                m=meta[(D,rule,metric)];r=sorted(grouped[(m['condition_id'],metric)],key=lambda x:int(x['t']))
                ts=np.array([int(x['t']) for x in r]);ys=np.array([float(x['survival']) for x in r])
                assert int(m['horizon'])==H and len(ts)==201 and np.all(np.diff(ts)==10)
                if rule=='ucb':
                    event=W if metric=='first_revisit' else (W+20 if W else None)
                    exact=(t<event).astype(float) if event is not None else np.ones(H+1)
                    if event:
                        assert float(m['observed_mean_if_no_censoring'])==event
                        assert int(m['recovered'])==1
                    else:assert int(m['censored'])==1
                    mean=float(event) if event is not None else None
                else:
                    exact=stochastic[rule][0][metric];mean=stochastic[rule][1][metric]
                    assert abs(mean-float(m['theory_full_mean']))<1e-10
                    assert int(m['n'])==300
                saved_theory=np.array([float(x['theory_survival']) for x in r])
                err=float(np.max(np.abs(exact[ts]-saved_theory)))
                assert err<2e-12,(D,rule,metric,err)
                ax.step(t,exact,where='post',color=colors[rule],lw=1.65,zorder=2)
                # Thin only display markers, always retaining saved (not interpolated) observations.
                mask=(ts<=200)|((ts<=500)&(ts%50==0))|(ts%100==0)
                if rule=='ucb':mask=np.isin(ts,[0,10,20,30,50,100,500,1000,2000])
                zeros=np.flatnonzero(ys==0)
                if zeros.size:mask &= (ts<=ts[zeros[0]]) | (ts==H)
                ax.plot(ts[mask],ys[mask],linestyle='none',marker=markers[rule],markersize=3.6,
                        markerfacecolor='white',markeredgewidth=.85,color=colors[rule],zorder=3,alpha=.90)
                checks.append({'condition_id':m['condition_id'],'D':D,'rule':rule,'metric':metric,
                               'n':int(m['n']),'computed_mean':mean,'saved_theory_max_abs_error':err,
                               'observations_every_steps':10,'censored':int(m['censored'])})
            name='First revisit' if col==0 else 'Confirmed Q recovery'
            ax.set_title(f'({chr(97+row*2+col)}) {name}; gap D = {D:g}',loc='left',pad=9)
            ax.set_xscale('symlog',linthresh=20,linscale=.8)
            ax.set_xlim(0,H);ax.set_ylim(-.03,1.06)
            ax.set_xticks([0,20,100,500,2000]);ax.set_xticklabels(['0','20','100','500','2,000'])
            ax.set_yticks([0,.25,.5,.75,1]);ax.grid(alpha=.18,lw=.7)
            for sp in ['top','right']:ax.spines[sp].set_visible(False)
            if row==1:
                ax.annotate('UCB: event beyond 2,000',xy=(.98,1.0),xycoords='axes fraction',color=GREEN,fontsize=8.8,ha='right',va='top')
                ax.plot([H],[1],marker='>',color=GREEN,markersize=6,clip_on=False,zorder=5)
    fig.supylabel('Probability / fraction still waiting',x=.016,fontsize=11)
    fig.supxlabel('Clean steps after the reward change (symmetric log scale)',y=.07,fontsize=10.5)
    handles=[Line2D([],[],color=colors[r],marker=markers[r],markerfacecolor='white',lw=1.5,label=lab)
             for r,lab in [('epsilon_greedy','Epsilon-greedy'),('softmax','Softmax'),('ucb','UCB-style')]]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.99),ncol=3,frameon=False,fontsize=10.5)
    fig.text(.5,.91,'Lines: exact theory    Hollow markers: saved observations at selected checkpoints',ha='center',fontsize=10)
    fig.text(.5,.012,'300 runs per stochastic condition; 1 deterministic UCB run. Confirmation requires 20 observations within tolerance.',
             ha='center',fontsize=8.6)
    save(fig,'terminal_theory_empirical')
    return checks

if __name__=='__main__':
    environment();checks=terminal()
    record={'note':'No experimental reruns. Exact terminal predictions evaluated and matched to saved theory columns.',
            'settings':{'alpha':.9,'gamma':.9,'epsilon':.1,'tau':.2,'beta':1,'rho':.05,
                        'confirmation_observations':20,'pre_counts':[100,100],'post_demotion_counts':[101,100],
                        'C':3,'Delta':3,'H':2000},
            'inputs':{n:hashlib.sha256((ROOT/'data'/n).read_bytes()).hexdigest()
                      for n in ['terminal_summary.csv','terminal_survival.csv']},'checks':checks}
    (OUT/'figure_generation_checks.json').write_text(json.dumps(record,indent=2))
    print('Created chain_reset_timeline and terminal_theory_empirical, each as PDF and PNG.')
    print('Checked',len(checks),'curve/condition combinations against saved theory and event summaries.')
