"""Create read-only Microsoft Fabric workspace inventory reports.

Run with --input for a safe local demonstration. Without it, the script reads
credentials from the environment and queries the Fabric Admin API.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

FABRIC_SCOPE = ["https://api.fabric.microsoft.com/.default"]
WORKSPACES_URL = "https://api.fabric.microsoft.com/v1/admin/workspaces"
INVENTORY_COLUMNS = ["id", "name", "type", "state", "capacityId", "domainId"]


def get_access_token() -> str:
    """Get an app-only token; secrets are only read from the environment."""
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
    result = app.acquire_token_for_client(scopes=FABRIC_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Could not obtain Fabric access token"))
    return result["access_token"]


def fetch_workspaces() -> list[dict[str, Any]]:
    """Collect all workspace pages from the Fabric Admin API."""
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    url: str | None = WORKSPACES_URL
    workspaces: list[dict[str, Any]] = []

    while url:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        workspaces.extend(payload.get("workspaces", []))
        url = payload.get("continuationUri")
    return workspaces


def load_workspaces(input_file: Path | None) -> list[dict[str, Any]]:
    if input_file:
        return json.loads(input_file.read_text(encoding="utf-8")).get("workspaces", [])
    return fetch_workspaces()


def write_reports(workspaces: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "workspace_inventory.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=INVENTORY_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(workspaces)

    summary = Counter((item.get("capacityId") or "Unassigned", item.get("state") or "Unknown") for item in workspaces)
    with (output_dir / "workspace_summary.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["capacityId", "state", "workspaceCount"])
        writer.writeheader()
        for (capacity_id, state), count in sorted(summary.items()):
            writer.writerow({"capacityId": capacity_id, "state": state, "workspaceCount": count})


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a Fabric workspace inventory.")
    parser.add_argument("--input", type=Path, help="Local Fabric-like JSON input for a safe demonstration")
    parser.add_argument("--output", type=Path, default=Path("reports"), help="Directory for generated CSV files")
    args = parser.parse_args()
    workspaces = load_workspaces(args.input)
    write_reports(workspaces, args.output)
    print(f"Wrote {len(workspaces)} workspaces to {args.output}")


if __name__ == "__main__":
    main()
