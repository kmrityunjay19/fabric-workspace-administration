# Fabric Workspace Administration Toolkit

A portfolio-safe reference implementation for governing Microsoft Fabric workspaces. It uses anonymised sample data and contains no client, tenant, or production configuration.

## What it demonstrates

- Tenant workspace inventory with pagination support
- Capacity and workspace-state reporting
- Workspace access-review controls for users, groups, and service principals
- Power BI Scanner API metadata scans, including lineage and artifact metadata
- Cross-workspace dependency extraction for semantic models, reports, and dataflows
- CSV reports for operational review, audit evidence, and governance follow-up
- Clear separation between read-only discovery and privileged administration actions

## Architecture

```text
Fabric Admin API --------> workspace_audit.py ------> workspace inventory
Power BI Scanner API ----> scanner_lineage.py ------> asset + dependency reports
                                                    -> access / governance review
```

The implementation uses Fabric's Admin Workspace endpoint for inventory and the Power BI Scanner API for artifact metadata and lineage. It intentionally does not perform mutations such as creating workspaces, changing capacity assignments, or changing access. Those operations should go through a controlled approval workflow.

## Quick start: local demonstration

```bash
python src/workspace_audit.py --input sample_data/workspaces.json --output reports
python src/scanner_lineage.py --input sample_data/scanner_result.json --output reports
```

This creates the following reports from fictitious data:

- `workspace_inventory.csv` and `workspace_summary.csv`
- `workspace_assets.csv` - reports, semantic models, and dataflows by workspace
- `cross_workspace_dependencies.csv` - dependencies that cross workspace boundaries
- `admin_review_queue.csv` - governance signals a Fabric administrator should review

## Run against Fabric

1. Register a Microsoft Entra application and grant the appropriate tenant-read permission.
2. Set `TENANT_ID`, `CLIENT_ID`, and `CLIENT_SECRET` as environment variables.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run `python src/workspace_audit.py --output reports` for the Fabric workspace inventory.
5. Run `python src/scanner_lineage.py --workspace-ids <id1,id2> --output reports` for a Scanner API metadata and lineage scan.

The signed-in identity must be authorised to use the Fabric Admin APIs. Fabric documents the Admin Workspace API as requiring a Fabric administrator or supported service principal, and it is rate limited; the script therefore respects pagination and keeps collection read-only. The Scanner API similarly requires Fabric administrator or supported service-principal access; scans are requested in batches of up to 100 workspace IDs and the result should only be read after a successful status check. See [Fabric workspace inventory](https://learn.microsoft.com/en-us/rest/api/fabric/admin/workspaces/list-workspaces) and [Power BI metadata scanning](https://learn.microsoft.com/power-bi/enterprise/service-admin-metadata-scanning).

## Admin information model

| Question | Source | Report / action |
| --- | --- | --- |
| Which workspaces exist, and on which capacity? | Fabric Admin Workspace API | `workspace_inventory.csv` |
| Who has Admin, Member, Contributor, or Viewer access? | Fabric Admin Workspace Access Details API | Review access against least-privilege policy |
| What items are hosted in each workspace? | Power BI Scanner API | `workspace_assets.csv` |
| Which reports use a semantic model in another workspace? | Scanner `datasetWorkspaceId` | `cross_workspace_dependencies.csv` |
| Which dataflows and semantic models depend on upstream artifacts? | Scanner lineage fields | `cross_workspace_dependencies.csv` |
| Which controls deserve follow-up? | Derived checks | `admin_review_queue.csv` |

### Governance review queue

The toolkit flags common review signals without changing tenant state:

- deleted workspaces still assigned to capacity
- workspaces without capacity assignment
- cross-workspace semantic-model dependencies
- artifacts with cross-workspace lineage
- items with a schema retrieval error or a potentially stale schema

The access-details endpoint is currently documented as Preview, so a production implementation should isolate that connector behind a feature flag and review release changes before relying on it for enforcement.

## Example outputs

| Report | Purpose |
| --- | --- |
| `workspace_inventory.csv` | Workspace-level operational inventory |
| `workspace_summary.csv` | Counts grouped by capacity and state |
| `workspace_assets.csv` | Scanned Power BI artifacts by workspace |
| `cross_workspace_dependencies.csv` | Cross-workspace lineage edges and relationship types |
| `admin_review_queue.csv` | Prioritised, read-only governance signals |

## Portfolio note

This is an independently designed demonstration project inspired by general Fabric workspace-administration patterns. It does not replicate any employer or customer implementation, source code, naming, data, configuration, or architecture.
