"""
Step 6 - Freight check and charts for the README.

Freight as % of line value, by shipment mode, uses only lines whose freight is a real number
(not "see another line" or "included in price").
Outputs: outputs/freight_by_mode.csv, outputs/charts/*.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from common import OUT, RDC, load_clean  # noqa: E402

BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
INK, INK2, GRID, BG = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
CHARTS = OUT / "charts"


def style(ax, title, xlabel=""):
    ax.set_facecolor(BG)
    ax.figure.set_facecolor(BG)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.set_xlabel(xlabel, color=INK2)
    ax.tick_params(colors=INK2, length=0)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def short(name, n=28):
    name = name.split(" (FORMERLY")[0].split(" (FORMALLY")[0]
    return name if len(name) <= n else name[: n - 1] + "…"


def freight_by_mode(df):
    d = df[(df["freight_status"] == "number") & (df["Line Item Value"] > 0) & df["Shipment Mode"].notna()].copy()
    d["freight_pct"] = 100 * d["freight_usd"] / d["Line Item Value"]
    t = d.groupby("Shipment Mode").agg(lines=("ID", "size"),
                                       freight_musd=("freight_usd", lambda x: round(x.sum() / 1e6, 2)),
                                       value_musd=("Line Item Value", lambda x: round(x.sum() / 1e6, 2)),
                                       median_freight_pct=("freight_pct", lambda x: round(x.median(), 1)))
    t["freight_pct_of_value"] = (100 * t["freight_musd"] / t["value_musd"]).round(1)
    return t.sort_values("freight_pct_of_value", ascending=False)


if __name__ == "__main__":
    CHARTS.mkdir(parents=True, exist_ok=True)
    df = load_clean()

    fm = freight_by_mode(df)
    fm.to_csv(OUT / "freight_by_mode.csv")
    print("--- Freight cost by shipment mode (lines with a freight number) ---")
    print(fm.to_string(), "\n")

    # 1. supplier Pareto
    v = pd.read_csv(OUT / "spend_by_vendor.csv", index_col=0).head(10)[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.barh([short(n) for n in v.index], v["spend_musd"], color=BLUE, height=0.6)
    for y, (val, cum) in enumerate(zip(v["spend_musd"], v["cum_%"])):
        ax.text(val + 2, y, f"${val:.0f}M  (cum. {cum:.0f}%)", va="center", fontsize=8.5, color=INK2)
    style(ax, "Top 10 suppliers by direct spend, 2006-2015 ($M)")
    ax.set_xlim(0, v["spend_musd"].max() * 1.35)
    fig.tight_layout()
    fig.savefig(CHARTS / "1_supplier_pareto.png", dpi=150)

    # 2. scorecard: price vs on-time
    s = pd.read_csv(OUT / "supplier_scorecard.csv", index_col=0)
    flag = (s["spend_musd"] >= 20) & (s["on_time_pct"] < 90)
    fig, ax = plt.subplots(figsize=(8, 5))
    for mask, color, label in [(~flag, BLUE, "Other suppliers"), (flag, ORANGE, "$20M+ and below 90% on-time")]:
        ax.scatter(s.loc[mask, "price_vs_median_pct"], s.loc[mask, "on_time_pct"],
                   s=20 + s.loc[mask, "spend_musd"] * 4, color=color, alpha=0.85,
                   edgecolor=BG, linewidth=1.5, label=label)
    offsets = {"MYLAN": (10, 6), "HETERO": (10, -12), "Trinity": (8, 10), "Orgenics": (14, 4),
               "CIPLA": (12, -10), "Aurobindo": (12, -4), "PHARMACY": (-10, -14), "Hoffmann": (6, 6)}
    for name, r in s[(s["spend_musd"] >= 20) | (s["price_vs_median_pct"] > 30)].iterrows():
        off = next((o for k, o in offsets.items() if name.startswith(k)), (6, 4))
        ax.annotate(short(name, 22), (r["price_vs_median_pct"], r["on_time_pct"]), fontsize=8, color=INK2,
                    xytext=off, textcoords="offset points", ha="right" if off[0] < 0 else "left")
    style(ax, "Supplier scorecard: price vs delivery (bubble = spend)", "Average price vs item median that year (%)")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_ylabel("On-time delivery (%)", color=INK2)
    ax.legend(frameon=False, fontsize=8.5, loc="center right", markerscale=0.5)
    fig.tight_layout()
    fig.savefig(CHARTS / "2_supplier_scorecard.png", dpi=150)

    # 3. freight % by mode
    fig, ax = plt.subplots(figsize=(7, 3.2))
    f = fm[::-1]
    ax.barh(f.index, f["freight_pct_of_value"], color=BLUE, height=0.55)
    for y, val in enumerate(f["freight_pct_of_value"]):
        ax.text(val + 0.3, y, f"{val:.1f}%", va="center", fontsize=9, color=INK2)
    style(ax, "Freight cost as % of goods value, by shipment mode")
    fig.tight_layout()
    fig.savefig(CHARTS / "3_freight_by_mode.png", dpi=150)

    # 4. allocation: spend change per supplier
    a = pd.read_csv(OUT / "allocation.csv")
    c = a.groupby("Vendor")[["value", "new_value"]].sum()
    c = ((c["new_value"] - c["value"]) / 1e6).round(2)
    c = c[c.abs() >= 0.05].sort_values()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh([short(n) for n in c.index], c.values, color=[RED if x < 0 else BLUE for x in c.values], height=0.6)
    ax.axvline(0, color=INK2, linewidth=0.8)
    for y, val in enumerate(c.values):
        ax.text(val + (0.1 if val >= 0 else -0.1), y, f"{val:+.2f}", va="center",
                ha="left" if val >= 0 else "right", fontsize=8.5, color=INK2)
    style(ax, "Optimised allocation, 2013-2015: change in spend per supplier ($M)")
    ax.set_xlim(c.min() * 1.3, c.max() * 1.4)
    fig.tight_layout()
    fig.savefig(CHARTS / "4_allocation_shift.png", dpi=150)
    print(f"Charts saved to {CHARTS.relative_to(OUT.parent)}")
