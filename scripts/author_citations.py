"""Normalize cited author names; retain variants for inspection."""
import collections
import csv
import json
import re
import unicodedata
from pathlib import Path
from reference_analysis import plain, title_of
from analyze_citations import field


def names(r):
    if r['internal_targets']:
        return ['OpenAI']
    raw=field(r['body'],'author') if r['source'].endswith('.bib') else title_of(r)[1]
    text=plain(raw)
    if not text:
        return []
    if 'openai' in text.lower():return ['OpenAI']
    if 'stacks project' in text.lower():return ['The Stacks Project Authors']
    text=re.sub(r'\bet\s+al\.?|\band others\b','',text,flags=re.I)
    if r['source'].endswith('.bib'):
        return [n.strip(' ,.') for n in re.split(r'\s+and\s+',text) if n.strip(' ,.')] 
    return [n.strip(' ,.') for n in re.split(r',\s*|\s+and\s+|\s*&\s*',text) if n.strip(' ,.')] 


def identity(name):
    if name in ('OpenAI','The Stacks Project Authors'):
        return name,''
    clean=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
    if ',' in clean:
        surname,given=clean.split(',',1)
    else:
        words=clean.split()
        if len(words)<2:return None
        surname=words[-1];given=' '.join(words[:-1])
        particles={'van','von','de','del','den','der','le','la','du','da','di'}
        while given.split() and given.split()[-1].lower() in particles:
            parts=given.split();surname=parts[-1]+' '+surname;given=' '.join(parts[:-1])
    # Break joined initials (J.-P., J.S.) into individual given-name initials.
    gs=re.findall(r'[A-Za-z]+',given)
    initials=''.join(w.lower() if w.isupper() and len(w)<=3 else w[0].lower() for w in gs)
    sn=re.sub(r'[^a-z]','',surname.lower())
    if not sn or not initials:return None
    if len(gs)>6 or any(w in clean.lower() for w in ['collaboration','university','society','editors','authors','press']):return None
    return sn,initials


def main():
    variants=collections.defaultdict(set);references=collections.defaultdict(set);papers=collections.defaultdict(set);ignored=[]
    records=list(csv.DictReader(open('data/references.csv')))
    for r in records:
        if r['cited_in_tex']!='True':continue
        for name in names(r):
            key=identity(name)
            if key is None:ignored.append({'name':name,'source':r['source'],'key':r['key']});continue
            variants[key].add(name);references[key].add((r['manuscript'],r['key']));papers[key].add(r['manuscript'])
    # Merge an abbreviated initial signature only when exactly one longer
    # signature with that surname extends it. Ambiguous names stay separate.
    for key in sorted(list(variants),key=lambda k:len(k[1])):
        sn,initials=key
        if not initials:continue
        compatible=[k for k in variants if k[0]==sn and k[1].startswith(initials) and len(k[1])>len(initials)]
        def given_names(v):
            words=re.findall(r'[A-Za-z]+',v.split(',',1)[1] if ',' in v else ' '.join(v.split()[:-1]))
            return {w.lower() for w in words if len(w)>2 and not w.isupper()}
        expanded={w for v in variants[key] for w in given_names(v)}
        if expanded:
            compatible=[k for k in compatible if expanded & {w for v in variants[k] for w in given_names(v)}]
        if len(compatible)==1:
            dest=compatible[0];variants[dest]|=variants.pop(key);references[dest]|=references.pop(key);papers[dest]|=papers.pop(key)
    rows=[];ambiguous=[]
    for key,vs in variants.items():
        def score(v):return (sum(len(w)>2 for w in re.findall('[A-Za-z]+',v)),-v.count('.'),len(v))
        display=max(vs,key=score)
        if ',' in display:
            last,first=display.split(',',1);display=first.strip()+' '+last.strip()
        expanded_firsts={next(iter(re.findall(r'[A-Za-z]+',v.split(',',1)[1] if ',' in v else v)), '').lower() for v in vs if len(re.findall(r'[A-Za-z]+',v.split(',',1)[1] if ',' in v else v)[0])>2} if key[1] else set()
        # Spelling variants for Gromov and Grothendieck are explicit aliases;
        # common surname/initial collisions are exposed, not silently named.
        if len(expanded_firsts)>1 and key[0] not in ('gromov','grothendieck'):
            ambiguous.append({'surname':key[0],'initials':key[1],'variants':sorted(vs)})
            display=key[1].upper()+'. '+key[0].title()+' (ambiguous)'
        rows.append({'author':display,'surname_key':key[0],'initials':key[1],'citing_manuscripts':len(papers[key]),'cited_reference_entries':len(references[key]),'variants':' | '.join(sorted(vs))})
    rows.sort(key=lambda r:(-r['citing_manuscripts'],r['author']))
    out=Path('results/blog')
    with (out/'authors.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'author-audit.json').write_text(json.dumps({'ignored':ignored,'ambiguous_groups':ambiguous,'method':'Names normalized by surname and given-name initials; unambiguous abbreviated initial signatures merged when expanded given names agree. Coauthors receive full credit; each citing manuscript counts once per author. Editors and unlisted et al. authors are not expanded. Ambiguous collisions are flagged.'},indent=2))
    print(json.dumps(rows[:35],indent=2))


if __name__=='__main__':main()
