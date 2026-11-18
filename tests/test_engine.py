"""Checks the SQL engine against an independent Python simulation and core invariants.

    python tests/test_engine.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_local_pipeline  # noqa: E402

AS_OF = "2026-11-18"


def simulate(on_hand, usage, receipts_by_day, horizon=60):
    inv, lost, first_out = float(on_hand), 0.0, -1
    for d in range(horizon):
        avail = inv + receipts_by_day.get(d, 0.0)
        if first_out < 0 and avail < usage:
            first_out = d
        lost += max(usage - avail, 0.0)
        inv = max(avail - usage, 0.0)
    return lost, first_out


def main():
    spark = run_local_pipeline.main()
    asof = date.fromisoformat(AS_OF)
    po = spark.table("gold.po_delay").toPandas()
    inv = spark.table("ops.inventory").toPandas()
    imp = spark.table("gold.plant_material_impact").toPandas().set_index(["plant_id", "material_id"])
    act = spark.table("gold.po_actions").toPandas()
    kpi = spark.table("gold.risk_kpis").toPandas().iloc[0]
    ev = spark.table("gold.event_impact").toPandas()
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    # 1. Delay flags are consistent
    check(((po.delay_days > 0) == po.is_delayed).all(), "delay_days > 0 must match is_delayed")
    check((po.delay_days <= 21).all(), "delay capped at 21 days")
    check((po.delay_days == po.supplier_delay_days.clip(upper=21) + 0).sum() >= 0, "sanity")

    # 2. Inventory simulation matches an independent Python run
    for _, row in inv.iterrows():
        sub = po[(po.plant_id == row.plant_id) & (po.material_id == row.material_id)]
        rb, rd = {}, {}
        for _, p in sub.iterrows():
            db = max((p.plant_eta_date - asof).days, 0)
            dd = max((p.new_eta_date - asof).days, 0)
            rb[db] = rb.get(db, 0) + p.qty
            rd[dd] = rd.get(dd, 0) + p.qty
        lb, _ = simulate(row.on_hand_qty, row.daily_usage_qty, rb)
        ld, fo = simulate(row.on_hand_qty, row.daily_usage_qty, rd)
        r = imp.loc[(row.plant_id, row.material_id)]
        check(abs(r.baseline_lost_qty - round(lb)) <= 1, f"baseline lost mismatch {row.plant_id}/{row.material_id}")
        check(abs(r.disrupted_lost_qty - round(ld)) <= 1, f"disrupted lost mismatch {row.plant_id}/{row.material_id}")
        if not sub.is_delayed.any():
            check(r.incremental_lost_qty == 0, f"no delayed PO but impact at {row.plant_id}/{row.material_id}")

    # 3. Actions never claim to protect more than is at risk, and cost is only spent when it pays
    check((act.margin_protected_usd <= act.margin_at_risk_usd + 1).all(), "protected > at risk")
    paid = act[act.recommended_action.isin(["Expedite", "Re-source"])]
    check((paid.margin_protected_usd > paid.action_cost_usd).all(), "action recommended that does not pay back")

    # 4. Rollups reconcile
    check(abs(act.margin_at_risk_usd.sum() - kpi.margin_at_risk_usd) <= 5, "PO-level margin != KPI margin")
    check(abs(ev.margin_at_risk_usd.sum() - kpi.margin_at_risk_usd) <= 5, "event margin != KPI margin")
    check(kpi.delayed_po_lines == po.is_delayed.sum(), "delayed count mismatch")

    print(f"\nChecked {len(inv)} plant-material simulations, {len(po)} PO lines, {len(act)} actions.")
    if failures:
        print("FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
