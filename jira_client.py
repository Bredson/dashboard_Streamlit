"""
Jira REST API client for Sprint Board Time Tracker.
Fetches boards, sprints, issues with changelog, and computes
time-in-column metrics based on status transition history.
"""

import os
import ssl
import base64
import json
import urllib.request
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")

# Explicit allowlist of boards to show in the dashboard
ALLOWED_BOARDS = [
    {"id": 23,  "name": "Flycatcher"},
    {"id": 70,  "name": "Team Parrot"},
    {"id": 72,  "name": "Team Roadrunner"},
    {"id": 98,  "name": "Spectre"},
    {"id": 96,  "name": "Team Eagle"},
    {"id": 115, "name": "Team Pike"},
    {"id": 259, "name": "Team Fenix"},
    {"id": 66,  "name": "Team Kiwi"},
    {"id": 216, "name": "Team Paw Patrol"},
    {"id": 130, "name": "Team Sparrow"},
]

_SSL_CTX = ssl._create_unverified_context()


def _auth_header() -> str:
    token = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    return f"Basic {token}"


def _get(path: str, params: dict = None) -> dict:
    url = f"{JIRA_URL}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(), "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as r:
        return json.loads(r.read())


import urllib.parse


def _get_paginated(path: str, key: str, extra_params: dict = None, max_results: int = 200) -> list:
    """Fetch all pages from a Jira paginated endpoint."""
    results = []
    start = 0
    while True:
        params = {"maxResults": 50, "startAt": start}
        if extra_params:
            params.update(extra_params)
        data = _get(path, params)
        page = data.get(key, data.get("values", []))
        results.extend(page)
        total = data.get("total", len(page))
        start += len(page)
        if start >= total or not page or start >= max_results:
            break
    return results


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

def get_boards() -> list[dict]:
    """Return the fixed allowlist of team boards."""
    return [{"id": b["id"], "name": b["name"], "type": "scrum"} for b in ALLOWED_BOARDS]


# ---------------------------------------------------------------------------
# Sprints
# ---------------------------------------------------------------------------

def get_sprints(board_id: int, state: str = "active,closed") -> list[dict]:
    """Return 20 most recent sprints for a board, newest first."""
    LIMIT = 20

    # Step 1: get total count
    first_page = _get(
        f"/rest/agile/1.0/board/{board_id}/sprint",
        {"maxResults": 1, "state": state},
    )
    total = first_page.get("total", 0)

    # Step 2: fetch the last page (most recent sprints by Jira's natural ID order)
    start_at = max(0, total - LIMIT)
    data = _get(
        f"/rest/agile/1.0/board/{board_id}/sprint",
        {"maxResults": LIMIT, "startAt": start_at, "state": state},
    )
    sprints = data.get("values", [])

    result = []
    for s in sprints:
        result.append({
            "id": s["id"],
            "name": s["name"],
            "state": s["state"],
            "startDate": s.get("startDate"),
            "endDate": s.get("endDate"),
            "completeDate": s.get("completeDate"),
        })

    # Newest first
    result.sort(key=lambda x: x.get("startDate") or "", reverse=True)
    return result


# ---------------------------------------------------------------------------
# Board columns
# ---------------------------------------------------------------------------

def get_board_columns(board_id: int) -> list[str]:
    """Return ordered column names from board configuration."""
    try:
        config = _get(f"/rest/agile/1.0/board/{board_id}/configuration")
        cols = config.get("columnConfig", {}).get("columns", [])
        return [c["name"] for c in cols]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Issues + changelog
# ---------------------------------------------------------------------------

def _fetch_issues_for_sprint(board_id: int, sprint_id: int) -> list[dict]:
    """Fetch all issues in a sprint with changelog."""
    issues = []
    start = 0
    while True:
        params = {
            "maxResults": 50,
            "startAt": start,
            "expand": "changelog",
            "fields": "summary,status,assignee,issuetype,priority,created,resolutiondate",
        }
        data = _get(f"/rest/agile/1.0/board/{board_id}/sprint/{sprint_id}/issue", params)
        page = data.get("issues", [])
        issues.extend(page)
        total = data.get("total", len(page))
        start += len(page)
        if start >= total or not page:
            break
    return issues


def _fetch_issues_by_date(board_id: int, date_from: str, date_to: str) -> list[dict]:
    """Fetch issues updated within date range (fallback for date-based queries)."""
    project_data = _get(f"/rest/agile/1.0/board/{board_id}/project")
    project_keys = [p["key"] for p in project_data.get("values", [])]
    if not project_keys:
        return []

    jql = (
        f"project in ({','.join(project_keys)}) "
        f"AND updated >= \"{date_from}\" AND updated <= \"{date_to}\" "
        f"ORDER BY updated DESC"
    )
    issues = []
    next_page_token = None
    while True:
        params = {
            "jql": jql,
            "maxResults": 50,
            "expand": "changelog",
            "fields": "summary,status,assignee,issuetype,priority,created,resolutiondate",
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        # Use new /rest/api/3/search/jql endpoint (GET /rest/api/3/search is deprecated/gone)
        data = _get("/rest/api/3/search/jql", params)
        page = data.get("issues", [])
        issues.extend(page)
        next_page_token = data.get("nextPageToken")
        if data.get("isLast", True) or not page or not next_page_token or len(issues) >= 100:
            break
    return issues


# ---------------------------------------------------------------------------
# Column time computation
# ---------------------------------------------------------------------------

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Handle both Z and +00:00 suffixes
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _compute_column_times(
    issue: dict,
    columns: list[str],
    date_from: datetime,
    date_to: datetime,
) -> dict:
    """
    Walk the changelog and compute hours spent in each board column.
    Maps Jira status names → board column names using a fuzzy match.
    """
    # Build status→column mapping (case-insensitive substring)
    col_lower = {c.lower(): c for c in columns}

    def status_to_column(status_name: str) -> Optional[str]:
        sl = status_name.lower()
        # Exact match first
        if sl in col_lower:
            return col_lower[sl]
        # Substring match
        for key, col in col_lower.items():
            if key in sl or sl in key:
                return col
        return None

    # Gather all status transitions from changelog
    transitions = []
    created_str = issue["fields"].get("created")
    created_dt = _parse_dt(created_str) or date_from

    changelog = issue.get("changelog", {})
    for history in changelog.get("histories", []):
        ts = _parse_dt(history.get("created"))
        if not ts:
            continue
        for item in history.get("items", []):
            if item.get("field") == "status":
                transitions.append({
                    "ts": ts,
                    "from": item.get("fromString", ""),
                    "to": item.get("toString", ""),
                })

    transitions.sort(key=lambda x: x["ts"])

    # Build timeline: list of (status, start_dt)
    current_status = transitions[0]["from"] if transitions else issue["fields"]["status"]["name"]
    timeline = [(current_status, created_dt)]
    for t in transitions:
        timeline.append((t["to"], t["ts"]))

    # Add current open period
    now = datetime.now(timezone.utc)
    timeline.append((None, min(now, date_to)))  # sentinel end

    # Accumulate hours per column within [date_from, date_to]
    col_hours: dict[str, float] = {c: 0.0 for c in columns}
    col_entry: dict[str, Optional[str]] = {c: None for c in columns}

    for i in range(len(timeline) - 1):
        status, start = timeline[i]
        _, end = timeline[i + 1]

        col = status_to_column(status)
        if col is None:
            continue

        # Clamp to [date_from, date_to]
        seg_start = max(start, date_from)
        seg_end = min(end, date_to)
        if seg_end <= seg_start:
            continue

        hours = (seg_end - seg_start).total_seconds() / 3600
        col_hours[col] = round(col_hours[col] + hours, 1)
        if col_entry[col] is None:
            col_entry[col] = seg_start.isoformat()

    # Build result dict (only columns where ticket spent time)
    result = {}
    for col in columns:
        if col_hours[col] > 0:
            result[col] = {
                "hours": col_hours[col],
                "entry": col_entry[col],
            }

    return result


# ---------------------------------------------------------------------------
# Sprint info helper
# ---------------------------------------------------------------------------

def _get_sprint_info(sprint_id: int) -> Optional[dict]:
    """Fetch sprint metadata (dates etc.)."""
    try:
        data = _get(f"/rest/agile/1.0/sprint/{sprint_id}")
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main metrics function
# ---------------------------------------------------------------------------

def get_metrics(
    board_id: int,
    date_from_str: str,
    date_to_str: str,
    sprint_id: Optional[int] = None,
    issue_types: Optional[list[str]] = None,
) -> dict:
    """
    Returns full metrics payload for the dashboard.
    If sprint_id is given, fetches issues for that sprint and uses sprint dates.
    Otherwise fetches issues updated within the date range.
    issue_types: list of Jira type names to include (None = all).
    """
    columns = get_board_columns(board_id)
    if not columns:
        columns = ["To Do", "In Progress", "In Review", "Testing", "Done"]

    # Fetch issues
    if sprint_id:
        raw_issues = _fetch_issues_for_sprint(board_id, sprint_id)
        # Use sprint dates for time computation when sprint is selected
        sprint_info = _get_sprint_info(sprint_id)
        if sprint_info:
            sprint_start = sprint_info.get("startDate")
            sprint_end = sprint_info.get("completeDate") or sprint_info.get("endDate")
            if sprint_start:
                date_from_str = sprint_start[:10]
            if sprint_end:
                date_to_str = sprint_end[:10]
    else:
        raw_issues = _fetch_issues_by_date(board_id, date_from_str, date_to_str)

    date_from = datetime.fromisoformat(date_from_str).replace(tzinfo=timezone.utc)
    date_to = datetime.fromisoformat(date_to_str).replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )

    # Normalise filter to lowercase set for fast lookup
    types_filter = {t.lower() for t in issue_types} if issue_types else None

    tickets = []
    for issue in raw_issues:
        fields = issue.get("fields", {})

        # Apply issue type filter
        if types_filter:
            issue_type = (fields.get("issuetype") or {}).get("name", "")
            if issue_type.lower() not in types_filter:
                continue
        col_times = _compute_column_times(issue, columns, date_from, date_to)

        # Skip tickets with no time in date range
        if not col_times:
            continue

        assignee_data = fields.get("assignee") or {}
        tickets.append({
            "id": issue["key"],
            "title": fields.get("summary", ""),
            "type": (fields.get("issuetype") or {}).get("name", "Task"),
            "assignee": assignee_data.get("displayName", "Unassigned"),
            "status": (fields.get("status") or {}).get("name", ""),
            "column_times": col_times,
            "total_hours": round(sum(v["hours"] for v in col_times.values()), 1),
        })

    tickets.sort(key=lambda t: t["total_hours"], reverse=True)

    # Column averages
    col_sums: dict[str, float] = {c: 0.0 for c in columns}
    col_counts: dict[str, int] = {c: 0 for c in columns}
    for t in tickets:
        for col, data in t["column_times"].items():
            col_sums[col] += data["hours"]
            col_counts[col] += 1

    column_averages = [
        {
            "column": col,
            "avg_hours": round(col_sums[col] / col_counts[col], 1) if col_counts[col] > 0 else 0,
            "ticket_count": col_counts[col],
        }
        for col in columns
    ]

    return {
        "board_id": board_id,
        "sprint_id": sprint_id,
        "date_from": date_from_str,
        "date_to": date_to_str,
        "columns": columns,
        "tickets": tickets,
        "column_averages": column_averages,
        "total_tickets": len(tickets),
    }
