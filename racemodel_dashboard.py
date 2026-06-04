"""
RACEMODEL — Streamlit Dashboard
================================
Run locally:
    pip install streamlit duckdb==1.5.2 pandas plotly
    set MOTHERDUCK_TOKEN=your_token
    streamlit run racemodel_dashboard.py

Deploy to Streamlit Cloud:
    1. Push to GitHub
    2. Connect at share.streamlit.io
    3. Add MOTHERDUCK_TOKEN to secrets
"""

import os
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RACEMODEL",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    
    .main { background: #0e0e14; }
    
    .metric-card {
        background: #16161e;
        border: 1px solid #2a2a38;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .metric-label { font-size: 11px; color: #6b6b80; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px; }
    .metric-value { font-size: 28px; font-weight: 700; font-family: 'DM Mono', monospace; }
    .metric-sub { font-size: 12px; color: #6b6b80; margin-top: 2px; }
    
    .green { color: #34d399; }
    .red { color: #f87171; }
    .yellow { color: #fbbf24; }
    .blue { color: #60a5fa; }
    
    .verdict-bet { background: #0d2018; border: 1px solid #166534; border-radius: 6px; padding: 2px 8px; color: #34d399; font-size: 11px; font-weight: 600; }
    .verdict-caution { background: #1c1700; border: 1px solid #854d0e; border-radius: 6px; padding: 2px 8px; color: #fbbf24; font-size: 11px; font-weight: 600; }
    .verdict-skip { background: #1a0f0f; border: 1px solid #7f1d1d; border-radius: 6px; padding: 2px 8px; color: #f87171; font-size: 11px; font-weight: 600; }
    
    div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        background: #16161e; 
        border-radius: 8px; 
        border: 1px solid #2a2a38;
        color: #9898b0;
        font-size: 13px;
    }
    .stTabs [aria-selected="true"] { 
        background: #1e1e2e !important; 
        border-color: #60a5fa !important;
        color: #60a5fa !important;
    }
    
    .search-result {
        background: #16161e;
        border: 1px solid #2a2a38;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── Connection ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    try:
        token = os.environ.get("MOTHERDUCK_TOKEN", "")
        if not token:
            try:
                token = st.secrets["MOTHERDUCK_TOKEN"]
            except:
                pass
        if not token:
            st.error("⚠️ MOTHERDUCK_TOKEN not set. Add it in Streamlit Cloud → App settings → Secrets.")
            st.stop()
        conn = duckdb.connect(f"md:my_db?motherduck_token={token}", config={'custom_user_agent': 'racemodel'})
        return conn
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")
        st.stop()

@st.cache_data(ttl=300)
def query(_conn, sql):
    try:
        return _conn.execute(sql).df()
    except Exception as e:
        st.warning(f"Query error: {e}")
        import pandas as pd
        return pd.DataFrame()

conn = get_connection()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏇 RACEMODEL")
    st.markdown("---")
    
    page = st.radio("Navigation", [
        "📊 Dashboard",
        "🏇 Selections",
        "📡 Stream Data",
        "📈 Signal ROI",
        "🔍 Horse Lookup",
        "🐴 Horse Profile",
        "📁 Raw Data"
    ])
    
    st.markdown("---")
    st.markdown(f"<div style='font-size:11px;color:#6b6b80'>Today: {date.today()}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown("## 📊 Performance Dashboard")
    
    # ── Top metrics ───────────────────────────────────────────────
    perf = query(conn, """
        SELECT
            COUNT(*) as total,
            SUM(place_result) as placed,
            SUM(win_result) as winners,
            ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
            ROUND(SUM(profit_loss),2) as pnl,
            ROUND(AVG(profit_loss),2) as avg_pnl,
            ROUND(AVG(clv),1) as avg_clv,
            ROUND(AVG(odds),2) as avg_odds
        FROM daily_selections
        WHERE result_loaded = TRUE
    """)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Selections", int(perf['total'][0]))
    with col2:
        st.metric("Place Rate", f"{perf['place_pct'][0]}%")
    with col3:
        pnl = perf['pnl'][0] or 0
        st.metric("Total P&L", f"{'+' if pnl>=0 else ''}{pnl}u")
    with col4:
        avg_clv = perf['avg_clv'][0]
        st.metric("Avg CLV", f"{avg_clv:+.1f}%" if avg_clv else "N/A")
    with col5:
        st.metric("Avg Odds", f"${perf['avg_odds'][0]}")

    st.markdown("---")

    col_left, col_right = st.columns(2)
    
    with col_left:
        # ── Cumulative P&L chart ──────────────────────────────────
        st.markdown("#### Cumulative P&L")
        pnl_data = query(conn, """
            SELECT race_date,
                   ROUND(SUM(SUM(COALESCE(profit_loss,0))) OVER (ORDER BY race_date), 2) as cumulative_pnl,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/COUNT(*),1) as daily_place_pct
            FROM daily_selections
            WHERE result_loaded = TRUE
            GROUP BY race_date
            ORDER BY race_date
        """)
        if not pnl_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pnl_data['race_date'], y=pnl_data['cumulative_pnl'],
                mode='lines+markers', line=dict(color='#34d399', width=2),
                marker=dict(size=6), fill='tozeroy',
                fillcolor='rgba(52,211,153,0.1)'
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="#f87171", opacity=0.5)
            fig.update_layout(
                paper_bgcolor='#16161e', plot_bgcolor='#16161e',
                font=dict(color='#9898b0', size=11),
                margin=dict(l=0,r=0,t=0,b=0), height=250,
                xaxis=dict(gridcolor='#2a2a38', showgrid=True),
                yaxis=dict(gridcolor='#2a2a38', showgrid=True, title="Units")
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        # ── Tier breakdown ────────────────────────────────────────
        st.markdown("#### Performance by Tier")
        tier_data = query(conn, """
            SELECT confidence_tier as tier,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
                   ROUND(AVG(clv),1) as avg_clv
            FROM daily_selections
            WHERE result_loaded = TRUE AND confidence_tier IS NOT NULL
            GROUP BY confidence_tier
            ORDER BY CASE confidence_tier WHEN 'ELITE' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
        """)
        if not tier_data.empty:
            st.dataframe(tier_data, use_container_width=True, hide_index=True)

    # ── Brain check impact ────────────────────────────────────────
    st.markdown("#### Claude Impact Report")
    bc_data = query(conn, """
        SELECT brain_check as verdict,
               COUNT(*) as bets,
               SUM(place_result) as placed,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
               ROUND(AVG(odds),2) as avg_odds
        FROM daily_selections
        WHERE result_loaded = TRUE AND brain_check IS NOT NULL
        GROUP BY brain_check ORDER BY brain_check
    """)
    if not bc_data.empty:
        col1, col2, col3 = st.columns(3)
        for i, (col, row) in enumerate(zip([col1,col2,col3], bc_data.itertuples())):
            with col:
                emoji = "✅" if row.verdict=='BET' else ("⚠️" if row.verdict=='CAUTION' else "❌")
                pnl_color = "green" if row.pnl >= 0 else "red"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="display:flex;justify-content:space-between;margin-bottom:10px">
                        <span style="font-weight:700;font-size:13px">{emoji} {row.verdict}</span>
                        <span style="font-size:22px;font-weight:700">{row.bets}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #2a2a38">
                        <span style="font-size:11px;color:#6b6b80">Strike Rate</span>
                        <span style="font-size:12px;font-weight:600">{row.place_pct}%</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #2a2a38">
                        <span style="font-size:11px;color:#6b6b80">P&L</span>
                        <span style="font-size:12px;font-weight:600;color:{'#34d399' if row.pnl>=0 else '#f87171'}">{'+' if row.pnl>=0 else ''}{row.pnl}u</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:4px 0">
                        <span style="font-size:11px;color:#6b6b80">Avg Odds</span>
                        <span style="font-size:12px;font-weight:600">${row.avg_odds}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Daily P&L table ───────────────────────────────────────────
    st.markdown("#### Daily Results")
    daily = query(conn, """
        SELECT race_date as date,
               COUNT(*) as selections,
               ROUND(SUM(place_result)*100.0/COUNT(*),1) as place_pct,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
        FROM daily_selections
        WHERE result_loaded = TRUE
        GROUP BY race_date
        ORDER BY race_date DESC
        LIMIT 30
    """)
    st.dataframe(daily, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 2 — SELECTIONS
# ══════════════════════════════════════════════════════════════════
elif page == "🏇 Selections":
    st.markdown("## 🏇 Daily Selections")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        date_from = st.date_input("From", value=date.today() - timedelta(days=14))
    with col2:
        date_to = st.date_input("To", value=date.today())
    with col3:
        tier_filter = st.multiselect("Tier", ["ELITE","MEDIUM","LOW"], default=["ELITE","MEDIUM","LOW"])
    with col4:
        bc_filter = st.multiselect("Brain Check", ["BET","CAUTION","SKIP"], default=["BET","CAUTION","SKIP"])

    tier_sql = "','".join(tier_filter) if tier_filter else "ELITE','MEDIUM','LOW"
    bc_sql = "','".join(bc_filter) if bc_filter else "BET','CAUTION','SKIP"

    df = query(conn, f"""
        SELECT race_date, race_number as r, course, horse, score, odds,
               confidence_tier as tier, going, field_size as field,
               brain_check as verdict, brain_check_reason as reason,
               finish_position as pos, place_result as placed,
               win_result as won, place_bsp,
               ROUND(profit_loss,2) as pnl,
               ROUND(clv,1) as clv,
               s1_last_start as s1, s2_form as s2, s3_course_dist as s3,
               s4_bsp_ratio as s4, s5_draw as s5, s6_weight as s6,
               s7_jockey as s7, s8_trainer as s8, s9_resuming as s9,
               s12_race_shape as s12, s13_class as s13, s14_going as s14,
               s15_market as s15, s16_rating as s16, s17_value as s17,
               s18_place_rate as s18, s19_dist_form as s19,
               signals_hit, steam_flag
        FROM daily_selections
        WHERE race_date BETWEEN '{date_from}' AND '{date_to}'
        AND confidence_tier IN ('{tier_sql}')
        ORDER BY race_date DESC, score DESC
    """)

    if not df.empty:
        # Filter by brain check
        if bc_filter:
            df = df[df['verdict'].isin(bc_filter)]

        st.markdown(f"**{len(df)} selections**")

        # Export button
        csv = df.to_csv(index=False)
        st.download_button("⬇️ Export to CSV", csv, "racemodel_selections.csv", "text/csv")

        st.dataframe(df, use_container_width=True, hide_index=True, height=600)
    else:
        st.info("No selections found for selected filters")


# ══════════════════════════════════════════════════════════════════
# PAGE 3 — STREAM DATA
# ══════════════════════════════════════════════════════════════════
elif page == "📡 Stream Data":
    st.markdown("## 📡 Betfair Stream Data")

    col1, col2 = st.columns(2)
    with col1:
        stream_date = st.date_input("Date", value=date(2026, 4, 1))
    with col2:
        track_filter = st.text_input("Track (optional)", "")

    track_sql = f"AND LOWER(track) LIKE '%{track_filter.lower()}%'" if track_filter else ""

    stream_df = query(conn, f"""
        SELECT meeting_date as date, track, race_name as race,
               horse_name as horse, barrier, field_size as field,
               bsp_rank as rank,
               ROUND(win_bsp,2) as win_bsp,
               ROUND(place_bsp,2) as place_bsp,
               ROUND(price_30min,2) as p30min,
               ROUND(price_10min,2) as p10min,
               ROUND(price_1min,2) as p1min,
               ROUND(steam_pct_30to_bsp,1) as steam_30,
               ROUND(steam_pct_10to_bsp,1) as steam_10,
               ROUND(steam_pct_1to_bsp,1) as steam_1,
               ROUND(price_high,2) as p_high,
               ROUND(price_low,2) as p_low,
               num_price_updates as updates,
               price_direction_changes as dir_changes,
               win_result, place_result, scratched
        FROM betfair_stream
        WHERE meeting_date = '{stream_date}'
        {track_sql}
        AND scratched = FALSE
        ORDER BY track, race_name, bsp_rank
    """)

    if not stream_df.empty:
        st.markdown(f"**{len(stream_df)} runners** on {stream_date}")
        st.download_button("⬇️ Export to CSV", stream_df.to_csv(index=False), "stream_data.csv", "text/csv")
        st.dataframe(stream_df, use_container_width=True, hide_index=True, height=600)

        # Steam distribution
        st.markdown("#### Steam Distribution (10min to BSP)")
        steam_clean = stream_df[stream_df['steam_10'].notna() & stream_df['win_bsp'].notna()]
        if not steam_clean.empty:
            fig = px.histogram(steam_clean, x='steam_10', nbins=40,
                              color_discrete_sequence=['#60a5fa'])
            fig.update_layout(
                paper_bgcolor='#16161e', plot_bgcolor='#16161e',
                font=dict(color='#9898b0'), height=200,
                margin=dict(l=0,r=0,t=0,b=0),
                xaxis_title="Steam % (positive = shortened)",
                yaxis_title="Count"
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No stream data for {stream_date}")

    # Summary stats
    st.markdown("#### Stream Data Summary")
    summary = query(conn, """
        SELECT YEAR(meeting_date) as year,
               MONTHNAME(meeting_date) as month,
               COUNT(DISTINCT meeting_date) as days,
               COUNT(*) as runners,
               SUM(CASE WHEN win_bsp IS NOT NULL THEN 1 ELSE 0 END) as has_win_bsp,
               SUM(CASE WHEN place_bsp IS NOT NULL THEN 1 ELSE 0 END) as has_place_bsp,
               SUM(CASE WHEN price_10min IS NOT NULL THEN 1 ELSE 0 END) as has_steam
        FROM betfair_stream
        GROUP BY 1, 2, MONTH(meeting_date)
        ORDER BY 1, MONTH(meeting_date)
    """)
    st.dataframe(summary, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 4 — SIGNAL ROI
# ══════════════════════════════════════════════════════════════════
elif page == "📈 Signal ROI":
    st.markdown("## 📈 Signal Strike Rate")

    signal_data = query(conn, """
        SELECT
            'S1 Last Start'   as signal, AVG(CASE WHEN s1_last_start  > 0 THEN place_result END)*100 as place_pct, SUM(CASE WHEN s1_last_start  > 0 THEN 1 ELSE 0 END) as fired
        FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S2 Form Last 3', AVG(CASE WHEN s2_form > 0 THEN place_result END)*100, SUM(CASE WHEN s2_form > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S3 Course+Dist', AVG(CASE WHEN s3_course_dist > 0 THEN place_result END)*100, SUM(CASE WHEN s3_course_dist > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S4 BSP Ratio', AVG(CASE WHEN s4_bsp_ratio > 0 THEN place_result END)*100, SUM(CASE WHEN s4_bsp_ratio > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S12 Race Shape', AVG(CASE WHEN s12_race_shape > 0 THEN place_result END)*100, SUM(CASE WHEN s12_race_shape > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S14 Going', AVG(CASE WHEN s14_going > 0 THEN place_result END)*100, SUM(CASE WHEN s14_going > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S18 Place Rate', AVG(CASE WHEN s18_place_rate > 0 THEN place_result END)*100, SUM(CASE WHEN s18_place_rate > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S19 Dist Form', AVG(CASE WHEN s19_dist_form > 0 THEN place_result END)*100, SUM(CASE WHEN s19_dist_form > 0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        ORDER BY place_pct DESC
    """)

    if not signal_data.empty:
        signal_data['place_pct'] = signal_data['place_pct'].round(1)
        fig = px.bar(signal_data, x='place_pct', y='signal', orientation='h',
                    color='place_pct', color_continuous_scale='Teal',
                    text='fired')
        fig.update_traces(texttemplate='%{text} fired', textposition='outside')
        fig.update_layout(
            paper_bgcolor='#16161e', plot_bgcolor='#16161e',
            font=dict(color='#9898b0'), height=350,
            margin=dict(l=0,r=80,t=0,b=0),
            xaxis_title="Place % when signal fired",
            yaxis_title="", coloraxis_showscale=False
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(signal_data, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 5 — HORSE LOOKUP
# ══════════════════════════════════════════════════════════════════
elif page == "🔍 Horse Lookup":
    st.markdown("## 🔍 Horse Lookup")
    st.markdown("Search a horse name across all data sources")

    horse_name = st.text_input("Horse name", placeholder="e.g. Presides")

    if horse_name and len(horse_name) >= 2:
        tabs = st.tabs(["📋 Selections", "📊 BSP History", "📡 Stream", "📝 Form"])

        with tabs[0]:
            sel = query(conn, f"""
                SELECT race_date, course, race_number as race, score, odds,
                       confidence_tier as tier, going, brain_check as verdict,
                       finish_position as pos, place_result as placed,
                       ROUND(profit_loss,2) as pnl, ROUND(clv,1) as clv,
                       signals_hit
                FROM daily_selections
                WHERE LOWER(horse) LIKE LOWER('%{horse_name}%')
                ORDER BY race_date DESC
            """)
            st.markdown(f"**{len(sel)} pipeline selections**")
            if not sel.empty:
                st.dataframe(sel, use_container_width=True, hide_index=True)
            else:
                st.info("No pipeline selections found")

        with tabs[1]:
            bsp = query(conn, f"""
                SELECT LOCAL_MEETING_DATE as date, TRACK as track,
                       WIN_MARKET_NAME as race,
                       ROUND(WIN_BSP,2) as win_bsp,
                       ROUND(PLACE_BSP,2) as place_bsp,
                       WIN_RESULT as result, PLACE_RESULT as placed,
                       ROUND(WIN_BSP_VOLUME,0) as volume,
                       DISTANCE as distance
                FROM anz_thoroughbreds
                WHERE LOWER(SELECTION_NAME) LIKE LOWER('%{horse_name}%')
                ORDER BY LOCAL_MEETING_DATE DESC
                LIMIT 50
            """)
            st.markdown(f"**{len(bsp)} BSP runs** (PROMO data)")
            if not bsp.empty:
                place_rate = round(bsp['placed'].eq('WINNER').sum() / len(bsp) * 100, 1)
                win_rate = round(bsp['result'].eq('WINNER').sum() / len(bsp) * 100, 1)
                col1, col2, col3 = st.columns(3)
                col1.metric("Runs", len(bsp))
                col2.metric("Place Rate", f"{place_rate}%")
                col3.metric("Win Rate", f"{win_rate}%")
                st.dataframe(bsp, use_container_width=True, hide_index=True)
            else:
                st.info("No BSP history found")

        with tabs[2]:
            stream = query(conn, f"""
                SELECT meeting_date as date, track, race_name as race,
                       ROUND(win_bsp,2) as win_bsp,
                       ROUND(place_bsp,2) as place_bsp,
                       bsp_rank as rank, field_size as field,
                       ROUND(price_10min,2) as p10min,
                       ROUND(steam_pct_10to_bsp,1) as steam_10,
                       ROUND(steam_pct_1to_bsp,1) as steam_1,
                       price_direction_changes as dir_changes,
                       win_result, place_result
                FROM betfair_stream
                WHERE LOWER(horse_name) LIKE LOWER('%{horse_name}%')
                ORDER BY meeting_date DESC
                LIMIT 50
            """)
            st.markdown(f"**{len(stream)} stream runs**")
            if not stream.empty:
                st.dataframe(stream, use_container_width=True, hide_index=True)
            else:
                st.info("No stream data found")

        with tabs[3]:
            form = query(conn, f"""
                SELECT meeting_date as date, track, race_number as race,
                       race_class as class, distance,
                       barrier, weight, jockey, trainer,
                       last10, prep_runs,
                       soft_starts, soft_wins, heavy_starts, heavy_wins,
                       neural_price, rated_run_style as style,
                       place_pct, career_starts
                FROM punting_form
                WHERE LOWER(horse_name) LIKE LOWER('%{horse_name}%')
                ORDER BY meeting_date DESC
                LIMIT 20
            """)
            st.markdown(f"**{len(form)} form entries**")
            if not form.empty:
                st.dataframe(form, use_container_width=True, hide_index=True)
            else:
                st.info("No punting form found")


# ══════════════════════════════════════════════════════════════════
# PAGE 6 — RAW DATA
# ══════════════════════════════════════════════════════════════════

elif page == "🐴 Horse Profile":
    st.markdown("## 🐴 Horse Profile")
    st.markdown("All data from every source in one window")

    horse_input = st.text_input("Horse name", placeholder="e.g. Presides")

    if horse_input and len(horse_input) >= 2:
        h = horse_input.replace("'", "")
        st.markdown(f"### {horse_input}")

        # Key stats row
        bsp_stats = query(conn, f"""
            SELECT COUNT(*) as runs,
                   SUM(CASE WHEN WIN_RESULT='WINNER' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN PLACE_RESULT='WINNER' THEN 1 ELSE 0 END) as places,
                   ROUND(AVG(WIN_BSP),2) as avg_win_bsp,
                   ROUND(AVG(PLACE_BSP),2) as avg_place_bsp
            FROM anz_thoroughbreds
            WHERE LOWER(REPLACE(SELECTION_NAME,chr(39),'')) LIKE LOWER('%{h}%')
        """)

        sel_stats = query(conn, f"""
            SELECT COUNT(*) as selections,
                   SUM(place_result) as placed,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
                   ROUND(AVG(score),1) as avg_score
            FROM daily_selections
            WHERE LOWER(REPLACE(horse,chr(39),'')) LIKE LOWER('%{h}%')
            AND result_loaded = TRUE
        """)

        col1,col2,col3,col4,col5 = st.columns(5)
        if not bsp_stats.empty:
            col1.metric("Total Runs", int(bsp_stats['runs'][0] or 0))
            col2.metric("Wins", int(bsp_stats['wins'][0] or 0))
            col3.metric("Places", int(bsp_stats['places'][0] or 0))
            col4.metric("Avg Win BSP", f"${bsp_stats['avg_win_bsp'][0] or 0}")
        if not sel_stats.empty and (sel_stats['selections'][0] or 0) > 0:
            pnl = sel_stats['pnl'][0] or 0
            col5.metric("Pipeline P&L", f"{'+' if pnl>=0 else ''}{pnl}u")

        st.markdown("---")

        # BSP + Pipeline side by side
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**📊 BSP History (PROMO)**")
            bsp = query(conn, f"""
                SELECT LOCAL_MEETING_DATE as date, TRACK as track,
                       WIN_MARKET_NAME as race,
                       ROUND(WIN_BSP,2) as win_bsp,
                       ROUND(PLACE_BSP,2) as place_bsp,
                       WIN_RESULT as result, PLACE_RESULT as placed
                FROM anz_thoroughbreds
                WHERE LOWER(REPLACE(SELECTION_NAME,chr(39),'')) LIKE LOWER('%{h}%')
                ORDER BY LOCAL_MEETING_DATE DESC LIMIT 30
            """)
            if not bsp.empty:
                st.dataframe(bsp, use_container_width=True, hide_index=True, height=280)
            else:
                st.info("No BSP history")

        with col_b:
            st.markdown("**🏇 Pipeline Selections**")
            pipe = query(conn, f"""
                SELECT race_date as date, course, race_number as r,
                       score, odds, confidence_tier as tier,
                       brain_check as verdict, going,
                       finish_position as pos, place_result as placed,
                       ROUND(profit_loss,2) as pnl
                FROM daily_selections
                WHERE LOWER(REPLACE(horse,chr(39),'')) LIKE LOWER('%{h}%')
                ORDER BY race_date DESC
            """)
            if not pipe.empty:
                st.dataframe(pipe, use_container_width=True, hide_index=True, height=280)
            else:
                st.info("Not in pipeline")

        # Stream + Form side by side
        col_c, col_d = st.columns(2)
        with col_c:
            st.markdown("**📡 Stream Data**")
            stream = query(conn, f"""
                SELECT meeting_date as date, track, race_name as race,
                       ROUND(win_bsp,2) as win_bsp,
                       ROUND(place_bsp,2) as place_bsp,
                       bsp_rank as rank, field_size as field,
                       ROUND(price_10min,2) as p10min,
                       ROUND(steam_pct_10to_bsp,1) as steam_10,
                       win_result, place_result
                FROM betfair_stream
                WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
                ORDER BY meeting_date DESC LIMIT 20
            """)
            if not stream.empty:
                st.dataframe(stream, use_container_width=True, hide_index=True, height=280)
            else:
                st.info("No stream data")

        with col_d:
            st.markdown("**📝 Punting Form (today + history)**")
            form = query(conn, f"""
                SELECT meeting_date as date, track, race_class as class,
                       distance, barrier, weight, jockey,
                       last10, neural_price, rated_run_style as style,
                       soft_starts, soft_wins, heavy_starts, heavy_wins,
                       place_pct, career_starts
                FROM punting_form
                WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
                UNION ALL
                SELECT meeting_date, track, race_class,
                       race_distance as distance, barrier, weight, jockey,
                       horse_last10 as last10, NULL as neural_price, NULL as rated_run_style,
                       NULL as soft_starts, NULL as soft_wins, NULL as heavy_starts, NULL as heavy_wins,
                       NULL as place_pct, NULL as career_starts
                FROM punting_form_history
                WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
                ORDER BY date DESC LIMIT 20
            """)
            if not form.empty:
                st.dataframe(form, use_container_width=True, hide_index=True, height=280)
            else:
                st.info("No form data — punting_form_history grows daily via Dropbox")

        # BSP price chart
        if not bsp.empty and len(bsp) > 2:
            st.markdown("**📈 Win BSP Over Time**")
            fig = go.Figure()
            colors = ['#34d399' if r=='WINNER' else '#f87171' for r in bsp['result']]
            fig.add_trace(go.Scatter(
                x=bsp['date'], y=bsp['win_bsp'],
                mode='lines+markers',
                line=dict(color='#60a5fa', width=2),
                marker=dict(size=8, color=colors)
            ))
            fig.update_layout(
                paper_bgcolor='#16161e', plot_bgcolor='#16161e',
                font=dict(color='#9898b0'), height=200,
                margin=dict(l=0,r=0,t=10,b=0),
                xaxis=dict(gridcolor='#2a2a38'),
                yaxis=dict(gridcolor='#2a2a38', title="Win BSP")
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("👆 Enter a horse name to see all data in one window")

elif page == "📁 Raw Data":
    st.markdown("## 📁 Raw Data")

    table = st.selectbox("Table", [
        "daily_selections",
        "anz_thoroughbreds",
        "betfair_stream",
        "punting_form",
        "punting_form_history"
    ])

    col1, col2, col3 = st.columns(3)
    with col1:
        limit = st.number_input("Rows", min_value=10, max_value=10000, value=200, step=50)
    with col2:
        custom_sql = st.text_input("WHERE clause", placeholder="e.g. track='Kembla Grange'")
    with col3:
        search_horse = st.text_input("Search horse", placeholder="e.g. Presides")

    filters = []
    if custom_sql:
        filters.append(custom_sql)
    if search_horse:
        if table == "anz_thoroughbreds":
            filters.append(f"LOWER(SELECTION_NAME) LIKE LOWER('%{search_horse}%')")
        elif table in ("punting_form","punting_form_history","betfair_stream"):
            filters.append(f"LOWER(horse_name) LIKE LOWER('%{search_horse}%')")
        else:
            filters.append(f"LOWER(horse) LIKE LOWER('%{search_horse}%')")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    if table == "anz_thoroughbreds":
        order = "ORDER BY LOCAL_MEETING_DATE DESC"
    else:
        order = "ORDER BY 1 DESC"

    df = query(conn, f"SELECT * FROM {table} {where} {order} LIMIT {limit}")

    st.markdown(f"**{len(df)} rows** from `{table}`")
    st.markdown(f"**{len(df)} rows** from `{table}`")
    if not df.empty:
        all_cols = list(df.columns)
        show_cols = st.multiselect("Columns to display", all_cols, default=all_cols, key="raw_cols")
        if show_cols:
            df = df[show_cols]
    st.download_button("⬇️ Export CSV", df.to_csv(index=False), f"{table}.csv", "text/csv")
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)
