"""
Step 2 - Spend analysis: where does the money go?

Supplier Pareto uses real suppliers only: "SCMS from RDC" is SCMS's own warehouse (67% of spend),
not a supplier. Other cuts (product, country, mode, fulfilment, year) use all spend.
Outputs: outputs/spend_by_*.csv
"""
import pandas as pd

from common import OUT, RDC, load_clean


def spend_by(data: pd.DataFrame, col: str) -> pd.DataFrame:
    tot = data["Line Item Value"].sum()
    t = data.groupby(col)["Line Item Value"].agg(spend="sum", lines="size").sort_values("spend", ascending=False)
    t["share_%"] = (100 * t["spend"] / tot).round(2)
    t["cum_%"] = t["share_%"].cumsum().round(2)
    t["spend_musd"] = (t["spend"] / 1e6).round(2)
    return t


def n_for_share(t: pd.DataFrame, pct: float = 80) -> int:
    """How many top rows are needed to reach pct% of spend."""
    return int((t["cum_%"] < pct).sum()) + 1


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    df = load_clean()
    total = df["Line Item Value"].sum()
    direct = df[df["Vendor"] != RDC]
    pd.set_option("display.width", 200, "display.max_colwidth", 50)

    print(f"Total spend ${total/1e6:,.1f}M; via SCMS warehouses (RDC) "
          f"${(total - direct['Line Item Value'].sum())/1e6:,.1f}M")
    v = spend_by(direct, "Vendor")
    n80 = n_for_share(v)
    print(f"Direct-from-supplier spend ${direct['Line Item Value'].sum()/1e6:,.1f}M across {len(v)} suppliers")
    print(f"{n80} suppliers ({100*n80/len(v):.1f}%) account for 80% of it\n")
    print(v[["spend_musd", "lines", "share_%", "cum_%"]].head(10).to_string(), "\n")
    v.to_csv(OUT / "spend_by_vendor.csv")

    for col in ["Product Group", "Country", "Shipment Mode", "Fulfill Via"]:
        t = spend_by(df, col)
        print(f"--- {col} ({len(t)} values) ---")
        print(t[["spend_musd", "share_%"]].head(5).to_string(), "\n")
        t.to_csv(OUT / f"spend_by_{col.lower().replace(' ', '_')}.csv")

    y = df.groupby("year")["Line Item Value"].sum().div(1e6).round(1)
    y.to_csv(OUT / "spend_by_year.csv")
    print("--- Spend by year ($M) ---")
    print(y.to_string())
