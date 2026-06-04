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
        "🐴 Horse Profile",
        "📁 Raw Data"
    ])
    
    st.markdown("---")
    st.markdown(f"<div style='font-size:11px;color:#6b6b80'>Today: {date.today()}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown("## 📊 RACEMODEL Dashboard")

    # ── Overall metrics ───────────────────────────────────────────────────────
    perf = query(conn, """
        SELECT COUNT(*) as total,
               SUM(place_result) as placed,
               SUM(win_result) as winners,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
               ROUND(AVG(COALESCE(profit_loss,0)),2) as avg_pnl,
               ROUND(AVG(clv),1) as avg_clv,
               ROUND(AVG(odds),2) as avg_odds
        FROM daily_selections WHERE result_loaded = TRUE
    """)

    col1,col2,col3,col4,col5 = st.columns(5)
    if not perf.empty:
        p = perf.iloc[0]
        col1.metric("Total Bets", int(p.total or 0))
        col2.metric("Place Rate", f"{p.place_pct or 0}%")
        pnl = p.pnl or 0
        col3.metric("Total P&L", f"{'+' if pnl>=0 else ''}{pnl}u")
        col4.metric("Avg CLV", f"{p.avg_clv:+.1f}%" if p.avg_clv else "N/A")
        col5.metric("Avg Odds", f"${p.avg_odds or 0}")

    st.markdown("---")

    # ── Row 1: P&L chart + Tier table ─────────────────────────────────────────
    col_left, col_right = st.columns([3,2])

    with col_left:
        st.markdown("#### Cumulative P&L")
        pnl_data = query(conn, """
            SELECT race_date,
                   ROUND(SUM(SUM(COALESCE(profit_loss,0))) OVER (ORDER BY race_date),2) as cum_pnl,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/COUNT(*),1) as strike
            FROM daily_selections WHERE result_loaded=TRUE
            GROUP BY race_date ORDER BY race_date
        """)
        if not pnl_data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pnl_data["race_date"], y=pnl_data["cum_pnl"],
                mode="lines+markers", line=dict(color="#34d399",width=2),
                marker=dict(size=6), fill="tozeroy",
                fillcolor="rgba(52,211,153,0.08)"
            ))
            fig.add_hline(y=0, line_dash="dash", line_color="#f87171", opacity=0.4)
            fig.update_layout(
                paper_bgcolor="#16161e", plot_bgcolor="#16161e",
                font=dict(color="#9898b0",size=11),
                margin=dict(l=0,r=0,t=0,b=0), height=220,
                xaxis=dict(gridcolor="#2a2a38"),
                yaxis=dict(gridcolor="#2a2a38",title="Units")
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("#### By Tier")
        tier_data = query(conn, """
            SELECT confidence_tier as tier,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
            FROM daily_selections
            WHERE result_loaded=TRUE AND confidence_tier IS NOT NULL
            GROUP BY 1 ORDER BY CASE confidence_tier WHEN 'ELITE' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
        """)
        if not tier_data.empty:
            st.dataframe(tier_data, use_container_width=True, hide_index=True)

        st.markdown("#### By BSP Bucket")
        bucket_data = query(conn, """
            SELECT bsp_bucket as bucket,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
            FROM daily_selections
            WHERE result_loaded=TRUE AND bsp_bucket IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        if not bucket_data.empty:
            st.dataframe(bucket_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Row 2: Claude Impact + Signal ROI ─────────────────────────────────────
    col_left2, col_right2 = st.columns([2,3])

    with col_left2:
        st.markdown("#### Claude Impact Report")
        bc_data = query(conn, """
            SELECT brain_check as verdict,
                   COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
                   ROUND(AVG(odds),2) as avg_odds
            FROM daily_selections
            WHERE result_loaded=TRUE AND brain_check IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        if not bc_data.empty:
            for _, row in bc_data.iterrows():
                emoji = "✅" if row.verdict=="BET" else ("⚠️" if row.verdict=="CAUTION" else "❌")
                pnl_col = "#34d399" if (row.pnl or 0)>=0 else "#f87171"
                st.markdown(f"""
                <div style="background:#16161e;border:1px solid #2a2a38;border-radius:8px;padding:10px 14px;margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                  <span style="font-weight:700;font-size:12px">{emoji} {row.verdict}</span>
                  <span style="font-size:18px;font-weight:700;color:#fff">{int(row.bets)}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:11px;color:#9898b0">
                  <span>Strike: <b style="color:#fff">{row.strike}%</b></span>
                  <span>P&L: <b style="color:{pnl_col}">{'+' if (row.pnl or 0)>=0 else ''}{row.pnl}u</b></span>
                  <span>Odds: <b style="color:#fff">${row.avg_odds}</b></span>
                </div>
                </div>
                """, unsafe_allow_html=True)

    with col_right2:
        st.markdown("#### Signal Strike Rate")
        sig_data = query(conn, """
            SELECT 'S1 Last Start' as sig, ROUND(AVG(CASE WHEN s1_last_start>0 THEN place_result END)*100,1) as pct, SUM(CASE WHEN s1_last_start>0 THEN 1 ELSE 0 END) as fired FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S2 Form Last 3', ROUND(AVG(CASE WHEN s2_form>0 THEN place_result END)*100,1), SUM(CASE WHEN s2_form>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S3 Course+Dist', ROUND(AVG(CASE WHEN s3_course_dist>0 THEN place_result END)*100,1), SUM(CASE WHEN s3_course_dist>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S4 BSP Ratio', ROUND(AVG(CASE WHEN s4_bsp_ratio>0 THEN place_result END)*100,1), SUM(CASE WHEN s4_bsp_ratio>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S12 Race Shape', ROUND(AVG(CASE WHEN s12_race_shape>0 THEN place_result END)*100,1), SUM(CASE WHEN s12_race_shape>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S14 Going', ROUND(AVG(CASE WHEN s14_going>0 THEN place_result END)*100,1), SUM(CASE WHEN s14_going>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S18 Place Rate', ROUND(AVG(CASE WHEN s18_place_rate>0 THEN place_result END)*100,1), SUM(CASE WHEN s18_place_rate>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            UNION ALL SELECT 'S19 Dist Form', ROUND(AVG(CASE WHEN s19_dist_form>0 THEN place_result END)*100,1), SUM(CASE WHEN s19_dist_form>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
            ORDER BY pct DESC NULLS LAST
        """)
        if not sig_data.empty:
            fig2 = go.Figure(go.Bar(
                x=sig_data["pct"], y=sig_data["sig"],
                orientation="h",
                marker_color="#60a5fa",
                text=[f"{int(f)} fired" for f in sig_data["fired"]],
                textposition="outside"
            ))
            fig2.update_layout(
                paper_bgcolor="#16161e", plot_bgcolor="#16161e",
                font=dict(color="#9898b0",size=11),
                margin=dict(l=0,r=60,t=0,b=0), height=260,
                xaxis=dict(gridcolor="#2a2a38", range=[0,110], title="Place %"),
                yaxis=dict(gridcolor="#2a2a38")
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ── Row 3: Top venues + Daily results ─────────────────────────────────────
    col_left3, col_right3 = st.columns([2,3])

    with col_left3:
        st.markdown("#### Top Venues (≥3 bets)")
        venue_data = query(conn, """
            SELECT course as venue, COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/COUNT(*),1) as strike,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
            FROM daily_selections
            WHERE result_loaded=TRUE
            GROUP BY course HAVING COUNT(*)>=3
            ORDER BY pnl DESC LIMIT 10
        """)
        if not venue_data.empty:
            st.dataframe(venue_data, use_container_width=True, hide_index=True)

    with col_right3:
        st.markdown("#### Daily Results")
        daily = query(conn, """
            SELECT race_date as date, COUNT(*) as bets,
                   ROUND(SUM(place_result)*100.0/COUNT(*),1) as strike,
                   ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
            FROM daily_selections WHERE result_loaded=TRUE
            GROUP BY race_date ORDER BY race_date DESC LIMIT 20
        """)
        if not daily.empty:
            st.dataframe(daily, use_container_width=True, hide_index=True, height=280)


elif page == "🏇 Selections":
    st.markdown("## 🏇 Daily Selections")

    # Hide today's unresulted selections until 7pm AEST (9am UTC)
    from datetime import datetime, timezone, timedelta as td
    aest_now = datetime.now(timezone.utc) + td(hours=10)
    cutoff_hour = 19  # 7pm AEST
    show_today = aest_now.hour >= cutoff_hour
    max_date = date.today() if show_today else date.today() - timedelta(days=1)

    if not show_today:
        st.info(f"⏰ Today's selections visible after 7pm AEST ({cutoff_hour - aest_now.hour}hrs remaining). Showing completed results only.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        date_from = st.date_input("From", value=date.today() - timedelta(days=14))
    with col2:
        date_to = st.date_input("To", value=max_date)
    with col3:
        tier_filter = st.multiselect("Tier", ["ELITE","MEDIUM","LOW"], default=["ELITE","MEDIUM","LOW"])
    with col4:
        bc_filter = st.multiselect("Brain Check", ["BET","CAUTION","SKIP"], default=["BET","CAUTION","SKIP"])

    tier_sql = "','".join(tier_filter) if tier_filter else "ELITE','MEDIUM','LOW"
    bc_sql = "','".join(bc_filter) if bc_filter else "BET','CAUTION','SKIP"

    # Only show result_loaded rows for today if before 7pm AEST
    result_filter = "AND (race_date < CURRENT_DATE OR result_loaded = TRUE)" if not show_today else ""

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
        {result_filter}
        ORDER BY race_date DESC, score DESC
    """)

    if not df.empty:
        # Filter by brain check
        if bc_filter:
            df = df[df['verdict'].isin(bc_filter)]

        st.markdown(f"**{len(df)} selections**")

        # Export button
        csv = df.to_csv(index=False)

        st.dataframe(df, use_container_width=True, hide_index=True, height=600)
    else:
        st.info("No selections found for selected filters")


# ══════════════════════════════════════════════════════════════════
# PAGE 3 — STREAM DATA
# ══════════════════════════════════════════════════════════════════
elif page == "🐴 Horse Profile":
    st.markdown("## 🐴 Horse Profile")

    horse_input = st.text_input("Search horse name", placeholder="e.g. Presides")

    if horse_input and len(horse_input) >= 2:
        h = horse_input.replace("'", "")

        # ── Key stats ─────────────────────────────────────────────────────────
        bsp_stats = query(conn, f"""
            SELECT COUNT(*) as runs,
                   SUM(CASE WHEN WIN_RESULT='WINNER' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN PLACE_RESULT='WINNER' THEN 1 ELSE 0 END) as places,
                   ROUND(SUM(CASE WHEN PLACE_RESULT='WINNER' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
                   ROUND(AVG(WIN_BSP),2) as avg_win_bsp,
                   ROUND(MIN(WIN_BSP),2) as best_bsp,
                   ROUND(MAX(WIN_BSP),2) as worst_bsp
            FROM anz_thoroughbreds
            WHERE LOWER(REPLACE(SELECTION_NAME,chr(39),'')) LIKE LOWER('%{h}%')
        """)

        if not bsp_stats.empty and (bsp_stats["runs"][0] or 0) > 0:
            st.markdown(f"### {horse_input}")
            col1,col2,col3,col4,col5,col6,col7 = st.columns(7)
            col1.metric("Total Runs", int(bsp_stats["runs"][0] or 0))
            col2.metric("Wins", int(bsp_stats["wins"][0] or 0))
            col3.metric("Places", int(bsp_stats["places"][0] or 0))
            col4.metric("Place Rate", f"{bsp_stats['place_pct'][0] or 0}%")
            col5.metric("Avg Win BSP", f"${bsp_stats['avg_win_bsp'][0] or 0}")
            col6.metric("Best BSP", f"${bsp_stats['best_bsp'][0] or 0}")
            col7.metric("Worst BSP", f"${bsp_stats['worst_bsp'][0] or 0}")
        else:
            st.markdown(f"### {horse_input}")
            st.info("No BSP history found in anz_thoroughbreds")

        st.markdown("---")

        # ── Block 1: BSP History ──────────────────────────────────────────────
        st.markdown("### 📊 BSP History")
        bsp = query(conn, f"""
            SELECT *
            FROM anz_thoroughbreds
            WHERE LOWER(REPLACE(SELECTION_NAME,chr(39),'')) LIKE LOWER('%{h}%')
            ORDER BY LOCAL_MEETING_DATE DESC
            LIMIT 50
        """)
        if not bsp.empty:
            st.dataframe(bsp, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No BSP history found")

        st.markdown("---")

        # ── Block 2: Win BSP Over Time chart ─────────────────────────────────
        st.markdown("### 📈 Win BSP Over Time")
        if not bsp.empty and len(bsp) > 1:
            fig = go.Figure()
            result_col = "WIN_RESULT" if "WIN_RESULT" in bsp.columns else "result"
            colors = ["#34d399" if r=="WINNER" else "#f87171" for r in bsp[result_col]]
            fig.add_trace(go.Scatter(
                x=bsp["date"], y=bsp["win_bsp"],
                mode="lines+markers",
                line=dict(color="#60a5fa", width=2),
                marker=dict(size=10, color=colors,
                    line=dict(color="#ffffff", width=1)),
                hovertemplate="<b>%{x}</b><br>BSP: $%{y}<extra></extra>"
            ))
            # Add place BSP line if available
            if "place_bsp" in bsp.columns and bsp["place_bsp"].notna().any():
                fig.add_trace(go.Scatter(
                    x=bsp["date"], y=bsp["place_bsp"],
                    mode="lines",
                    line=dict(color="#fbbf24", width=1, dash="dot"),
                    name="Place BSP",
                    hovertemplate="Place BSP: $%{y}<extra></extra>"
                ))
            fig.update_layout(
                paper_bgcolor="#16161e", plot_bgcolor="#16161e",
                font=dict(color="#9898b0"), height=250,
                margin=dict(l=0,r=0,t=10,b=0),
                xaxis=dict(gridcolor="#2a2a38"),
                yaxis=dict(gridcolor="#2a2a38", title="BSP ($)"),
                legend=dict(bgcolor="#16161e"),
                annotations=[dict(
                    x=0.01, y=0.95, xref="paper", yref="paper",
                    text="🟢 Win  🔴 Loss", showarrow=False,
                    font=dict(color="#9898b0", size=11)
                )]
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for chart")

        st.markdown("---")

        # ── Block 3: Punting Form ─────────────────────────────────────────────
        st.markdown("### 📝 Punting Form")

        # Today + history combined
        form = query(conn, f"""
            SELECT *
            FROM punting_form
            WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
            ORDER BY meeting_date DESC LIMIT 10
        """)

        if not form.empty:
            # Show records summary if available
            rec_query = query(conn, f"""
                SELECT career_record, dist_record, track_record,
                       track_dist_record, soft_record, heavy_record,
                       first_up_record, second_up_record,
                       horse_age, horse_sire, horse_dam
                FROM punting_form_history
                WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
                ORDER BY meeting_date DESC LIMIT 1
            """)
            if not rec_query.empty:
                r = rec_query.iloc[0]
                col1,col2,col3,col4 = st.columns(4)
                col1.metric("Career", r.get("career_record") or "—")
                col2.metric("Dist", r.get("dist_record") or "—")
                col3.metric("Soft", r.get("soft_record") or "—")
                col4.metric("Heavy", r.get("heavy_record") or "—")
                col1b,col2b,col3b,col4b = st.columns(4)
                col1b.metric("Track", r.get("track_record") or "—")
                col2b.metric("T+D", r.get("track_dist_record") or "—")
                col3b.metric("1st up", r.get("first_up_record") or "—")
                col4b.metric("2nd up", r.get("second_up_record") or "—")
                st.markdown(f"**Age:** {r.get('horse_age') or '—'} | **Sire:** {r.get('horse_sire') or '—'} | **Dam:** {r.get('horse_dam') or '—'}")
            st.markdown("**Today's form:**")
            st.dataframe(form, use_container_width=True, hide_index=True, height=250)
        else:
            st.info("No punting form for today")

        # Punting form history - all columns
        pf_hist = query(conn, f"""
            SELECT *
            FROM punting_form_history
            WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
            ORDER BY meeting_date DESC LIMIT 50
        """)
        if not pf_hist.empty:
            st.markdown("**Form history (Dropbox CSV):**")
            st.dataframe(pf_hist, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No form history yet — grows daily via Dropbox")

        st.markdown("---")

        # ── Block 4: Stream Data ──────────────────────────────────────────────
        st.markdown("### 📡 Stream Data")
        stream = query(conn, f"""
            SELECT *
            FROM betfair_stream
            WHERE LOWER(REPLACE(horse_name,chr(39),'')) LIKE LOWER('%{h}%')
            ORDER BY meeting_date DESC
            LIMIT 30
        """)
        if not stream.empty:
            # Steam summary
            steamers = stream[stream["steam_10"].notna() & (stream["steam_10"] > 15)]
            drifters = stream[stream["steam_10"].notna() & (stream["steam_10"] < -15)]
            col1,col2,col3 = st.columns(3)
            col1.metric("Stream Runs", len(stream))
            col2.metric("Steam >15%", len(steamers))
            col3.metric("Drift >15%", len(drifters))
            st.dataframe(stream, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No stream data found — load more months to expand coverage")

    else:
        st.markdown("### 👆 Enter a horse name above")
        st.info("Search any horse to see all available data: BSP history, punting form, stream data and price chart — all in one place.")


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
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)
