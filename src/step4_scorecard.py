"""
Step 4 - Supplier scorecard (real suppliers with 20+ order lines).

Score (0-100) on fixed, explainable scales, 50/50:
  price   = average % vs the item's median price that year:  -10% or cheaper -> 100,  +30% or worse -> 0
  on-time = % of lines delivered on or before the scheduled date:   100% -> 100,  80% or less -> 0
Lead time and freight % are shown but not scored: they mostly reflect where a product is made and
how it was shipped, not supplier quality. On-time is measured against the delivery to the client, so
it also includes the freight forwarder's part.
Output: outputs/supplier_scorecard.csv
"""
import warnings

import pandas as pd

from common import OUT, PRICE_LINES, RDC, load_clean

warnings.filterwarnings("ignore", category=RuntimeWarning)       # medians of all-blank groups


def price_score(pct_vs_median):
    return ((30 - pct_vs_median) / 40).clip(0, 1).fillna(0.5)


def on_time_score(on_time_pct):
    return ((on_time_pct - 80) / 20).clip(0, 1)


def late_median(x):
    late = x[x > 0]
    return late.median() if len(late) else float("nan")          # NaN = never late


def scorecard(df: pd.DataFrame, price: pd.DataFrame, min_lines: int = 20) -> pd.DataFrame:
    d = df[df["Vendor"] != RDC].merge(price, on="ID", how="left")
    num = (d["freight_status"] == "number") & (d["Line Item Value"] > 0)
    d["freight_pct"] = (100 * d["freight_usd"] / d["Line Item Value"]).where(num)
    s = d.groupby("Vendor").agg(
        lines=("ID", "size"),
        spend_musd=("Line Item Value", lambda x: round(x.sum() / 1e6, 2)),
        countries=("Country", "nunique"),
        on_time_pct=("on_time", lambda x: round(100 * x.mean(), 1)),       # mean skips unknown (NaN) lines
        delivery_known_pct=("on_time", lambda x: round(100 * x.notna().mean(), 1)),
        median_delay_if_late=("delay_days", late_median),
        median_lead_days=("lead_time_days", "median"),
        price_vs_median_pct=("vs_median_%", lambda x: round(x.mean(), 1)),
        freight_pct_of_value=("freight_pct", lambda x: round(x.median(), 1)),
    ).query("lines >= @min_lines")
    p, o = price_score(s["price_vs_median_pct"]), on_time_score(s["on_time_pct"])
    s["price_score"], s["on_time_score"] = (100 * p).round(0), (100 * o).round(0)
    s["score"] = (50 * p + 50 * o).round(1)
    return s.sort_values("score", ascending=False)


if __name__ == "__main__":
    df = load_clean()
    price = pd.read_csv(PRICE_LINES, usecols=["ID", "vs_median_%"])
    s = scorecard(df, price)
    direct = df[df["Vendor"] != RDC]
    direct_m = direct["Line Item Value"].sum() / 1e6

    pd.set_option("display.width", 250, "display.max_colwidth", 35)
    print(f"Suppliers scored: {len(s)} (20+ order lines each), covering "
          f"${s['spend_musd'].sum():,.1f}M of ${direct_m:,.1f}M direct spend\n")
    print(s.to_string())
    s.to_csv(OUT / "supplier_scorecard.csv")

    big_late = s[(s["spend_musd"] >= 20) & (s["on_time_pct"] < 90)]
    print(f"\nLarge suppliers ($20M+) below 90% on-time: {', '.join(big_late.index)}")
    print(f"  ${big_late['spend_musd'].sum():.1f}M = {100*big_late['spend_musd'].sum()/direct_m:.0f}% of direct spend, "
          f"on-time {big_late['on_time_pct'].min()}-{big_late['on_time_pct'].max()}%")
    print(f"SCMS warehouses (RDC) on-time {100*df.loc[df['Vendor'] == RDC, 'on_time'].mean():.1f}%, "
          f"direct suppliers {100*direct['on_time'].mean():.1f}%")
