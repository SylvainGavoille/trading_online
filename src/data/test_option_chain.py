"""
End-to-end test for option snapshot collection (no reqSecDefOptParams).
Tests spot price fetch + calculated chain + snapshot for NVDA.

Run: uv run python src/data/test_option_chain.py
"""

import sys
import time
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import yaml
from src.api.ib_connector import IBClient
from src.data.collect_options_snapshot import (
    build_option_contract,
    calc_expirations,
    calc_strikes,
    get_spot_price,
    load_config,
)

CONFIG_PATH = _ROOT / "src" / "config" / "config.yaml"

# Try client IDs 12-19 to avoid collision with dashboard (10) and collector (11)
raw_cfg = yaml.safe_load(open(CONFIG_PATH))
ib = None
for cid in range(12, 20):
    raw_cfg["api"]["client_id"] = cid
    candidate = IBClient(raw_cfg)
    if candidate.connect_and_run():
        ib = candidate
        print(f"Connected with client_id={cid}")
        break
    print(f"client_id={cid} in use, trying next...")

if ib is None:
    print("ERROR: could not connect on any client ID")
    sys.exit(1)

time.sleep(1)

cfg = load_config()
today = date.today()
SYMBOL = "NVDA"

print(f"\n=== Spot price for {SYMBOL} ===")
spot = get_spot_price(ib, SYMBOL)
print(f"spot = {spot}")
if not spot:
    print("ERROR: no spot price")
    ib.disconnect()
    sys.exit(1)

print(
    f"\n=== Calculated chain (DTE {cfg['dte_min']}-{cfg['dte_max']}, moneyness +-{cfg['moneyness_range']*100:.0f}%) ==="
)
expirations = calc_expirations(
    today, cfg["dte_min"], cfg["dte_max"], cfg["max_expirations"]
)
strikes = calc_strikes(spot, cfg["moneyness_range"])
print(f"Expirations ({len(expirations)}): {expirations}")
print(f"Strikes ({len(strikes)}): {strikes}")
total_contracts = len(expirations) * len(strikes) * 2
print(f"Total contracts to test: {total_contracts}")

print(f"\n=== Snapshot test (3 contracts) ===")
# ATM call, ATM put, one OTM call
atm_strike = strikes[len(strikes) // 2]
test_cases = [
    (expirations[0], atm_strike, "C"),
    (expirations[0], atm_strike, "P"),
    (expirations[0], strikes[-2] if len(strikes) >= 2 else atm_strike, "C"),
]

ok_count = 0
for exp, strike, right in test_cases:
    c = build_option_contract(SYMBOL, exp, strike, right)
    data = ib.get_option_snapshot(c, timeout=10.0)
    bid = data.get("bid")
    ask = data.get("ask")
    iv = data.get("iv")
    delta = data.get("delta")
    has_data = any(v is not None and v != 0 for v in [bid, ask, iv, delta])
    if has_data:
        ok_count += 1
    iv_str = f"{iv:.4f}" if iv is not None else "None"
    delta_str = f"{delta:.4f}" if delta is not None else "None"
    status = "OK" if has_data else "EMPTY"
    print(
        f"  [{status}] {SYMBOL} {exp} {strike} {right}: "
        f"bid={bid} ask={ask} iv={iv_str} delta={delta_str}"
    )

print(f"\n=== Result: {ok_count}/{len(test_cases)} snapshots had data ===")
ib.disconnect()
print("Done.")
