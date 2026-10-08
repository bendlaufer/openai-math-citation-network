"""Reproducible network, chronology, and external-reference analyses."""
import argparse
import collections
import csv
import datetime as dt
import difflib
import json
import re
import textwrap
import unicodedata
from pathlib import Path
import networkx as nx
from analyze_citations import balanced, field

OUT = Path('results/blog'); OUT.mkdir(parents=True, exist_ok=True)


def plain(s):
    # Preserve hyperlink labels and unwrap common text/math formatting.
    s=s.replace(r'\gt',' > ').replace(r'\lt',' < ')
    for _ in range(3):
        s = re.sub(r'\\href\s*\{[^{}]*\}\s*\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\[\'"`^~=.uvHckbdr]\s*\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\[\'"`^~=.]+\s*([A-Za-z])', r'\1', s)
    s = re.sub(r'\\(?:emph|textit|textbf|mathrm|mathbb|operatorname|newblock|newline|em|it)\b', '', s)
    s = re.sub(r'\\([A-Za-z]+)', r'\1', s)
    s = s.translate(str.maketrans({'{':'','}':'','$':'','~':' ','\\':'','\n':' ','`':''}))
    return re.sub(r'\s+', ' ', s).strip(' ,.;')


def cycle_label(title):
    labels = {
        'A surface counterexample to Shafarevich holomorphic convexity': 'Shafarevich counterexample',
        'Semialgebraic universal covers of normal projective varieties': 'Semialgebraic universal covers',
        'The abelianity conjecture for special compact Kähler manifolds': 'Special Kähler abelianity',
        'An Almost-Linear Approximation Scheme for Edit Distance': 'Edit-distance approximation',
        'Edit Distance in l1: Matching Bounds up to Constants in the Exponent': 'Edit distance in ℓ₁',
        'Finite-Circle Obstructions, Binary Codes, and Histogram Embeddings for Edit Distance': 'Finite-circle constructions',
        'Tree Constructions for the l1 Distortion of Binary Edit Distance': 'Tree constructions',
        'Conditional information under deterministic coordinate sweeps': 'Coordinate sweeps',
        'From partial permutation information to Fourier bounds': 'Permutation Fourier bounds',
        'Conditional permutations in a revealed switching environment': 'Conditional permutations',
        'Random coordinate frames and partial permutation laws': 'Random coordinate frames',
        'Optimal-order mixing of the Thorp shuffle': 'Thorp-shuffle mixing',
    }
    return labels.get(title, plain(title))


def norm(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD',plain(s)).encode('ascii','ignore').decode().lower())


def save(name, rows):
    if not rows:
        return
    with (OUT/name).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)


def title_of(r):
    body=r['body']
    if r['source'].endswith('.bib'):
        return field(body,'title'), field(body,'author'), 'bibtex'
    blocks = body.split(r'\newblock')
    if len(blocks)>1:
        return blocks[1].strip(), blocks[0].strip(), 'newblock'
    # Explicit hyperlink whose displayed label is the article title.
    for m in re.finditer(r'\\href\s*\{',body):
        url,end=balanced(body,m.end()-1)
        labelstart=re.search(r'\s*\{',body[end:])
        if not labelstart:
            continue
        label,_=balanced(body,end+labelstart.end()-1)
        labelplain=plain(label)
        if len(labelplain)>22 and not re.search(r'https?:|doi:|arxiv:|version|author|preprint|Lemma|Theorem|Tag',labelplain,re.I):
            return label,body[:m.start()].strip(),'linked-title'
    m=re.search(r'\\(?:emph|textit)\s*\{',body)
    if m:
        prefix=body[:m.start()].strip()
        lines=[l.strip() for l in prefix.splitlines() if l.strip()]
        # Some references put the unformatted article title before the journal.
        candidate=' '.join(lines[1:])
        looks_like_authors=lambda value: bool(re.search(r'(?:^|[ ,])(?:[A-Z]\.\s*)+',plain(value))) or 'collaboration' in value.lower()
        if len(lines)>=2 and lines[0].endswith(('.', ',')) and not looks_like_authors(candidate):
            return candidate,lines[0],'plain-before-journal'
        if len(lines)==1 and ',' in prefix:
            author, candidate=prefix.split(',',1)
            if len(plain(candidate))>15 and not looks_like_authors(candidate):
                return candidate,author,'plain-before-journal'
        pp=plain(prefix)
        if '. ' in pp:
            author,candidate=pp.rsplit('. ',1)
            if len(candidate)>20 and not looks_like_authors(candidate):
                return candidate,author,'plain-before-journal'
        return balanced(body,m.end()-1)[0],prefix,'formatted-title'
    lines=[l.strip() for l in body.strip().splitlines() if l.strip()]
    if len(lines)>=2:
        return lines[1],lines[0],'plain-line'
    return '', '', 'unparsed'


def identifiers(r):
    body=r['body']
    dois=set()
    if r['source'].endswith('.bib') and field(body,'doi'):
        dois.add(field(body,'doi').strip().lower())
    for m in re.finditer(r'(?:doi\.org/|doi:\s*)(10\.\d{4,9}/[^\s{}<>]+)',body,re.I):
        dois.add(m[1].rstrip('.,;').lower())
    arxivs=set(re.findall(r'(?:arxiv\.org/(?:abs|pdf)/|arXiv:\s*)((?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7}))(?:v\d+)?',body,re.I))
    if r['source'].endswith('.bib') and 'arxiv' in body.lower():
        ep=field(body,'eprint')
        if ep:
            arxivs.add(re.sub(r'v\d+$','',ep).lower())
    return sorted({d.replace('\\_', '_').replace('\\&', '&') for d in dois}),sorted(a.lower() for a in arxivs)


def external_analysis(refs):
    records=[]
    for r in refs:
        if r['cited_in_tex']!='True' or r['internal_targets']:
            continue
        title,author,method=title_of(r)
        dois,arxivs=identifiers(r)
        records.append({**r,'clean_title':plain(title),'author':plain(author),'method':method,'dois':dois,'arxivs':arxivs})
    parent=list(range(len(records)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        parent[find(a)]=find(b)
    ids=collections.defaultdict(list); titlegroups=collections.defaultdict(list)
    identity_conflicts=[]
    for i,r in enumerate(records):
        for ident in ['doi:'+d for d in r['dois']]+['arxiv:'+a for a in r['arxivs']]:
            for other in ids[ident]:
                a,b=norm(r['clean_title']),norm(records[other]['clean_title'])
                # A chapter and its containing book can share an arXiv URL.
                # Require compatible titles rather than blindly merging them.
                if not a or not b or a==b or difflib.SequenceMatcher(None,a,b).ratio()>=.75:
                    union(i,other)
                else:
                    identity_conflicts.append({'identifier':ident,'title_a':r['clean_title'],'title_b':records[other]['clean_title']})
            ids[ident].append(i)
        t=norm(r['clean_title'])
        body=r['body'].lower()
        if 'stacks.math.columbia.edu' in body or 'the stacks project authors' in plain(r['author']).lower() or t in ('thestacksproject','stacksproject'):
            t='database:stacksproject'
        elif t=='algebraictopology':
            # Hatcher and Spanier have distinct books with this title.
            t += ':hatcher' if 'hatcher' in body else ':spanier' if 'spanier' in body else ':unknown'
        elif t=='algebraicnumbertheory':
            t += ':neukirch' if 'neukirch' in body else ':casselsfrohlich' if 'cassels' in body else ':lang' if 'lang' in body else ':milne' if 'milne' in body else ':unknown'
        if t: titlegroups[t].append(i)
    conflicts=[]
    for t,inds in titlegroups.items():
        ds={d for i in inds for d in records[i]['dois']}
        if len(ds)>1:
            conflicts.append({'normalized_title':t,'dois':sorted(ds),'entries':len(inds)})
            # Avoid conflating different editions or papers with the same title.
            continue
        for i in inds[1:]:union(inds[0],i)
    groups=collections.defaultdict(list)
    for i,r in enumerate(records):groups[find(i)].append(r)
    ranked=[];members=[]
    for group in groups.values():
        candidates=[r for r in group if r['clean_title']]
        if not candidates:continue
        method_rank={'bibtex':0,'newblock':1,'linked-title':2,'plain-before-journal':3,'formatted-title':4,'plain-line':5}
        candidates.sort(key=lambda r:(method_rank.get(r['method'],6),len(r['clean_title'])))
        representative=candidates[0]
        title=representative['clean_title']
        if 'stacks.math.columbia.edu' in representative['body'].lower() or 'stacks project' in representative['author'].lower():title='The Stacks Project'
        papers=sorted({r['manuscript'] for r in group})
        is_database='stacks project' in representative['author'].lower() or 'stacks.math.columbia.edu' in representative['body'].lower() or 'dlmf.nist.gov' in representative['body'].lower()
        dois=sorted({d for r in group for d in r['dois']})
        arxivs=sorted({d for r in group for d in r['arxivs']})
        sourcepath=representative['source']
        # Mark books using bibliographic metadata rather than title guesses.
        is_book=bool(re.search(r'\bpublisher\s*=',representative['body'],re.I)) and not bool(re.search(r'\b(?:journal|booktitle)\s*=',representative['body'],re.I))
        kind='database' if is_database else 'book/monograph' if is_book else 'article or other work'
        row={'title':title,'author':representative['author'],'citing_manuscripts':len(papers),'kind':kind,'doi':';'.join(dois),'arxiv':';'.join(arxivs),'example_source':sourcepath,'example_key':representative['key']}
        ranked.append(row)
        for r in group:
            members.append({'group_title':title,'group_author':row['author'],'manuscript':r['manuscript'],'key':r['key'],'extracted_title':r['clean_title'],'method':r['method'],'source':r['source']})
    ranked.sort(key=lambda r:(-r['citing_manuscripts'],r['title']))
    save('outside-literature.csv',ranked);save('outside-reference-members.csv',members)
    (OUT/'outside-audit.json').write_text(json.dumps({'entries':len(records),'unparsed_titles':sum(not r['clean_title'] for r in records),'title_doi_conflicts':conflicts,'identifier_title_conflicts':identity_conflicts},indent=2))
    return ranked,records

