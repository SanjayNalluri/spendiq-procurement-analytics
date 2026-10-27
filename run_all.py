"""Run every step in order: python run_all.py"""
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
for step in ["step1_clean", "step2_spend", "step3_price_variance", "step4_scorecard",
             "step5_allocation", "step6_report"]:
    print(f"\n===== {step} =====", flush=True)
    subprocess.run([sys.executable, str(SRC / f"{step}.py")], check=True, cwd=SRC)
