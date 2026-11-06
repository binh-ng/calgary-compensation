"""Extract, transform and load the City of Calgary Compensation Disclosure Lists.

Usage:
    python src/etl.py             run one query against the unified dataset, then rebuild outputs
    python src/etl.py --offline   skip the download and rebuild from data/raw/compensation.json

In a notebook:
    from etl import get_dataframe
    df = get_dataframe()          # DataFrame for the years in datasets.yml
"""
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
URL = "https://data.calgary.ca/resource/{id}.json"
RAW_FILE = "compensation.json"
PAGE = 1000  # Socrata returns at most 1,000 rows unless you page with $limit and $offset

# Row counts seen when this project was built. A mismatch only prints a warning,
# because the City can revise a list after publishing it.
EXPECTED = {2024: 1902, 2025: 1923, 2026: 2063}

# Role groups: the first rule that matches the title wins. Edit the keywords to taste.
GROUP_RULES = [
    ("Executive and senior leadership", r"\b(chief|general manager|director|city solicitor|city clerk|city auditor|city manager|deputy city|commissioner|ceo)\b"),
    ("Management and supervision", r"\b(manager|superintendent|supervisor|foreperson|foreman|team lead|leader|lead hand|head)\b"),
    ("Public safety and emergency", r"\b(fire|firefighter|police|constable|sergeant|detective|peace officer|bylaw|paramedic|911|emergency|investigator|platoon|k9|captain|protective|safety|security|dispatcher|enforcement|patrol|lieutenant|battalion)\b"),
    ("IT, data and technology", r"\b(it|software|developer|data|application|applications|network|cyber|cloud|database|devops|gis|systems|digital|technology|web|solution|scrum|product owner)\b"),
    ("Engineering, planning and design", r"\b(engineer|engineering|planner|planning|architect|surveyor|geomatics|drafting|designer|design|urban|environmental|hydrolog\w*|geotechnical|land|development|inspector|inspection|technologist|estimator|permit|building)\b"),
    ("Transit and fleet", r"\b(transit|bus|lrt|ctrain|fleet|mechanic|driver|roadway|rail|train|vehicle|garage|stores|parts)\b"),
    ("Trades, utilities and field operations", r"\b(electrician|journeyperson|plumber|carpenter|operator|maintenance|laborer|labourer|utilities|utility|water|wastewater|waste|parks|arborist|forestry|horticulture|hydrant|road|traffic|welder|technician|pipe|landfill|custodian|equipment|worker|crew|sewer|mechanical)\b"),
    ("Finance, legal, HR and corporate", r"\b(accountant|accounting|financial|finance|payroll|human resources|hr|procurement|buyer|audit|auditor|tax|assessor|assessment|treasury|legal|lawyer|solicitor|paralegal|communications|marketing|insurance|risk|budget|recruit|labour relations|compensation|talent|corporate|contracts|supply|purchasing|records|privacy|policy|strategy|strategist)\b"),
    ("Recreation, library and community", r"\b(recreation|aquatic|lifeguard|instructor|library|librarian|community|social|program|golf|arena|cultural|child|youth|fitness|attendant|facility|facilitator|ambassador|outreach|cashier|guest|zoo|museum|heritage|arts)\b"),
    ("Customer service and administration", r"\b(administrative|admin|clerk|receptionist|customer|311|service representative|scheduler|assistant|coordinator|secretary|clerical|office|information|intake|support)\b"),
    ("Analysts, advisors and specialists", r"\b(analyst|advisor|specialist|consultant|business partner|researcher|coach|educator|trainer|expert)\b"),
]
GROUP_RULES = [(name, re.compile(rx, re.I)) for name, rx in GROUP_RULES]
OTHER = "Other / unclassified"


def group_of(title: str) -> str:
    for name, rx in GROUP_RULES:
        if rx.search(title):
            return name
    return OTHER


# ---------------------------------------------------------------- extract
def extract(dataset_id: str, first_year: int, last_year: int) -> list:
    """Run ONE SoQL query on the unified dataset, filtered to a year range.

    Socrata caps a response at 1,000 rows, so the same query is paged with
    $limit and $offset. The year column is text, so the filter lists the years.
    """
    headers = {}
    if os.environ.get("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
    years = ", ".join(f"'{y}'" for y in range(first_year, last_year + 1))
    where = f"year in ({years})"
    rows, offset = [], 0
    while True:
        resp = requests.get(
            URL.format(id=dataset_id),
            headers=headers,
            timeout=60,
            params={"$where": where, "$limit": PAGE, "$offset": offset, "$order": ":id"},
        )
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / RAW_FILE).write_text(json.dumps(rows))
    print(f"  {len(rows):,} rows downloaded where {where}")
    return rows


# -------------------------------------------------------------- transform
def transform(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows).rename(columns={
        "position_title": "title",
        "minimum_annual_base_rate": "min_rate",
        "maximum_annual_base_rate": "max_rate",
    })[["year", "title", "min_rate", "max_rate"]]
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)  # text in the source

    df["title"] = df["title"].astype(str).str.strip()
    for col in ("min_rate", "max_rate"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["midpoint"] = (df["min_rate"] + df["max_rate"]) / 2
    df["single_rate"] = df["min_rate"] == df["max_rate"]
    df["spread_pct"] = (df["max_rate"] / df["min_rate"] - 1) * 100
    df["role_group"] = df["title"].map(group_of)
    return df


def validate(df: pd.DataFrame) -> None:
    assert df[["title", "min_rate", "max_rate"]].notna().all().all(), "missing or non-numeric values"
    assert (df["min_rate"] <= df["max_rate"]).all(), "a minimum rate is above its maximum"
    counts = df.groupby("year").size()
    print("Rows per year:", counts.to_dict())
    for year, n in counts.items():
        if year in EXPECTED and n != EXPECTED[year]:
            print(f"  warning: {year} has {n:,} rows, expected {EXPECTED[year]:,}")
    dupes = df[df.duplicated(["year", "title"], keep=False)]
    if len(dupes):
        print(f"  note: {len(dupes)} rows share a title within a year")


# ------------------------------------------------------------------- load
def load(df: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "compensation_all_years.csv", index=False)
    df.to_parquet(OUT / "compensation_all_years.parquet", index=False)

    # Pivot: one row per role group and year
    pivot = (
        df.groupby(["role_group", "year"])
        .agg(roles=("title", "size"),
             avg_min=("min_rate", "mean"),
             avg_max=("max_rate", "mean"),
             median_midpoint=("midpoint", "median"))
        .round(0)
        .reset_index()
    )
    pivot.to_csv(OUT / "group_pivot.csv", index=False)

    # Change in the maximum rate for titles that appear in consecutive years
    first = df.drop_duplicates(["year", "title"])
    wide = first.pivot(index="title", columns="year", values="max_rate")
    pairs = []
    years = sorted(wide.columns)
    for a, b in zip(years, years[1:]):
        both = wide[[a, b]].dropna()
        pct = (both[b] / both[a] - 1) * 100
        pairs.append(pd.DataFrame({"title": both.index, "from_year": a, "to_year": b, "max_rate_change_pct": pct.values}))
    if pairs:
        pd.concat(pairs).to_csv(OUT / "matched_changes.csv", index=False)
    print(f"Wrote {len(df):,} rows and summary tables to {OUT}")


def get_dataframe(offline: bool = False) -> pd.DataFrame:
    """Extract (one query), transform and validate. Returns the analysis DataFrame."""
    cfg = yaml.safe_load((ROOT / "datasets.yml").read_text())
    if offline:
        rows = json.loads((RAW / RAW_FILE).read_text())
    else:
        rows = extract(cfg["dataset"], int(cfg["first_year"]), int(cfg["last_year"]))
    df = transform(rows)
    validate(df)
    return df


def main() -> None:
    df = get_dataframe(offline="--offline" in sys.argv)
    load(df)


if __name__ == "__main__":
    main()
