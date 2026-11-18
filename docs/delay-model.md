# How disruption turns into delay, shortage and money

The engine answers four questions for every open purchase order line, every
time hazards refresh.

## 1. Is any node on the PO's route inside a hazard? (`gold.node_exposure`)
Nodes are supplier sites and sea ports. A node is exposed when it lies within an
active hazard's impact radius (great-circle distance):

| Hazard | Severity | Radius |
|---|---|---|
| Cyclone (one row per forecast point) | category 1–3+ | 180 / 240 / 300 km |
| Earthquake | magnitude | 60 + 95 × (M − 4) km, so ~212 km at M5.6 |
| Port congestion | average wait hours | the port itself (30 km); never applied to suppliers |

## 2. How many days does the PO slip? (`gold.po_delay`)
A PO meets up to three nodes on future dates: **pickup at the supplier** (if not
yet shipped), the **origin port** and the **destination port** (sea lanes). If a
milestone date falls inside the hazard window (± 1 day), `ref.delay_rules` adds
days by hazard, node type and severity, e.g. cyclone cat 3 at a supplier = 7 days,
earthquake M5–6 at a supplier = 3 days, congestion = ceil(wait hours / 24).
Delays at successive nodes add up, capped at 21 days.

`new_eta_date = plant_eta_date + delay_days`

## 3. Does the plant run out, and what does it lose? (`gold.plant_material_impact`)
For each plant and material, the next 60 days are simulated twice, with promised
ETAs and with delayed ETAs. Each day: receive what arrives, then consume daily
usage. Stock never goes negative; demand that can't be met is **lost production**
(lines stop, the volume is not made up later).

```
lost_qty_disruption = lost_qty(delayed ETAs) − lost_qty(promised ETAs)
cases_at_risk      = lost_qty × cases per unit of material
revenue_at_risk    = cases_at_risk × net revenue per case
margin_at_risk     = cases_at_risk × margin per case
```
Product mix comes from `ref.plant_products` (bill of materials per case).
Taking the difference means shortages that would happen anyway are not blamed on
the hazard. Losses are counted only up to the day the last delayed PO for that
plant and material arrives: after that both runs hold the same goods, and later
gaps come from orders not placed yet, not from the hazard.

## 4. What should procurement do? (`gold.po_actions`)
A plant-material's impact is shared across its delayed POs by `delay_days × qty`.
For each delayed PO:

| Option | Recovers | Cost |
|---|---|---|
| **Expedite** (air for sea lanes, express truck for road) | port/transit delay only; not a supplier outage | 30% / 8% of PO value |
| **Re-source** to an approved alternate that is *not* exposed and arrives before the delayed ETA | the days it beats the delayed ETA | alternate's price premium × PO value |

The option with the best `margin protected − cost` wins. Otherwise **Monitor** (it
hurts but nothing pays back) or **No action** (stock covers the delay).

## Known simplifications (worth refining with real data)
- If two inputs of the same product run short on the same days, both count the lost cases (overstates).
- Delay rules are expert estimates; calibrate them against past events and actual receipt dates.
- Lost production is valued at standard margin; no recovery through overtime or other plants.
- Re-source assumes the alternate has capacity and can start now at its standard lead time.
