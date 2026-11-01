# Fabric Workspace Administration Toolkit

A portfolio-safe reference implementation for governing Microsoft Fabric workspaces. It uses anonymised sample data and contains no client, tenant, or production configuration.

## What it demonstrates

- Tenant workspace inventory with pagination support
- Capacity and workspace-state reporting
- Ownership and access-review controls
- CSV reports for operational review and audit evidence
- Clear separation between read-only discovery and privileged administration actions

## Architecture

```text
Fabric Admin API -> workspace_audit.py -> CSV reports -> access / governance review
```

The implementation uses Fabric's Admin Workspace endpoint for inventory. It intentionally does not perform mutations such as creating workspaces, changing capacity assignments, or changing access. Those operations should go through a controlled approval workflow.

## Quick start: local demonstration

```bash
python src/workspace_audit.py --input sample_data/workspaces.json --output reports
```

This creates `workspace_inventory.csv` and `workspace_summary.csv` from fictitious data.

## Run against Fabric

1. Register a Microsoft Entra application and grant the appropriate tenant-read permission.
2. Set `TENANT_ID`, `CLIENT_ID`, and `CLIENT_SECRET` as environment variables.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run `python src/workspace_audit.py --output reports`.

The signed-in identity must be authorised to use the Fabric Admin APIs. Fabric documents the Admin Workspace API as requiring a Fabric administrator or supported service principal, and it is rate limited; the script therefore respects pagination and keeps collection read-only. See [Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/fabric/admin/workspaces/list-workspaces).

## Example outputs

| Report | Purpose |
| --- | --- |
| `workspace_inventory.csv` | Workspace-level operational inventory |
| `workspace_summary.csv` | Counts grouped by capacity and state |

## Portfolio note

This is an independently designed demonstration project inspired by general Fabric workspace-administration patterns. It does not replicate any employer or customer implementation, source code, naming, data, configuration, or architecture.
