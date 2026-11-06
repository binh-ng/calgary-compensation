# City of Calgary compensation, over time

Data, interactive plots, reports and infographics built from the City of Calgary's annual
Compensation Disclosure Lists (open data, https://data.calgary.ca). The ETL reads the City's unified
dataset (`9bze-mzx6`, every year since 2014) with one query filtered to 2024 to 2026.

- **Complete dataset:** `data/processed/compensation_all_years.csv` and `.parquet`
- **Summary tables:** `group_pivot.csv`, `matched_changes.csv`
- **Site:** interactive plots, a one-page brief, a detailed report and infographics (GitHub Pages)

## Run it locally

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/etl.py             # one query, then rebuild the data (add --offline to reuse data/raw)
python src/plots.py           # site/plots/*.html
python src/infographics.py    # site/infographics/*.png
quarto render reports/brief.qmd
quarto render reports/detailed.qmd
```

## Change the years

Edit `first_year` and `last_year` in `datasets.yml` and run `python src/etl.py`. The query is
`$where=year in ('2024','2025','2026')`, paged 1,000 rows at a time. In a notebook:

```python
import sys; sys.path.insert(0, "src")
from etl import get_dataframe
df = get_dataframe()   # pandas DataFrame: year, title, min_rate, max_rate, midpoint, role_group, ...
```

## About the data

Each row is a position title with a minimum and maximum annual base rate, not an individual salary.
Only filled positions appear. Calgary Police Service, seasonal, on-call and student jobs, non-union
recreation program jobs, some unique contract positions and elected officials are excluded. Role groups
come from keywords in the title (`src/etl.py`) and are approximate.

Data: City of Calgary Open Data. Check the licence on each dataset page and credit the City when you reuse it.
