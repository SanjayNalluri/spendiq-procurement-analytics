"""
Step 0 - Look at the raw USAID SCMS shipment pricing data before cleaning anything.

Input : data/raw/scms_delivery_history.csv  (USAID, Supply Chain Shipment Pricing Data)
Usage : python src/step0_inspect.py
Prints: size, every column with type / missing / examples, and the messy text values hiding in
        number columns (freight, weight, insurance), which step 1 will have to handle.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "scms_delivery_history.csv"

df = pd.read_csv(RAW, low_memory=False)
pd.set_option("display.width", 200, "display.max_colwidth", 60)
print(f"Rows: {len(df):,}   Columns: {df.shape[1]}\n")

print("Columns (type, % missing, distinct values, 3 examples):")
for c in df.columns:
    s = df[c]
    ex = " | ".join(map(str, s.dropna().astype(str).unique()[:3]))
    print(f"  {c:38s} {str(s.dtype):8s} {100 * s.isna().mean():5.1f}%  {s.nunique():>6,}  {ex[:90]}")

print("\nText hiding in number-like columns (top values that are not numbers):")
for c in df.columns:
    if any(k in c.lower() for k in ["freight", "weight", "insurance", "price", "value", "quantity"]):
        s = df[c].astype(str)
        bad = s[pd.to_numeric(s.str.replace(",", ""), errors="coerce").isna() & df[c].notna()]
        if len(bad):
            print(f"  {c}: {len(bad):,} rows, e.g.")
            for v, n in bad.str.replace(r"\d+", "#", regex=True).value_counts().head(5).items():
                print(f"      {n:>6,}  {v[:80]}")

print("\nDate-like columns (first 3 raw values):")
for c in df.columns:
    if "date" in c.lower():
        print(f"  {c}: {df[c].dropna().astype(str).head(3).tolist()}   non-dates e.g. "
              f"{df[c][pd.to_datetime(df[c], errors='coerce').isna() & df[c].notna()].astype(str).unique()[:3].tolist()}")

for c in ["Vendor", "Product Group", "Country", "Shipment Mode", "Fulfill Via", "Vendor INCO Term"]:
    if c in df.columns:
        print(f"\nTop values of {c}:")
        print(df[c].value_counts().head(8).to_string())
