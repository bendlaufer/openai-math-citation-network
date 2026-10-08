"""Extract manuscript-level citation edges from the OpenAI math release sources."""
import argparse
import collections
import csv
import json
import re
import subprocess
from pathlib import Path


def uncomment(s):
    return re.sub(r'(?<!\\)%[^\n]*', '', s)


def balanced(s, start):
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{' and (i == 0 or s[i-1] != '\\'):
            depth += 1
        elif s[i] == '}' and (i == 0 or s[i-1] != '\\'):
            depth -= 1
            if depth == 0:
                return s[start+1:i], i+1
    return s[start+1:], len(s)


def field(s, name):
    m = re.search(r'\b'+name+r'\s*=\s*([{"])', s, re.I)
    if not m:
        return ''
    if m[1] == '{':
        return balanced(s, m.end()-1)[0]
    return s[m.end():].split('"')[0]


def normalized(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('repository', type=Path)
    args = ap.parse_args()
    root = args.repository
    out = Path('data'); out.mkdir(exist_ok=True)
    catalogue = root.joinpath('CONTENTS.md').read_text()
    titles = {slug:title for title,slug in re.findall(r'\[([^\n]+?)\]\(preprints/([^/]+)/[^)]+\.pdf\)',catalogue)}
    assert len(titles) == 722, len(titles)
    title_lookup = collections.defaultdict(set)
    for slug, title in titles.items():
        title_lookup[normalized(title)].add(slug)
    refs = []; edges = {}; unresolved = []; missing = []; uncalled = []
    for slug,title in titles.items():
        directory = root/'preprints'/slug
        entries = {}
        texts = []
        for path in sorted(directory.rglob('*')):
            if path.suffix not in ('.tex','.bib','.bbl'):
                continue
            raw = path.read_text(errors='replace')
            # BibTeX permits literal percent-encoded URLs in field values.
            # TeX-style inline comment removal would unbalance their braces.
            s = re.sub(r'^\s*%[^\n]*', '', raw, flags=re.M) if path.suffix == '.bib' else uncomment(raw)
            if path.suffix == '.tex':
                texts.append(s)
            if path.suffix == '.bib':
                for m in re.finditer(r'@\w+\s*\{\s*([^,\s]+)\s*,',s):
                    body,_ = balanced(s,s.index('{',m.start()))
                    entries[m[1]] = (body,field(body,'title'),str(path.relative_to(root)))
            else:
                matches = list(re.finditer(r'\\bibitem\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}',s))
                for i,m in enumerate(matches):
                    body = s[m.end():matches[i+1].start() if i+1<len(matches) else len(s)]
                    body = body.split(r'\end{thebibliography}')[0]
                    tm = re.search(r'\\(?:emph|textit)\s*\{',body)
                    rt = balanced(body,tm.end()-1)[0] if tm else ''
                    entries[m[1]] = (body,rt,str(path.relative_to(root)))
        text = '\n'.join(texts)
        called = set()
        for m in re.finditer(r'\\(?:[Cc]ite\w*|nocite)\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}',text):
            called.update(k.strip() for k in m[1].split(','))
        if '*' in called:
            called.update(entries)
            called.remove('*')
        for key in called - entries.keys():
            missing.append({'manuscript':slug,'key':key})
        for key,(body,rt,source) in entries.items():
            targets = set(re.findall(r'(?:preprints/|OAI:)([A-Za-z0-9-]+)',body)) & titles.keys()
            if not targets and normalized(rt) and re.search(r'\bOpenAI\b',body,re.I):
                targets = title_lookup.get(normalized(rt), set())
            active = key in called
            if ('OpenAI' in body or 'OAI:' in body or 'openai/math' in body) and not targets:
                unresolved.append({'manuscript':slug,'key':key,'body':body,'active':active})
            refs.append({'manuscript':slug,'key':key,'title':rt,'cited_in_tex':active,'internal_targets':';'.join(sorted(targets)),'source':source,'body':body})
            if not active:
                uncalled.append({'manuscript':slug,'key':key,'internal_targets':list(targets)})
            for target in targets:
                if target != slug:
                    edges[(slug,target)] = {'citing':slug,'cited':target,'key':key,'cited_in_tex':active,'source':source}
    def save_csv(name,rows,fields):
        with (out/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    save_csv('references.csv',refs,list(refs[0]))
    save_csv('internal_edges.csv',list(edges.values()),['citing','cited','key','cited_in_tex','source'])
    incoming = collections.Counter(e['cited'] for e in edges.values() if e['cited_in_tex'])
    outgoing = collections.Counter(e['citing'] for e in edges.values() if e['cited_in_tex'])
    refcounts = collections.Counter(r['manuscript'] for r in refs if r['cited_in_tex'])
    rows = [{'slug':s,'title':t,'internal_citations_received':incoming[s],'internal_references':outgoing[s],'references_cited':refcounts[s]} for s,t in titles.items()]
    save_csv('manuscripts.csv',rows,list(rows[0]))
    summary = {'commit':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip(),'manuscripts':len(titles),'internal_edges':sum(e['cited_in_tex'] for e in edges.values()),'bibliography_edges':len(edges),'papers_receiving_internal_citations':len(incoming),'papers_citing_internal':len(outgoing),'incoming_distribution':dict(sorted(collections.Counter(incoming[s] for s in titles).items())),'top_internal':sorted(rows,key=lambda r:-r['internal_citations_received'])[:15],'unresolved_internal':unresolved,'missing_keys':missing,'uncalled_internal':[r for r in uncalled if r['internal_targets']]}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k not in ('unresolved_internal','missing_keys','uncalled_internal')},indent=2))
    print('Audit counts:',len(unresolved),len(missing),len(summary['uncalled_internal']))


if __name__ == '__main__':
    main()
