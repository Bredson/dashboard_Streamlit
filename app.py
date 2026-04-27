import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import jira_client as jira

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sprint Board Time Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #1e293b; }
    [data-testid="stSidebar"] * { color: #e2e8f0; }
    .metric-card {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 3px solid;
    }
    .block-container { padding-top: 1.5rem; }
    a { color: #3b82f6 !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
ISSUE_TYPES = ["Story", "Task", "Bug", "Defect"]

TYPE_ICONS = {
    "Story":  "📖",
    "Task":   "✅",
    "Bug":    "🐛",
    "Defect": "⚠️",
}

# ── Cached data loaders ───────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_boards():
    return jira.get_boards()

@st.cache_data(show_spinner=False)
def load_sprints(board_id: int):
    return jira.get_sprints(board_id, "active,closed")

@st.cache_data(show_spinner=False)
def load_metrics(board_id: int, date_from: str, date_to: str,
                 sprint_id: int | None, issue_types: list[str] | None):
    types = issue_types if issue_types and len(issue_types) < len(ISSUE_TYPES) else None
    return jira.get_metrics(board_id, date_from, date_to, sprint_id, types)

# ── Sidebar — filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Sprint Dashboard")
    st.caption("finago-products.atlassian.net")
    st.divider()

    # Board
    boards = load_boards()
    board_names = [b["name"] for b in boards]
    board_index = st.selectbox("Board", range(len(board_names)),
                               format_func=lambda i: board_names[i])
    selected_board = boards[board_index]

    # Sprint
    with st.spinner("Loading sprints..."):
        sprints = load_sprints(selected_board["id"])

    if not sprints:
        st.error("No sprints found for this board.")
        st.stop()

    STATE_ICON = {"active": "▶", "closed": "✓", "future": "⏳"}
    sprint_labels = [
        f"{STATE_ICON.get(s['state'], '')} {s['name']} ({(s.get('startDate') or '')[:10]})"
        for s in sprints
    ]

    # Default to first closed sprint
    default_idx = next((i for i, s in enumerate(sprints) if s["state"] == "closed"), 0)
    sprint_index = st.selectbox("Sprint", range(len(sprint_labels)),
                                format_func=lambda i: sprint_labels[i],
                                index=default_idx)
    selected_sprint = sprints[sprint_index]

    # Date range — pre-fill from sprint
    sprint_start = date.fromisoformat(selected_sprint["startDate"][:10]) \
        if selected_sprint.get("startDate") else date.today() - timedelta(days=14)
    sprint_end = date.fromisoformat(selected_sprint["endDate"][:10]) \
        if selected_sprint.get("endDate") else date.today()

    st.divider()
    st.caption("Date range override")
    col_a, col_b = st.columns(2)
    with col_a:
        date_from = st.date_input("From", value=sprint_start, key="date_from")
    with col_b:
        date_to = st.date_input("To", value=sprint_end, key="date_to")

    # Detect if user changed dates away from sprint dates → custom mode
    custom_mode = (date_from != sprint_start or date_to != sprint_end)
    if custom_mode:
        st.info("📅 Custom date range active — sprint ignored")
        effective_sprint_id = None
    else:
        effective_sprint_id = selected_sprint["id"]

    # Issue types
    st.divider()
    st.caption("Issue types")
    selected_types = []
    cols = st.columns(2)
    for i, t in enumerate(ISSUE_TYPES):
        with cols[i % 2]:
            if st.checkbox(f"{TYPE_ICONS[t]} {t}", value=True, key=f"type_{t}"):
                selected_types.append(t)

    if not selected_types:
        st.warning("Select at least one issue type.")
        st.stop()

    st.divider()
    refresh = st.button("🔄 Refresh", use_container_width=True, type="primary")

# ── Load metrics ─────────────────────────────────────────────────────────────
# Clear cache on manual refresh
if refresh:
    load_metrics.clear()
    load_sprints.clear()

with st.spinner("Fetching Jira data..."):
    try:
        data = load_metrics(
            board_id=selected_board["id"],
            date_from=str(date_from),
            date_to=str(date_to),
            sprint_id=effective_sprint_id,
            issue_types=selected_types if len(selected_types) < len(ISSUE_TYPES) else None,
        )
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        st.stop()

tickets = data["tickets"]
columns = data["columns"]
col_averages = data["column_averages"]

if not tickets:
    st.warning("No tickets found for the selected filters.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"## {selected_board['name']}  —  {selected_sprint['name']}")
st.caption(f"{data['date_from']}  →  {data['date_to']}")

# ── KPI cards ─────────────────────────────────────────────────────────────────
total = len(tickets)
done  = sum(1 for t in tickets if t["status"].lower() in ("done", "closed"))
avg_h = round(sum(t["total_hours"] for t in tickets) / total, 1) if total else 0

middle_avgs = [c for c in col_averages if c["ticket_count"] > 0
               and c["column"] not in (columns[0], columns[-1])]
bottleneck = max(middle_avgs, key=lambda c: c["avg_hours"]) if middle_avgs else None

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tickets analysed", total)
k2.metric("Done / Closed", f"{done} / {total}")
k3.metric("Avg cycle time", f"{avg_h} h")
k4.metric("Bottleneck",
          bottleneck["column"] if bottleneck else "—",
          delta=f"avg {bottleneck['avg_hours']} h" if bottleneck else None,
          delta_color="inverse")

st.divider()

# ── Charts row ────────────────────────────────────────────────────────────────
chart_left, chart_right = st.columns(2)

# Bar chart — avg time per column
with chart_left:
    st.subheader("Average time per column")
    df_avg = pd.DataFrame(col_averages).query("ticket_count > 0")
    fig_bar = px.bar(
        df_avg, x="column", y="avg_hours",
        text="avg_hours",
        color="avg_hours",
        color_continuous_scale=["#3b82f6", "#f59e0b", "#ef4444"],
        labels={"column": "", "avg_hours": "Hours"},
        template="plotly_dark",
    )
    fig_bar.update_traces(texttemplate="%{text:.1f} h", textposition="outside")
    fig_bar.update_layout(
        coloraxis_showscale=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=0),
        height=320,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Heat map
with chart_right:
    st.subheader("Ticket heat map")
    top_tickets = tickets[:20]
    ids = [t["id"] for t in top_tickets]
    matrix = []
    for col in columns:
        row = [t["column_times"].get(col, {}).get("hours", 0) for t in top_tickets]
        matrix.append(row)

    fig_heat = go.Figure(go.Heatmap(
        z=matrix,
        x=ids,
        y=columns,
        colorscale=[[0, "#1e293b"], [0.33, "#1d4ed8"],
                    [0.66, "#f59e0b"], [1.0, "#ef4444"]],
        text=[[f"{v:.1f}h" if v > 0 else "" for v in row] for row in matrix],
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="<b>%{x}</b><br>%{y}: %{z:.1f} h<extra></extra>",
    ))
    fig_heat.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=0),
        height=320,
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# ── Ticket table ──────────────────────────────────────────────────────────────
st.subheader("Ticket details")

# Build dataframe
rows = []
JIRA_BASE = "https://finago-products.atlassian.net/browse"
for t in tickets:
    row = {
        "ID": f"[{t['id']}]({JIRA_BASE}/{t['id']})",
        "Title": t["title"],
        "Type": f"{TYPE_ICONS.get(t['type'], '📌')} {t['type']}",
        "Assignee": t["assignee"],
        "Status": t["status"],
        "Total (h)": t["total_hours"],
    }
    for col in columns:
        row[col] = t["column_times"].get(col, {}).get("hours", 0)
    rows.append(row)

df = pd.DataFrame(rows)

# Search
search = st.text_input("🔍 Search by ID, title or assignee", placeholder="e.g. DEV-123 or Alice")
if search:
    mask = (
        df["ID"].str.contains(search, case=False, na=False) |
        df["Title"].str.contains(search, case=False, na=False) |
        df["Assignee"].str.contains(search, case=False, na=False)
    )
    df = df[mask]

st.caption(f"Showing {len(df)} tickets")

# Colour column hours by intensity
max_h = max((t["total_hours"] for t in tickets), default=1)

def colour_hours(val):
    if not isinstance(val, (int, float)) or val == 0:
        return ""
    ratio = min(val / max_h, 1.0)
    if ratio < 0.33:
        return "background-color: #1e3a5f; color: #93c5fd"
    elif ratio < 0.66:
        return "background-color: #78350f; color: #fcd34d"
    else:
        return "background-color: #7f1d1d; color: #fca5a5"

col_hour_cols = columns

styled = (
    df.style
    .map(colour_hours, subset=col_hour_cols)
    .format({col: lambda v: f"{v:.1f} h" if v > 0 else "—" for col in col_hour_cols})
    .format({"Total (h)": "{:.1f} h"})
)

st.dataframe(
    styled,
    use_container_width=True,
    height=min(40 + len(df) * 35, 600),
    column_config={
        "ID": st.column_config.LinkColumn("ID", display_text=r"\[(.+?)\]"),
        "Total (h)": st.column_config.NumberColumn("Total (h)", format="%.1f h"),
    },
    hide_index=True,
)
