"""Recalculate chart counts from the pinned OpenAI math release."""
import argparse
import collections
import csv
import datetime as dt
import json
import pprint
import re
import subprocess
import sys
from pathlib import Path
import networkx as nx
from figure_inputs import INPUTS
from reference_analysis import external_analysis


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source_repository',type=Path)
    args=parser.parse_args()
    source=args.source_repository.resolve()
    project=Path(__file__).resolve().parents[1]
    snapshot=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if snapshot!=INPUTS['snapshot']:
        parser.error('Check out source commit '+INPUTS['snapshot']+' first.')
    import os
    os.chdir(project)
    subprocess.run([sys.executable,'scripts/analyze_citations.py',str(source)],check=True,stdout=subprocess.DEVNULL)
    references=list(csv.DictReader(open('data/references.csv')))
    outside,_=external_analysis(references)
    subprocess.run([sys.executable,'scripts/author_citations.py'],check=True,stdout=subprocess.DEVNULL)
    authors=list(csv.DictReader(open('results/blog/authors.csv')))
    papers={r['slug']:r for r in csv.DictReader(open('data/manuscripts.csv'))}
    graph=nx.DiGraph();graph.add_nodes_from(papers)
    graph.add_edges_from((r['citing'],r['cited']) for r in csv.DictReader(open('data/internal_edges.csv')) if r['cited_in_tex']=='True')
    largest=max(nx.weakly_connected_components(graph),key=len)
    frozen={n['id']:n['slug'] for n in INPUTS['network']['nodes']}
    assert largest==set(frozen.values())
    assert set(graph.subgraph(largest).edges)=={(frozen[e['source']],frozen[e['target']]) for e in INPUTS['network']['edges']}
    # Preserve the published layout; recomputation verifies all its edges.
    internal=sorted([{'title':r['title'],'direct_citing_manuscripts':graph.in_degree(s)} for s,r in papers.items()],key=lambda r:(-r['direct_citing_manuscripts'],r['title']))
    dates={}
    for slug in papers:
        readme=(source/'preprints'/slug/'README.md').read_text()
        match=re.search(r'([A-Z][a-z]+ \d{1,2}, 2026|\d{1,2} [A-Z][a-z]+ 2026)',readme)
        assert match,slug
        dates[slug]=dt.datetime.strptime(match[1],'%B %d, %Y' if ',' in match[1] else '%d %B %Y').date()
    counts=collections.Counter(dates.values())
    lags=[(dates[b]-dates[a]).days for a,b in graph.edges]
    chronology=[sum(d<0 for d in lags),sum(d==0 for d in lags),sum(d>0 for d in lags)]
    cycles=list(nx.simple_cycles(graph))
    for example in INPUTS['cycles']:
        slugs=[n['slug'] for n in example['nodes']]
        assert all(graph.has_edge(a,b) for a,b in zip(slugs,slugs[1:]+slugs[:1]))
    assert len(graph)==722 and graph.number_of_edges()==594
    assert collections.Counter(map(len,cycles))=={2:103,3:28,4:12,5:4}
    assert chronology==[199,345,50]
    INPUTS['authors']=[{k:r[k] for k in ('author','citing_manuscripts')} for r in authors[:10]]
    INPUTS['outside_works']=[{k:r[k] for k in ('title','citing_manuscripts')} for r in outside[:10]]
    INPUTS['internal_papers']=internal[:10]
    INPUTS['dates']=[{'date':str(d),'manuscripts':n} for d,n in sorted(counts.items())]
    INPUTS['chronology']=chronology
    (project/'scripts/figure_inputs.py').write_text('"""Frozen inputs for the four published figures, from the pinned source snapshot."""\n\nINPUTS = '+pprint.pformat(INPUTS,width=105,sort_dicts=False)+'\n')
    print('Verified source snapshot, graph, cycle counts, and chronology; rebuilt figure inputs.')


if __name__=='__main__':
    main()
