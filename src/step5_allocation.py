"""
Step 5 - Optimal supplier allocation (linear program, PuLP: CBC solver on PuLP 3, HiGHS on PuLP 4).

Question: for items that 2+ suppliers already sold to SCMS (2013-2015, direct orders), could the same
quantities have been split between those suppliers more cheaply, without worse delivery?

  minimise    sum  price[i,s] * x[i,s]
  subject to  sum_s x[i,s] = demand[i]                      every item's quantity is met
              0 <= x[i,s] <= 1.5 * actual[i,s]              capacity: at most 1.5x what s really supplied
              x[i,s] <= max(70%, actual share) * demand[i]  no new single-sourcing above 70%
              sum on_time[s,i] * x[i,s] >= actual on-time   overall on-time rate no worse than reality

price = what that supplier actually charged for that item (value / quantity over the window).
The actual split satisfies every constraint, so the optimum can only match or beat reality.
Limits: prices differ partly by order size, destination and INCO term, which the model does not see.
Output: outputs/allocation.csv
"""
import pandas as pd
import pulp

from common import OUT, RDC, load_clean

YEARS = (2013, 2015)
CAPACITY = 1.5
MAX_SHARE = 0.7


def options(df: pd.DataFrame, years=YEARS, min_lines: int = 3) -> pd.DataFrame:
    d = df[(df["Vendor"] != RDC) & df["year"].between(*years)
           & (df["Line Item Quantity"] > 0) & (df["Line Item Value"] > 0)]
    g = d.groupby(["Item Description", "Vendor"]).agg(
        qty=("Line Item Quantity", "sum"), value=("Line Item Value", "sum"),
        lines=("ID", "size"), on_time=("on_time", "mean")).reset_index()
    g = g.rename(columns={"Item Description": "item"})
    g = g[g["lines"] >= min_lines]
    g = g[g.groupby("item")["Vendor"].transform("size") >= 2].reset_index(drop=True)
    g["price"] = g["value"] / g["qty"]
    g["share"] = g["qty"] / g.groupby("item")["qty"].transform("sum")
    return g


def solve(g: pd.DataFrame, capacity=CAPACITY, max_share=MAX_SHARE) -> tuple[pd.DataFrame, str]:
    demand = g.groupby("item")["qty"].sum()      # plain floats below: PuLP 4 rejects numpy numbers in constraints
    m = pulp.LpProblem("supplier_allocation", pulp.LpMinimize)
    # PuLP 4 creates variables through the problem; older versions use LpVariable directly
    var = m.add_variable if hasattr(m, "add_variable") else pulp.LpVariable
    x = {i: var(f"x{i}", lowBound=0, upBound=float(capacity * g.at[i, "qty"])) for i in g.index}   # capacity
    m += pulp.lpSum(float(g.at[i, "price"]) * x[i] for i in g.index)
    for item, grp in g.groupby("item"):
        m += pulp.lpSum(x[i] for i in grp.index) == float(demand[item])
        for i in grp.index:
            m += x[i] <= float(max(max_share, g.at[i, "share"]) * demand[item])
    target = (g["on_time"] * g["qty"]).sum() * (1 - 1e-9)          # tiny tolerance for rounding
    m += pulp.lpSum(float(g.at[i, "on_time"]) * x[i] for i in g.index) >= float(target)
    # PuLP 3 ships the CBC solver, PuLP 4 ships HiGHS
    res = m.solve(pulp.PULP_CBC_CMD(msg=False) if hasattr(pulp, "PULP_CBC_CMD") else pulp.HiGHS(msg=False))
    status = res.status.name if hasattr(res, "status") else pulp.LpStatus[res]    # PuLP 4 / PuLP 3
    out = g.copy()
    out["new_qty"] = [max(0.0, x[i].value() or 0.0) for i in g.index]
    out["new_value"] = out["price"] * out["new_qty"]
    return out, status


if __name__ == "__main__":
    g = options(load_clean())
    print(f"Items with 2+ suppliers: {g['item'].nunique()}, supplier options: {len(g)}, "
          f"spend ${g['value'].sum()/1e6:,.1f}M ({YEARS[0]}-{YEARS[1]}, direct orders)")
    r, status = solve(g)
    print(f"Solver status: {status}\n")

    actual, new = r["value"].sum(), r["new_value"].sum()
    ot, new_ot = (r["on_time"] * r["qty"]).sum() / r["qty"].sum(), (r["on_time"] * r["new_qty"]).sum() / r["qty"].sum()
    print(f"Actual cost    ${actual/1e6:,.2f}M   on-time {100*ot:.1f}%")
    print(f"Optimised cost ${new/1e6:,.2f}M   on-time {100*new_ot:.1f}%")
    print(f"Saving         ${(actual-new)/1e6:,.2f}M ({100*(actual-new)/actual:.1f}%)\n")

    pd.set_option("display.width", 200, "display.max_colwidth", 50)
    v = r.groupby("Vendor")[["value", "new_value"]].sum().div(1e6).round(2)
    v["change_musd"] = (v["new_value"] - v["value"]).round(2)
    v = v[v["change_musd"].abs() >= 0.01].sort_values("change_musd")
    print("--- Suppliers whose spend changes ($M) ---")
    print(v.to_string(), "\n")

    it = r.groupby("item")[["value", "new_value"]].sum()
    it["saving_musd"] = ((it["value"] - it["new_value"]) / 1e6).round(2)
    print("--- Top 10 items by saving ---")
    print(it.sort_values("saving_musd", ascending=False)["saving_musd"].head(10).to_string())

    # sensitivity: how much depends on the capacity assumption
    print("\n--- Sensitivity: saving vs capacity limit ---")
    for cap in [1.0, 1.25, 1.5, 2.0]:
        rr, st = solve(g, capacity=cap)
        print(f"  capacity {cap:.2f}x actual: saving ${(actual - rr['new_value'].sum())/1e6:,.2f}M ({st})")
    r.to_csv(OUT / "allocation.csv", index=False)
