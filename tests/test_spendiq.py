"""Small hand-made data, so the tests run without the USAID file."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from step1_clean import clean, split_text_number  # noqa: E402
from step2_spend import n_for_share, spend_by  # noqa: E402
from step3_price_variance import price_lines  # noqa: E402
from step4_scorecard import on_time_score, price_score  # noqa: E402
from step5_allocation import check, solve  # noqa: E402


def test_freight_text_is_classified():
    s = pd.Series(["120.5", "See DN-304 (ID#:10589)", "Freight Included in Commodity Cost",
                   "Invoiced Separately", None])
    num, status, ref = split_text_number(s)
    assert num[0] == 120.5 and num[1:].isna().all()
    assert list(status) == ["number", "on another line", "included in price", "billed/recorded separately", "missing"]
    assert ref[1] == 10589 and ref.drop(1).isna().all()


def test_missing_date_is_unknown_not_late():
    raw = pd.DataFrame({
        "Scheduled Delivery Date": ["2-Jun-06", "2-Jun-06", "2-Jun-06", None],
        "Delivered to Client Date": ["1-Jun-06", "5-Jun-06", "Date Not Captured", "5-Jun-06"],
        "Delivery Recorded Date": "5-Jun-06", "PQ First Sent to Client Date": "Pre-PQ Process",
        "PO Sent to Vendor Date": "5/1/06", "Freight Cost (USD)": "10", "Weight (Kilograms)": "5"})
    d = clean(raw)
    assert d["on_time"].iloc[0] == 1 and d["on_time"].iloc[1] == 0      # early = on time, 3 days late = late
    assert d["on_time"].iloc[2:].isna().all()                           # missing date = unknown
    assert d["on_time"].mean() == 0.5                                   # unknown lines don't count as late


def test_pareto_count():
    df = pd.DataFrame({"Vendor": list("ABCD"), "Line Item Value": [70, 15, 10, 5]})
    t = spend_by(df, "Vendor")
    assert list(t.index) == list("ABCD") and n_for_share(t, 80) == 2


def test_price_lines_drop_bad_prices_and_benchmark():
    df = pd.DataFrame({"Item Description": "X", "year": 2014, "Line Item Quantity": 10,
                       "Pack Price": [0.01, 4, 4, 4, 5, 6, 8], "Line Item Value": 1, "Vendor": "V"})
    d, n_bad = price_lines(df)
    assert n_bad == 1 and len(d) == 6
    assert d["p25_price"].iloc[0] == 4.0
    assert d["overpay_usd"].sum() == (1 + 2 + 4) * 10          # (5-4)+(6-4)+(8-4), times 10 packs


def test_score_scales():
    assert list(price_score(pd.Series([-15, -10, 10, 30, 50]))) == [1, 1, 0.5, 0, 0]
    assert list(on_time_score(pd.Series([100, 90, 80, 70]))) == [1, 0.5, 0, 0]


def options():
    return pd.DataFrame({"item": ["A", "A"], "Vendor": ["cheap", "dear"], "qty": [50.0, 50.0],
                         "value": [50.0, 100.0], "price": [1.0, 2.0], "on_time": [0.9, 0.9], "share": [0.5, 0.5]})


def test_allocation_moves_volume_to_cheaper_supplier():
    r, status = solve(options(), capacity=1.5, max_share=0.7)
    assert status == "Optimal" and check(r, capacity=1.5, max_share=0.7) == []
    assert abs(r["new_qty"].sum() - 100) < 1e-6                  # demand met
    assert abs(r.loc[0, "new_qty"] - 70) < 1e-6                  # cheap supplier up to the 70% share cap


def test_allocation_without_spare_capacity_changes_nothing():
    r, status = solve(options(), capacity=1.0)
    assert status == "Optimal" and abs(r["new_value"].sum() - 150) < 1e-6


def test_on_time_floor_is_respected():
    g = options()
    g["on_time"] = [0.5, 1.0]                                     # cheap but late
    r, _ = solve(g, capacity=2.0, max_share=1.0)
    assert (r["on_time"] * r["new_qty"]).sum() >= (g["on_time"] * g["qty"]).sum() - 1e-6
    assert abs(r.loc[0, "new_qty"] - 50) < 1e-6                  # can't shift to the late supplier


def test_per_item_rule_protects_each_item():
    # item A: cheap supplier is late; item B: cheap supplier is on time.
    g = pd.DataFrame({"item": ["A", "A", "B", "B"], "Vendor": ["a1", "a2", "b1", "b2"],
                      "qty": [50.0, 50.0, 50.0, 50.0], "price": [1.0, 2.0, 1.0, 2.0],
                      "on_time": [0.5, 1.0, 1.0, 0.5], "share": 0.5})
    overall, _ = solve(g, capacity=2.0, max_share=1.0)
    item, _ = solve(g, capacity=2.0, max_share=1.0, per_item=True)
    assert check(overall, capacity=2.0, max_share=1.0) == []
    assert check(item, capacity=2.0, max_share=1.0, per_item=True) == []
    # overall rule lets item A get worse (B's gain pays for it); per-item rule does not
    a = lambda r: (r["on_time"] * r["new_qty"])[r["item"] == "A"].sum()
    assert a(overall) < 75 - 1e-6 and a(item) >= 75 - 1e-6
    assert (item["price"] * item["new_qty"]).sum() >= (overall["price"] * overall["new_qty"]).sum() - 1e-6


def test_check_catches_a_broken_solution():
    r = options()
    r["new_qty"] = [90.0, 0.0]                                    # demand short by 10, over 1.5x capacity
    bad = check(r)
    assert any("demand" in b for b in bad) and any("capacity" in b for b in bad)
