"""Create Fabric admin lineage reports from Power BI Scanner API results.

Use --input to run locally with fictional scan data. Without it, the script
submits an Admin WorkspaceInfo scan, polls its status, and downloads the result.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

SCANNER_SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
SCANNER_BASE = "https://api.powerbi.com/v1.0/myorg/admin/workspaces"


def get_access_token() -> str:
    try:
        import msal
    except ImportError as exc:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc
    required = ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ['TENANT_ID']}",
        client_credential=os.environ["CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(scopes=SCANNER_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Could not obtain a Scanner API token"))
    return result["access_token"]


def fetch_scan(workspace_ids: list[str]) -> dict[str, Any]:
    """Request and retrieve one metadata scan. Scanner requests allow 1-100 IDs."""
    if not 1 <= len(workspace_ids) <= 100:
        raise ValueError("Scanner API requests require between 1 and 100 workspace IDs")
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    params = {"lineage": "true", "datasourceDetails": "true", "getArtifactUsers": "true"}
    response = requests.post(f"{SCANNER_BASE}/getInfo", headers=headers, params=params,
                             json={"workspaces": workspace_ids}, timeout=30)
    response.raise_for_status()
    scan_id = response.json()["id"]
    status_url = f"{SCANNER_BASE}/scanStatus/{scan_id}"
    for _ in range(30):
        status = requests.get(status_url, headers=headers, timeout=30)
        status.raise_for_status()
        value = status.json().get("status")
        if value == "Succeeded":
            result = requests.get(f"{SCANNER_BASE}/scanResult/{scan_id}", headers=headers, timeout=60)
            result.raise_for_status()
            return result.json()
        if value == "Failed":
            raise RuntimeError(f"Scanner request {scan_id} failed")
        time.sleep(5)
    raise TimeoutError(f"Scanner request {scan_id} did not finish in 150 seconds")


def artifact_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("objectId") or "")


def dependency_edges(workspace: dict[str, Any], item: dict[str, Any], item_type: str) -> Iterable[dict[str, str]]:
    source_workspace = str(workspace.get("id", ""))
    source_name = str(workspace.get("name", ""))
    for relation_key, relation_type in (("upstreamDataflows", "upstream-dataflow"),
                                        ("upstreamDatasets", "upstream-dataset"),
                                        ("upstreamDatamarts", "upstream-datamart")):
        for upstream in item.get(relation_key, []) or []:
            target_workspace = str(upstream.get("groupId") or upstream.get("workspaceId") or "")
            if target_workspace and target_workspace != source_workspace:
                yield {
                    "sourceWorkspaceId": source_workspace,
                    "sourceWorkspaceName": source_name,
                    "sourceArtifactId": artifact_id(item),
                    "sourceArtifactName": str(item.get("name", "")),
                    "sourceArtifactType": item_type,
                    "targetWorkspaceId": target_workspace,
                    "targetArtifactId": str(upstream.get("targetDataflowId") or upstream.get("targetDatasetId") or upstream.get("id") or ""),
                    "relationshipType": relation_type,
                }


def build_reports(scan: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    assets: list[dict[str, str]] = []
    dependencies: list[dict[str, str]] = []
    review_queue: list[dict[str, str]] = []
    for workspace in scan.get("workspaces", []):
        workspace_id, workspace_name = str(workspace.get("id", "")), str(workspace.get("name", ""))
        if workspace.get("state") == "Deleted":
            review_queue.append({"workspaceId": workspace_id, "workspaceName": workspace_name,
                                 "severity": "High", "signal": "Deleted workspace in scanner result",
                                 "recommendedAction": "Confirm retention and capacity clean-up."})
        for key, item_type in (("reports", "Report"), ("datasets", "SemanticModel"), ("dataflows", "Dataflow")):
            for item in workspace.get(key, []) or []:
                assets.append({"workspaceId": workspace_id, "workspaceName": workspace_name,
                               "artifactId": artifact_id(item), "artifactName": str(item.get("name", "")),
                               "artifactType": item_type, "owner": str(item.get("configuredBy") or item.get("createdBy") or "")})
                dependencies.extend(dependency_edges(workspace, item, item_type))
                if item.get("schemaMayNotBeUpToDate") or item.get("schemaRetrievalError"):
                    review_queue.append({"workspaceId": workspace_id, "workspaceName": workspace_name,
                                         "severity": "Medium", "signal": f"{item_type} schema health warning",
                                         "recommendedAction": "Review schema refresh and metadata extraction status."})
                if item_type == "Report" and item.get("datasetWorkspaceId") and item["datasetWorkspaceId"] != workspace_id:
                    dependencies.append({"sourceWorkspaceId": workspace_id, "sourceWorkspaceName": workspace_name,
                                         "sourceArtifactId": artifact_id(item), "sourceArtifactName": str(item.get("name", "")),
                                         "sourceArtifactType": item_type, "targetWorkspaceId": str(item["datasetWorkspaceId"]),
                                         "targetArtifactId": str(item.get("datasetId", "")), "relationshipType": "report-to-remote-semantic-model"})
    return assets, dependencies, review_queue


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Power BI Scanner API lineage reports.")
    parser.add_argument("--input", type=Path, help="Fictional Scanner API response for local demonstration")
    parser.add_argument("--workspace-ids", help="Comma-separated workspace IDs for a live scan")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    if args.input:
        scan = json.loads(args.input.read_text(encoding="utf-8"))
    elif args.workspace_ids:
        scan = fetch_scan([item.strip() for item in args.workspace_ids.split(",") if item.strip()])
    else:
        parser.error("provide --input for a local demonstration or --workspace-ids for a live scan")
    args.output.mkdir(parents=True, exist_ok=True)
    assets, dependencies, review_queue = build_reports(scan)
    write_csv(args.output / "workspace_assets.csv", assets, ["workspaceId", "workspaceName", "artifactId", "artifactName", "artifactType", "owner"])
    write_csv(args.output / "cross_workspace_dependencies.csv", dependencies, ["sourceWorkspaceId", "sourceWorkspaceName", "sourceArtifactId", "sourceArtifactName", "sourceArtifactType", "targetWorkspaceId", "targetArtifactId", "relationshipType"])
    write_csv(args.output / "admin_review_queue.csv", review_queue, ["workspaceId", "workspaceName", "severity", "signal", "recommendedAction"])
    print(f"Wrote {len(assets)} assets, {len(dependencies)} dependencies, and {len(review_queue)} review signals")


if __name__ == "__main__":
    main()
