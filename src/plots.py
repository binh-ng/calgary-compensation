"""Build interactive Plotly charts from data/processed into site/plots/ (standalone HTML files)."""
from pathlib import Path

import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "plots"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "data" / "processed" / "compensation_all_years.csv")
changes = pd.read_csv(ROOT / "data" / "processed" / "matched_changes.csv")
pivot = pd.read_csv(ROOT / "data" / "processed" / "group_pivot.csv")

df["year"] = df["year"].astype(str)
pivot["year"] = pivot["year"].astype(str)
changes["period"] = changes["from_year"].astype(str) + " to " + changes["to_year"].astype(str)
YEAR_ORDER = {"year": sorted(df["year"].unique())}


def save(fig, name, height=520):
    fig.update_layout(height=height, template="plotly_white", margin=dict(t=70, l=20, r=20, b=40))
    fig.write_html(OUT / f"{name}.html", include_plotlyjs="cdn", full_html=True)
    print("wrote", name)


# 1. How many roles sit at each pay level
fig = px.histogram(
    df, x="midpoint", color="year", barmode="overlay", opacity=0.6,
    category_orders=YEAR_ORDER,
    labels={"midpoint": "Range midpoint ($)", "year": "Year"},
    title="Roles by pay-range midpoint ($10k bands)",
)
fig.update_traces(xbins=dict(start=40000, end=210000, size=10000))
fig.update_yaxes(title="Roles")
save(fig, "01_distribution")

# 2. Share of roles in each pay band
bands = pd.cut(df["midpoint"], [0, 60000, 100000, 150000, float("inf")],
               labels=["Under $60k", "$60k to $100k", "$100k to $150k", "$150k and above"], right=False)
share = (df.assign(band=bands).groupby(["year", "band"], observed=False).size()
         .groupby(level=0).transform(lambda s: s / s.sum() * 100).rename("share").reset_index())
fig = px.bar(share, x="share", y="year", color="band", orientation="h", text_auto=".1f",
             category_orders={"year": sorted(df["year"].unique(), reverse=True)},
             labels={"share": "Share of roles (%)", "year": "", "band": "Midpoint band"},
             title="Share of roles by pay band", color_discrete_sequence=px.colors.sequential.Blues[2:])
save(fig, "02_band_mix", height=380)

# 3. Change in the maximum rate for roles on both lists
fig = px.histogram(changes[changes["max_rate_change_pct"].between(-20, 40)],
                   x="max_rate_change_pct", color="period", barmode="group",
                   labels={"max_rate_change_pct": "Change in maximum rate (%)", "period": "Period"},
                   title="Change in the maximum rate, roles on both lists")
fig.update_traces(xbins=dict(start=-20, end=40, size=2))
fig.update_yaxes(title="Roles")
save(fig, "03_ceiling_change")

# 4. Median midpoint by role group
last = pivot["year"].max()
order = pivot[pivot["year"] == last].sort_values("median_midpoint")["role_group"].tolist()
fig = px.bar(pivot, x="median_midpoint", y="role_group", color="year", barmode="group", orientation="h",
             category_orders={"role_group": order, **YEAR_ORDER},
             hover_data={"roles": True, "avg_min": ":,.0f", "avg_max": ":,.0f"},
             labels={"median_midpoint": "Median range midpoint ($)", "role_group": "", "year": "Year"},
             title="Median pay midpoint by role group")
save(fig, "04_role_groups", height=640)

# 5. Explorer: every role, animated by year, hover shows the title
lim_x, lim_y = df["min_rate"].max() * 1.05, df["max_rate"].max() * 1.05
fig = px.scatter(df, x="min_rate", y="max_rate", color="role_group", animation_frame="year",
                 hover_name="title", opacity=0.65, category_orders=YEAR_ORDER,
                 range_x=[0, lim_x], range_y=[0, lim_y],
                 labels={"min_rate": "Minimum rate ($)", "max_rate": "Maximum rate ($)", "role_group": "Role group"},
                 title="Every role: minimum against maximum rate (press play or drag the year slider)")
save(fig, "05_explorer", height=640)
print("done")
