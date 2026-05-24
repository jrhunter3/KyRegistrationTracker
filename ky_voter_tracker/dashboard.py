import sqlite3

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ky_voter_tracker.database import DB_PATH

PARTIES = [
    "democratic", "republican", "independent", "libertarian",
    "green", "constitution", "reform", "socialist_workers",
    "kentucky_party", "other",
]

PARTY_LABELS = {
    "democratic": "Democratic", "republican": "Republican",
    "independent": "Independent", "libertarian": "Libertarian",
    "green": "Green", "constitution": "Constitution",
    "reform": "Reform", "socialist_workers": "Socialist Workers",
    "kentucky_party": "KY Party", "other": "Other",
}

PARTY_COLORS = {
    "democratic": "#1a56db", "republican": "#dc2626",
    "independent": "#d97706", "libertarian": "#fcd34d",
    "green": "#16a34a", "constitution": "#7c3aed",
    "reform": "#ec4899", "socialist_workers": "#ef4444",
    "kentucky_party": "#6b7280", "other": "#9ca3af",
}


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_registrations(from_month: str, until_month: str) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """SELECT * FROM registrations
           WHERE month >= ? AND month <= ?
           ORDER BY month ASC""",
        (from_month, until_month),
    ).fetchall()


def get_month_range() -> tuple[str, str]:
    conn = get_conn()
    row = conn.execute(
        "SELECT MIN(month) as min_m, MAX(month) as max_m FROM registrations"
    ).fetchone()
    return row["min_m"], row["max_m"]


def get_county_names() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT county_name FROM county_stats ORDER BY county_name"
    ).fetchall()
    return [r["county_name"] for r in rows]


def load_county_stats(
    county_names: list[str], from_month: str, until_month: str
) -> list[sqlite3.Row]:
    conn = get_conn()
    placeholders = ",".join("?" for _ in county_names)
    return conn.execute(
        f"""SELECT * FROM county_stats
            WHERE county_name IN ({placeholders})
            AND month >= ? AND month <= ?
            ORDER BY month ASC, county_code ASC""",
        (*county_names, from_month, until_month),
    ).fetchall()


st.set_page_config(page_title="KY Voter Registration Tracker", layout="wide")
st.title("Kentucky Voter Registration Tracker")
st.markdown("Data from KY State Board of Elections (2017–present)")

min_month, max_month = get_month_range()

with st.sidebar:
    st.header("Filters")
    from_month, until_month = st.select_slider(
        "Date Range",
        options=sorted(set(
            r["month"] for r in get_conn().execute(
                "SELECT DISTINCT month FROM registrations ORDER BY month"
            ).fetchall()
        )),
        value=(min_month, max_month),
    )

tab1, tab2, tab3 = st.tabs(
    ["Statewide Overview", "Party Breakdown", "County Comparison"]
)

regs = load_registrations(from_month, until_month)
months = [r["month"] for r in regs]

if not regs:
    for tab in [tab1, tab2, tab3]:
        tab.warning("No data for the selected filters.")
    st.stop()

with tab1:
    totals = [r["total"] for r in regs]

    fig_total = px.line(
        x=months, y=totals,
        title="Total Registered Voters",
        labels={"x": "Month", "y": "Voters"},
    )
    fig_total.update_traces(line=dict(color="#1a56db", width=3))
    fig_total.update_layout(hovermode="x unified")
    tab1.plotly_chart(fig_total, width='stretch')

    col1, col2 = tab1.columns(2)

    with col1:
        male = [r["male"] for r in regs]
        female = [r["female"] for r in regs]
        fig_gender = go.Figure()
        fig_gender.add_trace(go.Scatter(
            x=months, y=male, mode="lines", name="Male",
            line=dict(color="#2563eb", width=2),
        ))
        fig_gender.add_trace(go.Scatter(
            x=months, y=female, mode="lines", name="Female",
            line=dict(color="#ec4899", width=2),
        ))
        fig_gender.update_layout(
            title="By Gender",
            hovermode="x unified",
            yaxis_title="Voters",
        )
        col1.plotly_chart(fig_gender, width='stretch')

    with col2:
        latest = regs[-1]
        cols = col2.columns(3)
        cols[0].metric("Total", f"{latest['total']:,}")
        cols[0].metric(
            "Democratic", f"{latest['democratic']:,}",
            delta=f"{latest['democratic'] / latest['total'] * 100:.1f}%",
        )
        cols[1].metric(
            "Republican", f"{latest['republican']:,}",
            delta=f"{latest['republican'] / latest['total'] * 100:.1f}%",
        )
        cols[1].metric(
            "Other", f"{latest['other']:,}",
            delta=f"{latest['other'] / latest['total'] * 100:.1f}%",
        )
        cols[2].metric(
            "Independent", f"{latest['independent']:,}",
            delta=f"{latest['independent'] / latest['total'] * 100:.1f}%",
        )

with tab2:
    party_data = {p: [r[p] for r in regs] for p in PARTIES}
    dem_pct = [d / t * 100 for d, t in zip(party_data["democratic"], totals)]
    rep_pct = [d / t * 100 for d, t in zip(party_data["republican"], totals)]
    ind_pct = [d / t * 100 for d, t in zip(party_data["independent"], totals)]
    other_pct = [(t - d - r - i) / t * 100
                 for d, r, i, t in zip(
                     party_data["democratic"], party_data["republican"],
                     party_data["independent"], totals,
                 )]

    fig_party_area = go.Figure()
    fig_party_area.add_trace(go.Scatter(
        x=months, y=dem_pct, mode="lines", name="Democratic",
        stackgroup="one", line=dict(width=0.5, color=PARTY_COLORS["democratic"]),
    ))
    fig_party_area.add_trace(go.Scatter(
        x=months, y=rep_pct, mode="lines", name="Republican",
        stackgroup="one", line=dict(width=0.5, color=PARTY_COLORS["republican"]),
    ))
    fig_party_area.add_trace(go.Scatter(
        x=months, y=ind_pct, mode="lines", name="Independent",
        stackgroup="one", line=dict(width=0.5, color=PARTY_COLORS["independent"]),
    ))
    fig_party_area.add_trace(go.Scatter(
        x=months, y=other_pct, mode="lines", name="Other",
        stackgroup="one", line=dict(width=0.5, color=PARTY_COLORS["other"]),
    ))
    fig_party_area.update_layout(
        title="Party Registration Share (% of Total)",
        yaxis_title="Percentage",
        hovermode="x unified",
        yaxis=dict(ticksuffix="%"),
    )
    tab2.plotly_chart(fig_party_area, width='stretch')

    dem_vals = party_data["democratic"]
    rep_vals = party_data["republican"]
    diff_d = [d - r for d, r in zip(dem_vals, rep_vals)]

    fig_diff = px.bar(
        x=months, y=diff_d,
        title="Democratic Advantage (Dem - Rep)",
        labels={"x": "Month", "y": "Voter Advantage"},
        color=diff_d,
        color_continuous_scale=["#dc2626", "#fef2f2", "#1a56db"],
    )
    fig_diff.update_layout(hovermode="x unified", showlegend=False)
    tab2.plotly_chart(fig_diff, width='stretch')

with tab3:
    county_names = get_county_names()
    selected_counties = tab3.multiselect(
        "Select Counties",
        options=county_names,
        default=["JEFFERSON", "FAYETTE", "KENTON", "BOONE"],
    )

    if selected_counties:
        county_rows = load_county_stats(selected_counties, from_month, until_month)

        fig_county = go.Figure()
        for cname in selected_counties:
            cdata = [r for r in county_rows if r["county_name"] == cname]
            if cdata:
                fig_county.add_trace(go.Scatter(
                    x=[r["month"] for r in cdata],
                    y=[r["total"] for r in cdata],
                    mode="lines", name=cname,
                ))

        fig_county.update_layout(
            title="Registration by County",
            hovermode="x unified",
            yaxis_title="Voters",
        )
        tab3.plotly_chart(fig_county, width='stretch')

        party_choice = tab3.selectbox(
            "Party Breakdown", ["total"] + PARTIES,
            format_func=lambda x: "Total" if x == "total" else PARTY_LABELS.get(x, x),
        )

        fig_county_party = go.Figure()
        for cname in selected_counties:
            cdata = [r for r in county_rows if r["county_name"] == cname]
            if cdata:
                key = "total" if party_choice == "total" else party_choice
                fig_county_party.add_trace(go.Scatter(
                    x=[r["month"] for r in cdata],
                    y=[r[key] for r in cdata],
                    mode="lines", name=cname,
                ))

        fig_county_party.update_layout(
            title=f"County Comparison — {'Total' if party_choice == 'total' else PARTY_LABELS.get(party_choice, party_choice)}",
            hovermode="x unified",
            yaxis_title="Voters",
        )
        tab3.plotly_chart(fig_county_party, width='stretch')

with st.expander("Raw Data"):
    st.dataframe(
        [dict(r) for r in regs],
        width='stretch',
        hide_index=True,
    )
