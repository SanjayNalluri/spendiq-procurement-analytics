"""
Step 1 - Clean the raw SCMS file.

- Dates: two formats in the file ('2-Jun-06' and '11/13/06'); text such as "Date Not Captured",
  "Pre-PQ Process" or "N/A - From RDC" becomes blank (NaT).
- Freight and weight: keep the number, and record WHY it is missing:
    "See DN-304 (ID#:10589)"            -> on another line (the shipment's cost is recorded on line 10589)
    "Freight Included in Commodity Cost" -> included in price
    "Invoiced Separately" / "Weight Captured Separately" -> billed/recorded separately
- Adds delay_days, on_time (1 = delivered on or before the scheduled date, 0 = late, blank = unknown because a
  date is missing; unknown lines are left out of on-time rates, never counted as late),
  lead_time_days (PO sent -> delivered), year.
Output: data/processed/scms_clean.csv
"""
import pandas as pd

from common import CLEAN, RAW


def split_text_number(s: pd.Series):
    """(number, status, referenced line ID) for a column that mixes numbers and notes."""
    txt = s.astype(str)
    num = pd.to_numeric(s, errors="coerce")
    status = pd.Series("number", index=s.index)
    status[txt.str.startswith("See ")] = "on another line"
    status[txt.str.contains("Included in Commodity", na=False)] = "included in price"
    status[txt.str.contains("Invoiced Separately|Captured Separately", na=False)] = "billed/recorded separately"
    status[s.isna()] = "missing"
    ref = txt.str.extract(r"ID#:(\d+)")[0].astype(float)
    return num, status, ref


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["Scheduled Delivery Date", "Delivered to Client Date", "Delivery Recorded Date"]:
        df[c] = pd.to_datetime(df[c], format="%d-%b-%y", errors="coerce")
    for c in ["PQ First Sent to Client Date", "PO Sent to Vendor Date"]:
        df[c] = pd.to_datetime(df[c], format="%m/%d/%y", errors="coerce")

    df["freight_usd"], df["freight_status"], df["freight_ref_id"] = split_text_number(df["Freight Cost (USD)"])
    df["weight_kg"], df["weight_status"], df["weight_ref_id"] = split_text_number(df["Weight (Kilograms)"])

    df["delay_days"] = (df["Delivered to Client Date"] - df["Scheduled Delivery Date"]).dt.days
    known = df["delay_days"].notna()
    df["on_time"] = (df["delay_days"] <= 0).astype(float).where(known)       # NaN = unknown, not late
    df["lead_time_days"] = (df["Delivered to Client Date"] - df["PO Sent to Vendor Date"]).dt.days
    df["year"] = df["Delivered to Client Date"].dt.year
    return df


if __name__ == "__main__":
    df = clean(pd.read_csv(RAW, low_memory=False))
    CLEAN.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN, index=False)

    print(f"Rows: {len(df):,}")
    print("Freight status:\n", df["freight_status"].value_counts().to_string())
    print("\nDates that failed to parse:")
    for c in ["Scheduled Delivery Date", "Delivered to Client Date", "PO Sent to Vendor Date"]:
        print(f"  {c}: {df[c].isna().sum():,}")
    print("  PO date blank, by fulfilment:", df.loc[df["PO Sent to Vendor Date"].isna(), "Fulfill Via"]
          .value_counts().to_dict(), "(From RDC has no supplier PO)")
    print(f"\nYears: {int(df['year'].min())}-{int(df['year'].max())}")
    print(f"Lines with unknown delivery status (a date missing): {df['on_time'].isna().sum():,}")
    print(f"On-time rate: {100*df['on_time'].mean():.1f}% of lines with both dates   "
          f"median delay {df['delay_days'].median()} days")
    print(f"Lead time (PO to delivery), median: {df['lead_time_days'].median()} days, "
          f"rows with it: {df['lead_time_days'].notna().sum():,}")
    print(f"Total spend (Line Item Value): ${df['Line Item Value'].sum():,.0f}")
