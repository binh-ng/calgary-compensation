"""Build a set of portrait infographics (PNG) from data/processed into site/infographics/."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "infographics"
OUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(ROOT / "data" / "processed" / "compensation_all_years.csv")
changes = pd.read_csv(ROOT / "data" / "processed" / "matched_changes.csv")
pivot = pd.read_csv(ROOT / "data" / "processed" / "group_pivot.csv")
years = sorted(df["year"].unique())

BG, INK, MUTED, ACCENT, GREY = "#FAF7F2", "#1F2937", "#6B7280", "#2A78D6", "#C9C5BA"
SOURCE = "Source: City of Calgary Open Data, Compensation Disclosure Lists. Base pay ranges for position titles; police and seasonal staff are not on the list."


def canvas(title, subtitle):
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
    fig.text(0.07, 0.94, title, fontsize=34, fontweight="bold", color=INK, va="top", wrap=True)
    fig.text(0.07, 0.855, subtitle, fontsize=17, color=MUTED, va="top", wrap=True)
    fig.text(0.07, 0.03, SOURCE, fontsize=10, color=MUTED, va="bottom", wrap=True)
    return fig


def style(ax):
    ax.set_facecolor(BG)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=MUTED, length=0, labelsize=14)


def save(fig, name):
    fig.savefig(OUT / name, facecolor=BG)
    plt.close(fig)
    print("wrote", name)


# 1. The typical role's pay midpoint, year by year
med = df.groupby("year")["midpoint"].median()
fig = canvas("What the typical Calgary role pays", f"Median pay-range midpoint, {years[0]} to {years[-1]}")
for i, y in enumerate(years):
    x = 0.07 + i * (0.86 / len(years))
    fig.text(x, 0.74, str(y), fontsize=18, color=MUTED)
    fig.text(x, 0.69, f"${med[y] / 1000:,.0f}k", fontsize=40, fontweight="bold",
             color=ACCENT if y == years[-1] else INK)
ax = fig.add_axes([0.1, 0.12, 0.8, 0.42])
style(ax)
ax.plot(years, med.values, color=ACCENT, lw=4, marker="o", ms=12)
ax.set_xticks(years)
ax.set_ylim(med.min() * 0.9, med.max() * 1.05)
ax.yaxis.set_major_formatter(lambda v, _: f"${v / 1000:,.0f}k")
fig.text(0.07, 0.58, f"Up {(med.iloc[-1] / med.iloc[0] - 1) * 100:.1f}% in {len(years) - 1} years", fontsize=22, color=INK)
save(fig, "01_median_over_time.png")

# 2. Share of roles at the top of the scale
top = df.assign(top=df["midpoint"] >= 150000).groupby("year")["top"].mean() * 100
fig = canvas("More roles at the top of the pay scale", "Share of roles with a pay-range midpoint of $150,000 or more")
ax = fig.add_axes([0.1, 0.12, 0.8, 0.6])
style(ax)
bars = ax.bar([str(y) for y in years], top.values, color=[ACCENT if y == years[-1] else GREY for y in years], width=0.55)
for b, v in zip(bars, top.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f"{v:.1f}%", ha="center", fontsize=24, fontweight="bold", color=INK)
ax.set_yticks([])
ax.set_ylim(0, top.max() * 1.2)
save(fig, "02_share_150k.png")

# 3. Which role groups moved most
first, last = years[0], years[-1]
wide = pivot.pivot(index="role_group", columns="year", values="median_midpoint")
chg = ((wide[last] / wide[first] - 1) * 100).dropna().sort_values()
fig = canvas("Where pay ranges moved most", f"Change in median pay midpoint by role group, {first} to {last}")
ax = fig.add_axes([0.42, 0.1, 0.5, 0.68])
style(ax)
colors = [ACCENT if i >= len(chg) - 2 else GREY for i in range(len(chg))]  # highlight the top two
ax.barh(chg.index, chg.values, color=colors, height=0.65)
pad = max(abs(chg).max(), 1) * 0.02
for i, v in enumerate(chg.values):
    ax.text(max(v, 0) + pad, i, f"{v:+.1f}%", va="center", ha="left", fontsize=15, color=INK)  # right of zero, clear of the names
ax.axvline(0, color=GREY, lw=1)
ax.set_xticks([])
ax.set_xlim(min(0, chg.min()) * 1.35, max(0, chg.max()) * 1.25)
ax.tick_params(axis="y", labelsize=13, colors=INK)
save(fig, "03_role_groups.png")

# 4. How many roles got a big ceiling increase
changes["period"] = changes["from_year"].astype(str) + " to " + changes["to_year"].astype(str)
big = changes.assign(big=changes["max_rate_change_pct"] > 10).groupby("period")["big"].mean() * 100
fig = canvas("Big raises to pay ceilings", "Share of roles on both lists whose maximum rate rose more than 10%")
ax = fig.add_axes([0.1, 0.12, 0.8, 0.6])
style(ax)
bars = ax.bar(big.index, big.values, color=[ACCENT if p == big.index[-1] else GREY for p in big.index], width=0.55)
for b, v in zip(bars, big.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f}%", ha="center", fontsize=24, fontweight="bold", color=INK)
ax.set_yticks([])
ax.set_ylim(0, max(big.max() * 1.2, 1))
save(fig, "04_big_raises.png")
print("done")
