# Sprint Board Time Tracker — Streamlit

A dashboard that visualizes how long tickets spend in each column of a Jira Sprint Board. Built entirely in Python using Streamlit — one file, one process, zero JavaScript.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Dashboard](#running-the-dashboard)
- [Configuration](#configuration)
- [Jira Integration](#jira-integration)
- [Sharing on a Network](#sharing-on-a-network)
- [Known Limitations](#known-limitations)

---

## Overview

The tool analyses the status-transition history (Jira changelog) of every ticket and calculates how many hours each ticket spent in each board column (e.g. "In Progress", "Code Review", "Testing"). This makes it easy to identify bottlenecks in a team's delivery process.

This project is a simplified rewrite of [sprint-dashboard](https://github.com/Bredson/sprint-dashboard) (FastAPI + React). Instead of two processes and ~15 files — a single Python file.

---

## Features

- **Board selector** — choose from 10 pre-configured Scrum team boards
- **Sprint selector** — 20 most recent sprints (active + closed), newest first; defaults to the last closed sprint
- **Date range** — From/To fields pre-filled from the selected sprint; changing the dates switches to custom mode (sprint ignored)
- **Issue type filter** — Story, Task, Bug, Defect (checkboxes, at least one required)
- **Refresh button** — clears the cache and fetches fresh data from Jira
- **Summary KPIs** — 4 metric cards: ticket count, done/closed, average cycle time, bottleneck column
- **Bar chart** — average time per column (Plotly, interactive)
- **Heat map** — tickets × columns with blue→orange→red gradient (Plotly)
- **Ticket table** — with search, colour-coded cells by intensity, and clickable Jira links

---

## Architecture

```
Jira REST API
     │
     ▼
jira_client.py  ←  data fetching + time-in-column analytics
     │
     ▼
app.py  ←  Streamlit UI (sidebar + charts + table)
     │
     ▼
Browser  →  http://localhost:8501
```

The entire stack is a **single Python process**. Streamlit serves the UI directly — there is no separate backend or frontend.

---

## Project Structure

```
dashboard_Streamlit/
├── app.py              # Full dashboard — UI, logic, charts
├── jira_client.py      # Jira API client + time-in-column analytics engine
├── requirements.txt    # Python dependencies
├── .env                # Jira credentials — NEVER commit this file
├── .env.example        # Template for .env (safe to commit)
├── .gitignore
├── README.md           # Documentation (Polish)
├── README.en.md        # Documentation (English)
└── .venv/              # Python virtual environment (auto-generated)
```

### File descriptions

| File | Description |
|------|-------------|
| `app.py` | Main application file. Contains: page config, CSS overrides, cached data loaders, sidebar filters, KPI cards, Plotly bar chart, Plotly heat map, and a searchable colour-coded ticket table. |
| `jira_client.py` | Jira REST API client. Fetches boards, sprints, columns, and issues with changelog. Calculates time spent in each column based on status-transition history. See [Jira Integration](#jira-integration) for details. |
| `requirements.txt` | Four dependencies: `streamlit`, `plotly`, `pandas`, `python-dotenv`. |
| `.env` | Jira connection credentials — excluded from the repository. |
| `.env.example` | `.env` template with empty values — included in the repository. |

---

## Requirements

- Python 3.11+
- Access to Jira Cloud (`finago-products.atlassian.net`)
- Jira API Token — generate one at: https://id.atlassian.com/manage-profile/security/api-tokens

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Bredson/dashboard_Streamlit.git
cd dashboard_Streamlit

# 2. Create a virtual environment
python3 -m venv .venv

# 3. Install dependencies
.venv/bin/pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env — fill in JIRA_URL, JIRA_EMAIL, JIRA_TOKEN
```

---

## Running the Dashboard

```bash
.venv/bin/streamlit run app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

To run on a different port:

```bash
.venv/bin/streamlit run app.py --server.port 8502
```

---

## Configuration

### `.env` file

```
JIRA_URL=https://finago-products.atlassian.net
JIRA_EMAIL=your.email@finago.com
JIRA_TOKEN=<your_api_token>
```

> **Note:** Jira API tokens expire after 1 year. When the token expires the dashboard returns `401 Unauthorized`. To renew: generate a new token at https://id.atlassian.com/manage-profile/security/api-tokens, update `JIRA_TOKEN` in `.env`, and restart the app.

---

### Board list (`jira_client.py`)

The boards available in the selector are defined as the `ALLOWED_BOARDS` constant in `jira_client.py`:

```python
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
```

To add or remove a board, edit this list. The board ID can be found in the Jira URL when viewing the board: `.../jira/software/projects/.../boards/<ID>`.

---

### Cache

Jira data is cached by Streamlit (`@st.cache_data`). To refresh — click the **Refresh** button in the sidebar. It clears all data loader caches and fetches fresh data from Jira.

---

## Jira Integration

### How time-in-column is calculated

The full `changelog` is fetched from the Jira API for every ticket. The algorithm in `jira_client._compute_column_times()`:

1. Reconstructs the complete status-transition timeline (oldest → newest)
2. Maps Jira status names to board column names using fuzzy substring matching
3. For each segment, computes its intersection with the requested date window
4. Sums the hours per column

```
Ticket DEV-74351:
  2024-03-20  ──►  In Implementation  (106 h)
  2024-04-02  ──►  IN REVIEW          (110 h)
  2024-04-03  ──►  Ready for Testing  ( 59 h)
  2024-04-05  ──►  In Testing         (  9 h)
  2024-04-05  ──►  Closed
```

### Data fetching modes

| Mode | When | Source |
|------|------|--------|
| **Sprint** | Dates match the selected sprint | `GET /board/{id}/sprint/{id}/issue` — all tickets in the sprint |
| **Date range** | User changed dates manually | `GET /search/jql` — tickets updated within the date range |

> Note: The old `GET /rest/api/3/search` endpoint has been removed by Atlassian (HTTP 410). The dashboard uses the new `GET /rest/api/3/search/jql` with `nextPageToken`-based pagination.

---

## Sharing on a Network

### Local network / VPN

```bash
.venv/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Find your IP address:

```bash
# macOS
ifconfig | grep "inet " | grep -v "127.0.0.1"

# Windows
ipconfig
```

Share the VPN address (e.g. `http://192.168.240.37:8501`) with people connected via the company VPN. The Wi-Fi address (`192.168.x.x`) only works on the same physical network.

---

## Known Limitations

- Date-range mode returns a maximum of 100 tickets per query
- Time in column is calculated as calendar time, not business hours
- The Jira API token expires after 1 year
- The heat map displays a maximum of 20 tickets (top 20 by total hours)
