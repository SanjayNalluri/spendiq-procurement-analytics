"""
Step 3 - Price variance: the same item bought in the same year at different prices.

Benchmark = the item's 25th-percentile pack price that year (a price SCMS already paid on its
cheaper quarter of orders). Lines priced below 20% of the item's median are dropped as data errors
or donations (e.g. $0.01 for a $4.60 item). Needs 5+ purchases of the item that year.
The saving is an upper bound: over-priced lines are mostly small (urgent) orders.
Outputs: outputs/price_variance_items.csv, outputs/price_variance_vendors.csv, data/processed/price_lines.csv
"""
import pandas as pd

from common import OUT, PRICE_LINES, load_clean

KEY = ["Item Description", "year"]


def price_lines(df: pd.DataFrame, min_lines: int = 5) -> tuple[pd.DataFrame, int]:
    d = df[(df["Pack Price"] > 0) & (df["Line Item Quantity"] > 0)].copy()
    d["median_price"] = d.groupby(KEY)["Pack Price"].transform("median")
    bad = d["Pack Price"] < 0.2 * d["median_price"]
    d = d[~bad].copy()
    g = d.groupby(KEY)["Pack Price"]
    d["n_lines"] = g.transform("size")
    d["median_price"] = g.transform("median")
    d["p25_price"] = g.transform(lambda s: s.quantile(0.25))
    d = d[d["n_lines"] >= min_lines].copy()
    d["vs_median_%"] = 100 * (d["Pack Price"] / d["median_price"] - 1)
    d["overpay_usd"] = (d["Pack Price"] - d["p25_price"]).clip(lower=0) * d["Line Item Quantity"]
    return d, int(bad.sum())


if __name__ == "__main__":
    df = load_clean()
    d, n_bad = price_lines(df)
    covered, opp = d["Line Item Value"].sum(), d["overpay_usd"].sum()
    high = d["vs_median_%"] > 20
    print(f"Dropped {n_bad} lines priced below 20% of the item's median (data errors / donations)")
    print(f"Lines compared: {len(d):,} of {len(df):,}  (spend covered ${covered/1e6:,.1f}M of "
          f"${df['Line Item Value'].sum()/1e6:,.1f}M)")
    print(f"Savings if every line paid the item's 25th-percentile price that year: ${opp/1e6:,.1f}M "
          f"({100*opp/covered:.1f}% of covered spend)")
    print(f"Lines priced >20% above the item's median: {high.sum():,}")
    print(f"Median order size (packs): those lines {d.loc[high, 'Line Item Quantity'].median():,.0f} "
          f"vs others {d.loc[~high, 'Line Item Quantity'].median():,.0f}\n")

    pd.set_option("display.width", 200, "display.max_colwidth", 50)
    items = d.groupby("Item Description").agg(
        spend_musd=("Line Item Value", lambda s: round(s.sum() / 1e6, 2)),
        lines=("Pack Price", "size"),
        min_price=("Pack Price", "min"),
        median_price=("Pack Price", "median"),
        max_price=("Pack Price", "max"),
        savings_musd=("overpay_usd", lambda s: round(s.sum() / 1e6, 2)),
    ).sort_values("savings_musd", ascending=False)
    print("--- Top 10 items by savings opportunity ---")
    print(items.head(10).to_string(), "\n")
    items.to_csv(OUT / "price_variance_items.csv")

    v = d.groupby("Vendor").agg(
        lines=("Pack Price", "size"),
        avg_vs_median_pct=("vs_median_%", lambda s: round(s.mean(), 1)),
        pct_lines_above_20=("vs_median_%", lambda s: round(100 * (s > 20).mean(), 1)),
        savings_musd=("overpay_usd", lambda s: round(s.sum() / 1e6, 2)),
    ).query("lines >= 20").sort_values("savings_musd", ascending=False)
    print("--- Vendors (20+ comparable lines) ---")
    print(v.head(10).to_string())
    v.to_csv(OUT / "price_variance_vendors.csv")
    d.to_csv(PRICE_LINES, index=False)
