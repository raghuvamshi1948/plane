"""
Smoke-test the Prodoc dependency DELETE endpoint against a running instance.

Usage:
    PLANE_BASE_URL=http://localhost:8000 \
    PLANE_API_KEY=<key> \
    WORKSPACE_SLUG=<slug> \
    PROJECT_ID=<uuid> \
    ISSUE_A_ID=<uuid> \
    ISSUE_B_ID=<uuid> \
    python smoke_dependency_api.py

Sequence:
    1. Create a `blocked_by` relation via UPSTREAM POST (issue B blocked by A).
       This proves the prerequisite (upstream create) works in this instance.
    2. List relations on issue B via UPSTREAM GET. Capture the new relation id.
    3. DELETE the relation via the PRODOC endpoint.
    4. List relations on issue B again via UPSTREAM GET. Assert empty.
    5. Print PASS/FAIL summary.

Exits 0 on success, 1 on any failure.
"""

import os
import sys

import requests


def _env(name):
    val = os.environ.get(name)
    if not val:
        print(f"FAIL: missing required env var {name}", file=sys.stderr)
        sys.exit(1)
    return val


def main():
    base = _env("PLANE_BASE_URL").rstrip("/")
    api_key = _env("PLANE_API_KEY")
    slug = _env("WORKSPACE_SLUG")
    project_id = _env("PROJECT_ID")
    issue_a_id = _env("ISSUE_A_ID")
    issue_b_id = _env("ISSUE_B_ID")

    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    upstream_relations_url = (
        f"{base}/api/v1/workspaces/{slug}/projects/{project_id}"
        f"/work-items/{issue_b_id}/relations/"
    )

    # 1. Create the relation via upstream POST.
    print(f"[1/4] POST {upstream_relations_url}")
    create_payload = {
        "relation_type": "blocked_by",
        "issues": [issue_a_id],
    }
    r = requests.post(upstream_relations_url, headers=headers, json=create_payload, timeout=30)
    if r.status_code not in (200, 201):
        print(f"FAIL: upstream POST returned {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    print(f"      ok ({r.status_code})")

    # 2. List relations via upstream GET. Find our new edge.
    print(f"[2/4] GET  {upstream_relations_url}")
    r = requests.get(upstream_relations_url, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"FAIL: upstream GET returned {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)

    body = r.json()
    # Upstream returns a dict like {"blocked_by": [...], "blocking": [...], ...}
    # or a flat list depending on version. Handle both.
    relation_id = None
    if isinstance(body, dict):
        for bucket in body.values():
            if isinstance(bucket, list):
                for entry in bucket:
                    if str(entry.get("issue")) == issue_a_id or str(entry.get("related_issue")) == issue_a_id:
                        relation_id = entry.get("id")
                        break
            if relation_id:
                break
    elif isinstance(body, list):
        for entry in body:
            if str(entry.get("issue")) == issue_a_id or str(entry.get("related_issue")) == issue_a_id:
                relation_id = entry.get("id")
                break

    if not relation_id:
        print(f"FAIL: could not locate created relation in GET response: {body}", file=sys.stderr)
        sys.exit(1)
    print(f"      relation_id={relation_id}")

    # 3. DELETE via the prodoc endpoint.
    prodoc_delete_url = (
        f"{base}/api/v1/prodoc/workspaces/{slug}/projects/{project_id}"
        f"/work-items/{issue_b_id}/relations/{relation_id}/"
    )
    print(f"[3/4] DEL  {prodoc_delete_url}")
    r = requests.delete(prodoc_delete_url, headers=headers, timeout=30)
    if r.status_code != 204:
        print(f"FAIL: prodoc DELETE returned {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    print("      ok (204)")

    # 4. Verify removal via upstream GET.
    print(f"[4/4] GET  {upstream_relations_url}")
    r = requests.get(upstream_relations_url, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"FAIL: upstream GET returned {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)

    body = r.json()
    still_present = False
    if isinstance(body, dict):
        for bucket in body.values():
            if isinstance(bucket, list):
                for entry in bucket:
                    if str(entry.get("id")) == str(relation_id):
                        still_present = True
                        break
    elif isinstance(body, list):
        still_present = any(str(entry.get("id")) == str(relation_id) for entry in body)

    if still_present:
        print("FAIL: relation still present after DELETE", file=sys.stderr)
        sys.exit(1)

    print("\nPASS: created via upstream → deleted via prodoc → verified via upstream")
    sys.exit(0)


if __name__ == "__main__":
    main()
