import json
import sqlite3
import urllib.request

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

MAJOR_COLOR = "#4f46e5"
ALT_COLOR = "#059669"


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


@st.cache_data
def _load_ky_geojson() -> dict | None:
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            all_counties = json.loads(resp.read().decode())
    except Exception:
        return None
    features = [f for f in all_counties["features"] if f["id"].startswith("21")]
    return {"type": "FeatureCollection", "features": features}


def load_single_month_county_stats(month: str) -> list[sqlite3.Row]:
    conn = get_conn()
    return conn.execute(
        """SELECT *, CAST(21001 + (CAST(county_code AS INTEGER) - 1) * 2 AS TEXT) AS fips
           FROM county_stats
           WHERE month = ?
           ORDER BY county_code ASC""",
        (month,),
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


def _alt_parties() -> list[str]:
    return [p for p in PARTIES if p not in ("democratic", "republican")]


def compute_alternative(regs: list[sqlite3.Row]) -> list[int]:
    alt = _alt_parties()
    return [sum(r[p] for p in alt) for r in regs]


def compute_major(regs: list[sqlite3.Row]) -> list[int]:
    return [r["democratic"] + r["republican"] for r in regs]


def _growth(values: list[float]) -> list[float]:
    result = [0.0]
    for i in range(1, len(values)):
        prev = values[i - 1]
        result.append(0.0 if prev == 0 else (values[i] - prev) / prev * 100)
    return result


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

    selected_parties = st.multiselect(
        "Parties",
        options=PARTIES,
        default=PARTIES,
        format_func=lambda x: PARTY_LABELS.get(x, x),
    )

    use_share = st.radio("Display", ["Raw counts", "Share (%)"]) == "Share (%)"

    group_major_alt = st.checkbox("Group as Major vs Alternative", value=False)

regs = load_registrations(from_month, until_month)
months = [r["month"] for r in regs]
totals = [r["total"] for r in regs]

if not regs:
    st.warning("No data for the selected filters.")
    st.stop()

tab1, tab2, tab3 = st.tabs(
    ["Statewide Overview", "Party Comparison", "County Comparison"]
)

# ── Tab 1: Statewide Overview ──────────────────────────────────────────────

with tab1:
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
        ncols = min(len(selected_parties) + 1, 4)
        metric_cols = col2.columns(ncols)
        idx = 0

        metric_cols[idx].metric("Total", f"{latest['total']:,}")
        idx += 1

        for p in selected_parties[: ncols - 1]:
            metric_cols[idx].metric(
                PARTY_LABELS.get(p, p),
                f"{latest[p]:,}",
                delta=f"{latest[p] / latest['total'] * 100:.1f}%",
            )
            idx += 1

    if selected_parties:
        tab1.subheader("Party Trend Overlay")
        fig_overlay = go.Figure()
        fig_overlay.add_trace(go.Scatter(
            x=months, y=totals, mode="lines", name="Total",
            line=dict(color="#9ca3af", width=1, dash="dot"),
        ))

        show_parties = list(selected_parties)

        if group_major_alt and {"democratic", "republican"} & set(selected_parties):
            major_vals = compute_major(regs)
            alt_vals = compute_alternative(regs)
            show_parties = [p for p in selected_parties if p not in ("democratic", "republican")]

            if use_share:
                combined = [m + a for m, a in zip(major_vals, alt_vals)]
                major_disp = [m / c * 100 for m, c in zip(major_vals, combined)]
                alt_disp = [a / c * 100 for a, c in zip(alt_vals, combined)]
            else:
                major_disp = major_vals
                alt_disp = alt_vals

            fig_overlay.add_trace(go.Scatter(
                x=months, y=major_disp, mode="lines",
                name="Major (Dem + Rep)",
                line=dict(color=MAJOR_COLOR, width=2.5),
            ))
            fig_overlay.add_trace(go.Scatter(
                x=months, y=alt_disp, mode="lines",
                name="Alternative",
                line=dict(color=ALT_COLOR, width=2.5),
            ))

        for p in show_parties:
            vals = [r[p] for r in regs]
            if use_share:
                vals = [v / t * 100 for v, t in zip(vals, totals)]
            fig_overlay.add_trace(go.Scatter(
                x=months, y=vals, mode="lines",
                name=PARTY_LABELS.get(p, p),
                line=dict(dash="dot", width=1),
            ))

        fig_overlay.update_layout(
            title="Party Totals",
            hovermode="x unified",
            yaxis_title="Share (%)" if use_share else "Voters",
            legend=dict(font=dict(size=10)),
        )
        tab1.plotly_chart(fig_overlay, width='stretch')

# ── Tab 2: Party Comparison ────────────────────────────────────────────────

with tab2:
    if not selected_parties:
        tab2.info("Select at least one party in the sidebar to show comparison charts.")
    else:
        chart_style = tab2.radio(
            "Chart style",
            ["Overlaid lines", "Stacked area", "Stacked area (%)"],
            horizontal=True,
        )

        stacking = chart_style != "Overlaid lines"
        show_pct = chart_style == "Stacked area (%)"

        fig = go.Figure()

        if group_major_alt and {"democratic", "republican"} & set(selected_parties):
            show_parties = [p for p in selected_parties if p not in ("democratic", "republican")]
            major_vals = compute_major(regs)
            alt_vals = compute_alternative(regs)

            if show_pct:
                combined = [m + a for m, a in zip(major_vals, alt_vals)]
                major_disp = [m / c * 100 for m, c in zip(major_vals, combined)]
                alt_disp = [a / c * 100 for a, c in zip(alt_vals, combined)]
            else:
                major_disp = major_vals
                alt_disp = alt_vals

            fig.add_trace(go.Scatter(
                x=months, y=major_disp, mode="lines",
                name="Major (Dem + Rep)",
                stackgroup="one" if stacking else None,
                line=dict(width=0.5 if stacking else 2.5, color=MAJOR_COLOR),
            ))
            fig.add_trace(go.Scatter(
                x=months, y=alt_disp, mode="lines",
                name="Alternative",
                stackgroup="one" if stacking else None,
                line=dict(width=0.5 if stacking else 2.5, color=ALT_COLOR),
            ))

            for p in show_parties:
                vals = [r[p] for r in regs]
                if stacking:
                    continue
                fig.add_trace(go.Scatter(
                    x=months, y=vals, mode="lines",
                    name=PARTY_LABELS.get(p, p),
                    line=dict(dash="dot", width=1),
                ))
        else:
            for p in selected_parties:
                vals = [r[p] for r in regs]
                if show_pct:
                    vals = [v / t * 100 for v, t in zip(vals, totals)]
                fig.add_trace(go.Scatter(
                    x=months, y=vals, mode="lines",
                    name=PARTY_LABELS.get(p, p),
                    stackgroup="one" if stacking else None,
                    line=dict(width=0.5 if stacking else 2, color=PARTY_COLORS.get(p)),
                ))

        y_title = "Share (%)" if show_pct else "Voters"
        fig.update_layout(
            title="Party Comparison",
            hovermode="x unified",
            yaxis_title=y_title,
            legend=dict(font=dict(size=10)),
        )
        if show_pct:
            fig.update_layout(yaxis=dict(ticksuffix="%"))
        tab2.plotly_chart(fig, width='stretch')

        if len(selected_parties) >= 1:
            tab2.subheader("Month-over-Month Growth Rate")
            fig_growth = go.Figure()

            if group_major_alt and {"democratic", "republican"} & set(selected_parties):
                show_parties = [p for p in selected_parties if p not in ("democratic", "republican")]
                major_vals = compute_major(regs)
                alt_vals = compute_alternative(regs)
                fig_growth.add_trace(go.Scatter(
                    x=months, y=_growth(major_vals),
                    mode="lines", name="Major (Dem + Rep)",
                    line=dict(color=MAJOR_COLOR, width=2.5),
                ))
                fig_growth.add_trace(go.Scatter(
                    x=months, y=_growth(alt_vals),
                    mode="lines", name="Alternative",
                    line=dict(color=ALT_COLOR, width=2.5),
                ))
                for p in show_parties:
                    vals = [r[p] for r in regs]
                    fig_growth.add_trace(go.Scatter(
                        x=months, y=_growth(vals),
                        mode="lines", name=PARTY_LABELS.get(p, p),
                        line=dict(dash="dot", width=1),
                    ))
            else:
                for p in selected_parties:
                    vals = [r[p] for r in regs]
                    fig_growth.add_trace(go.Scatter(
                        x=months, y=_growth(vals),
                        mode="lines", name=PARTY_LABELS.get(p, p),
                        line=dict(color=PARTY_COLORS.get(p), width=1.5),
                    ))

            fig_growth.update_layout(
                hovermode="x unified",
                yaxis=dict(ticksuffix="%"),
                yaxis_title="Monthly Growth (%)",
                legend=dict(font=dict(size=10)),
            )
            tab2.plotly_chart(fig_growth, width='stretch')

# ── Tab 3: County Comparison ───────────────────────────────────────────────

with tab3:
    use_pct = tab3.checkbox("Show as % of county total", value=False)

    ky_geojson = _load_ky_geojson()
    if ky_geojson is not None and regs:
        all_months = [r["month"] for r in regs]
        map_month = tab3.select_slider(
            "Map month",
            options=all_months,
            value=all_months[-1],
        )
        cm_data = load_single_month_county_stats(map_month)
        cm_rows = [dict(r) for r in cm_data] if cm_data else []
        if cm_rows and selected_parties:
            map_party = selected_parties[0]
            if len(selected_parties) > 1:
                map_party = tab3.selectbox(
                    "Map party", options=selected_parties,
                    format_func=lambda p: PARTY_LABELS.get(p, p),
                    index=0,
                )
            map_vals = [r[map_party] for r in cm_rows]
            if use_pct:
                map_vals = [v / r["total"] * 100 for v, r in zip(map_vals, cm_rows)]
            fig_map = go.Figure(go.Choropleth(
                geojson=ky_geojson,
                locations=[r["fips"] for r in cm_rows],
                z=map_vals,
                text=[r["county_name"] for r in cm_rows],
                colorscale="Blues",
                colorbar_title=PARTY_LABELS.get(map_party, map_party),
                hovertemplate="%{text}<br>%{z:,.0f}" + ("%" if use_pct else ""),
            ))
            fig_map.update_geos(fitbounds="locations", visible=False)
            fig_map.update_layout(
                title=f"{PARTY_LABELS.get(map_party, map_party)} — {map_month}",
                height=500, margin=dict(l=0, r=0, t=30, b=0),
            )
            tab3.plotly_chart(fig_map, width='stretch')

    county_names = get_county_names()
    selected_counties = tab3.multiselect(
        "Select Counties",
        options=county_names,
        default=["JEFFERSON", "FAYETTE", "KENTON", "BOONE"],
    )

    if not selected_counties:
        tab3.info("Select at least one county above.")
    else:
        county_rows = load_county_stats(selected_counties, from_month, until_month)

        if group_major_alt and {"democratic", "republican"} & set(selected_parties):
            tab3.subheader("Major vs Alternative by County")
            fig_mc = go.Figure()
            for cname in selected_counties:
                cdata = [r for r in county_rows if r["county_name"] == cname]
                if not cdata:
                    continue
                major = [r["democratic"] + r["republican"] for r in cdata]
                alt = [sum(r[p] for p in _alt_parties()) for r in cdata]
                ctotals = [r["total"] for r in cdata]
                major_disp = [m / t * 100 for m, t in zip(major, ctotals)] if use_pct else major
                alt_disp = [a / t * 100 for a, t in zip(alt, ctotals)] if use_pct else alt
                fig_mc.add_trace(go.Scatter(
                    x=[r["month"] for r in cdata],
                    y=major_disp, mode="lines",
                    name=f"{cname} — Major",
                ))
                fig_mc.add_trace(go.Scatter(
                    x=[r["month"] for r in cdata],
                    y=alt_disp, mode="lines",
                    name=f"{cname} — Alt",
                    line=dict(dash="dot"),
                ))
            fig_mc.update_layout(
                title="County Comparison — Major vs Alternative",
                hovermode="x unified",
                yaxis_title="Share (%)" if use_pct else "Voters",
                legend=dict(font=dict(size=10)),
            )
            tab3.plotly_chart(fig_mc, width='stretch')

        if selected_parties:
            tab3.subheader("Party Breakdown by County")
            fig_cp = go.Figure()
            for cname in selected_counties:
                cdata = [r for r in county_rows if r["county_name"] == cname]
                if not cdata:
                    continue
                ctotals = [r["total"] for r in cdata]
                for p in selected_parties:
                    vals = [r[p] for r in cdata]
                    if use_pct:
                        vals = [v / t * 100 for v, t in zip(vals, ctotals)]
                    fig_cp.add_trace(go.Scatter(
                        x=[r["month"] for r in cdata],
                        y=vals, mode="lines",
                        name=f"{cname} — {PARTY_LABELS.get(p, p)}",
                    ))
            fig_cp.update_layout(
                title="County Comparison — Selected Parties",
                hovermode="x unified",
                yaxis_title="Share (%)" if use_pct else "Voters",
                legend=dict(font=dict(size=10)),
            )
            tab3.plotly_chart(fig_cp, width='stretch')

with st.expander("Raw Data"):
    st.dataframe(
        [dict(r) for r in regs],
        width='stretch',
        hide_index=True,
    )
