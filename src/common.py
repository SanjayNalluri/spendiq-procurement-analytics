"""Shared paths and loaders."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "scms_delivery_history.csv"
CLEAN = ROOT / "data" / "processed" / "scms_clean.csv"
PRICE_LINES = ROOT / "data" / "processed" / "price_lines.csv"
OUT = ROOT / "outputs"
RDC = "SCMS from RDC"          # SCMS's own regional warehouse, not a supplier

DATE_COLS = ["Scheduled Delivery Date", "Delivered to Client Date", "Delivery Recorded Date",
             "PQ First Sent to Client Date", "PO Sent to Vendor Date"]


def load_clean() -> pd.DataFrame:
    return pd.read_csv(CLEAN, low_memory=False, parse_dates=DATE_COLS)
