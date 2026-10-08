# OpenAI math citation network

Code and four finished PNG figures for the citation-network analysis of [OpenAI's mathematics release](https://github.com/openai/math), using source commit `adc7f1241b42e322a6451854ab7e4b4c146bf78a`.

## Figures

- [Largest connected component](plots/figure-01-network.png)
- [Most cited authors and works](plots/figure-02-rankings.png)
- [Citation-cycle examples](plots/figure-03-cycles.png)
- [Manuscript dates and citation timing](plots/figure-04-dates-and-chronology.png)

## Reproduce the figures

Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
MPLCONFIGDIR=.matplotlib-cache python scripts/plot_figures.py
```

The plotting script uses frozen inputs in `scripts/figure_inputs.py` and generates exactly the four PNG files. The first figure's layout is retained so repeated renders preserve its arrangement.

## Recalculate from source

```sh
git clone https://github.com/openai/math.git /tmp/openai-math-source
git -C /tmp/openai-math-source checkout adc7f1241b42e322a6451854ab7e4b4c146bf78a
python scripts/rebuild_inputs.py /tmp/openai-math-source
MPLCONFIGDIR=.matplotlib-cache python scripts/plot_figures.py
```

The extractor reads LaTeX and BibTeX sources and excludes unused bibliography entries. Internal edges count each citing/cited manuscript pair once. Outside works are matched using identifiers and titles. Author normalization credits named coauthors and flags ambiguous names; omitted authors in “et al.” references are not reconstructed. The results are source-derived citation counts, not proof verification or worldwide citation counts. Dates are manuscript metadata.

Intermediate CSVs and audits generated during recalculation are gitignored. The repository contains no drafts, PDFs, or separately exported panels.
