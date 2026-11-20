# Step I · Deploy the God's Eye View app (Databricks Apps, Free Edition)

The app lives in `app/`. It reads the gold tables through a SQL warehouse and sends chat questions to
the **Supply Risk Forecast** Genie agent. No CLI needed — everything below is clicks in the workspace.

## Before you start
- The notebook `notebooks/01_setup_and_run.py` has run (the `supply_risk_dev` gold tables exist).
- The Genie agent **Supply Risk Forecast** exists.
- Your Git folder is pulled to the latest commit.

## 1. Create the app
1. Left sidebar → **Compute** → **Apps** tab → **Create app**.
2. Choose **Create a custom app**. Name: `gev-supply-risk`. Click **Next / Configure**.
3. Under **App resources** → **Add resource**:
   - **SQL warehouse** → pick your Serverless Starter Warehouse → permission **Can use** → resource key `sql-warehouse`.
   - **Genie space** → pick **Supply Risk Forecast** → permission **Can run** → resource key `genie-space`.
4. **Create app**. Wait until the compute shows **Running** (a few minutes).

## 2. Give the app read access to the data
The app runs as its own service principal (shown on the app page under **App resource / Service principal**,
named like `app-xxxx gev-supply-risk`). Copy its **application ID** and run this in a SQL editor:

```sql
GRANT USE CATALOG ON CATALOG supply_risk_dev TO `<application-id>`;
GRANT USE SCHEMA, SELECT ON SCHEMA supply_risk_dev.ref    TO `<application-id>`;
GRANT USE SCHEMA, SELECT ON SCHEMA supply_risk_dev.silver TO `<application-id>`;
GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA supply_risk_dev.gold TO `<application-id>`;
```
(`EXECUTE` lets Genie call the trusted functions as the app.)
Or click through it: **Catalog** → `supply_risk_dev` → **Permissions** → **Grant** → the app's service principal →
*USE CATALOG, USE SCHEMA, SELECT, EXECUTE*.

## 3. Deploy the code
1. On the app page → **Deploy**.
2. Source code path: your Git folder + `/app`, e.g. `/Workspace/Users/<you>/gev-supply-risk/app`.
3. **Deploy**. When the status turns **Running**, click the app URL.

## 4. Updating later
`git pull` in the Git folder → app page → **Deploy** again (same path).

## Troubleshooting
| You see | Fix |
|---|---|
| Red banner "Couldn't load the risk tables… PERMISSION_DENIED" | Step 2 grants are missing for the app's service principal. |
| "WAREHOUSE_ID is not set" / "GENIE_SPACE_ID is not set" | Resource keys must be exactly `sql-warehouse` and `genie-space`. Redeploy after fixing. |
| Chat says "Genie request failed … permission" | Genie resource needs **Can run**; also the step 2 grants. |
| App stopped next day | Free Edition stops apps after 24 h. App page → **Start**. |
| Logs | App page → **Logs** tab. |

Free Edition: max 3 apps, no commercial use, sample data only.
