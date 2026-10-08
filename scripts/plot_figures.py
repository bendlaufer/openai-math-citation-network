"""Arrange figures to follow the author's blog outline."""
import csv
import json
import argparse
import textwrap
from datetime import date, timedelta
from pathlib import Path
import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reference_analysis import plain, cycle_label
from figure_inputs import INPUTS

OUT=Path(__file__).resolve().parents[1]/'plots';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':11,'axes.titlesize':14,'axes.labelsize':10})


def export(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=200,bbox_inches='tight')
    plt.close(fig)


def network():
    data=INPUTS['network']
    g=nx.DiGraph()
    g.add_nodes_from(n['id'] for n in data['nodes'])
    g.add_edges_from((e['source'],e['target']) for e in data['edges'])
    positions={n['id']:(n['x'],n['y']) for n in data['nodes']}
    fig,ax=plt.subplots(figsize=(12,9),layout='constrained')
    nx.draw_networkx_edges(g,positions,ax=ax,arrows=True,arrowstyle='-|>',
                           arrowsize=13,edge_color='#888888',alpha=.65,
                           connectionstyle='arc3,rad=0.08',node_size=180)
    nx.draw_networkx_nodes(g,positions,ax=ax,node_size=180,
                           node_color='#333333',
                           edgecolors='white',linewidths=1)
    ax.set_title('Largest citation component\n39 papers · 72 links',
                 loc='left',fontsize=18,pad=18)
    ax.text(0,-.02,'Arrows: citing → cited',
            transform=ax.transAxes,fontsize=10,color='#4c5966')
    ax.margins(.10);ax.axis('off')
    export(fig,'figure-01-network')


def bar_panel(ax,rows,value,label,color,wrap=37):
    labels=['\n'.join(textwrap.wrap(plain(r[label]),wrap)) for r in rows]
    values=[int(r[value]) for r in rows]
    ax.barh(range(len(rows)),values,color=color,height=.65)
    ax.set_yticks(range(len(rows)),labels,fontsize=9)
    ax.invert_yaxis();ax.set_xlim(0,max(values)*1.18)
    for i,v in enumerate(values):
        ax.text(v+max(values)*.015,i,str(v),va='center',fontsize=10)
    ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True);ax.grid(axis='x',alpha=.15)
    ax.set_xlabel('Citing papers')


def rankings():
    authors=INPUTS['authors']
    works=INPUTS['outside_works']
    internal=INPUTS['internal_papers']
    internal.sort(key=lambda r:(-int(r['direct_citing_manuscripts']),r['title']))
    fig,axs=plt.subplots(1,3,figsize=(24,9),layout='constrained')
    bar_panel(axs[0],authors[:10],'citing_manuscripts','author','#7464a4')
    bar_panel(axs[1],works[:10],'citing_manuscripts','title','#458873')
    bar_panel(axs[2],internal[:10],'direct_citing_manuscripts','title','#346a9b')
    axs[0].set_title('A. Authors',loc='left',pad=15)
    axs[1].set_title('B. Outside works',loc='left',pad=15)
    axs[2].set_title('C. Internal papers',loc='left',pad=15)
    fig.suptitle('Most cited authors and works',fontsize=22)
    export(fig,'figure-02-rankings')


def cycles():
    examples=INPUTS['cycles']
    totals={3:28,4:12,5:4}
    fig,axs=plt.subplots(1,3,figsize=(19,6),layout='constrained')
    for ax,example in zip(axs,examples):
        nodes=example['nodes'];k=len(nodes)
        g=nx.DiGraph();g.add_edges_from((i,(i+1)%k) for i in range(k))
        positions=nx.circular_layout(g)
        nx.draw_networkx_edges(g,positions,ax=ax,arrows=True,arrowsize=24,node_size=600,edge_color='#8495a4',width=1.8)
        nx.draw_networkx_nodes(g,positions,ax=ax,node_color='#346a9b',node_size=600)
        nx.draw_networkx_labels(g,positions,ax=ax,labels={i:str(i+1) for i in range(k)},font_color='white',font_size=12)
        ax.set_title(f'{k}-paper cycle',fontsize=14)
        legend='\n\n'.join(f'{i+1}. '+'\n   '.join(textwrap.wrap(cycle_label(n['title']),48)) for i,n in enumerate(nodes))
        ax.text(0,-.08,legend,transform=ax.transAxes,va='top',fontsize=17,linespacing=1.35)
        ax.set_ylim(-1.3,1.3);ax.set_xlim(-1.4,1.4);ax.axis('off')
    fig.suptitle('Citation cycles',fontsize=20)
    export(fig,'figure-03-cycles')


def chronology():
    counts={date.fromisoformat(r['date']):int(r['manuscripts']) for r in INPUTS['dates']}
    days=[];d=min(counts)
    while d<=max(counts):days.append(d);d+=timedelta(days=1)
    fig,axs=plt.subplots(1,2,figsize=(16,5.5),layout='constrained',gridspec_kw={'width_ratios':[1.8,1]})
    ax=axs[0];ax.bar(days,[counts.get(d,0) for d in days],width=.78,color='#346a9b')
    for d,n in counts.items():ax.annotate(str(n),(mdates.date2num(d),n),xytext=(0,5),textcoords='offset points',ha='center',fontsize=9)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3));ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.set_ylim(0,225);ax.set_ylabel('Manuscripts');ax.set_title('A. Manuscript dates',loc='left',pad=15)
    release=date(2026,10,6);ax.axvline(release,color='#cc744b',ls='--',lw=1.5)
    ax.annotate('Release: Oct 6',(mdates.date2num(release),210),xytext=(-8,0),textcoords='offset points',ha='right',color='#a95332',fontsize=10)
    ax=axs[1];values=INPUTS['chronology'];labels=['Earlier','Same date','Later']
    ax.bar(labels,values,color=['#458873','#90a2b2','#cc744b'])
    for i,n in enumerate(values):ax.text(i,n+8,f'{n}\n({n/594:.1%})',ha='center',fontsize=11)
    ax.set_ylim(0,410);ax.set_ylabel('Citations');ax.set_title('B. Citation timing',loc='left',pad=15)
    for ax in axs:ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Dates and citation timing (2026)',fontsize=20)
    export(fig,'figure-04-dates-and-chronology')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--figure',choices=['all','network','cycles'],default='all')
    args=parser.parse_args()
    if args.figure in ('all','network'):
        network()
    if args.figure=='all':
        rankings();cycles();chronology()
        print('Created the four published PNG figures.')
    elif args.figure=='network':
        print('Updated figure-01-network.png.')
    else:
        cycles()
        print('Updated figure-03-cycles.png.')
