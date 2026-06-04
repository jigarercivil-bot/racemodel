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
    
    /* Disable text selection on horse profile data */
    .no-select {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    /* Disable selection on all dataframes in horse profile */
    [data-testid="stDataFrame"] {
        -webkit-user-select: none;
        -moz-user-select: none;
        user-select: none;
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

    # ── Fetch all data ────────────────────────────────────────────────────────
    perf = query(conn, """
        SELECT COUNT(*) as total, SUM(place_result) as placed,
               SUM(win_result) as winners,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as place_pct,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl,
               ROUND(AVG(clv),1) as avg_clv,
               ROUND(AVG(odds),2) as avg_odds
        FROM daily_selections WHERE result_loaded=TRUE
    """)

    pnl_data = query(conn, """
        SELECT race_date,
               ROUND(SUM(SUM(COALESCE(profit_loss,0))) OVER (ORDER BY race_date),2) as cum_pnl,
               COUNT(*) as bets,
               ROUND(SUM(place_result)*100.0/COUNT(*),1) as strike
        FROM daily_selections WHERE result_loaded=TRUE
        GROUP BY race_date ORDER BY race_date
    """)

    tier_data = query(conn, """
        SELECT confidence_tier as tier, COUNT(*) as bets,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
        FROM daily_selections WHERE result_loaded=TRUE AND confidence_tier IS NOT NULL
        GROUP BY 1 ORDER BY CASE confidence_tier WHEN 'ELITE' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
    """)

    bc_data = query(conn, """
        SELECT brain_check as verdict, COUNT(*) as bets,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
        FROM daily_selections WHERE result_loaded=TRUE AND brain_check IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """)

    sig_data = query(conn, """
        SELECT 'S1' as sig, ROUND(AVG(CASE WHEN s1_last_start>0 THEN place_result END)*100,1) as pct, SUM(CASE WHEN s1_last_start>0 THEN 1 ELSE 0 END) as fired FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S2', ROUND(AVG(CASE WHEN s2_form>0 THEN place_result END)*100,1), SUM(CASE WHEN s2_form>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S3', ROUND(AVG(CASE WHEN s3_course_dist>0 THEN place_result END)*100,1), SUM(CASE WHEN s3_course_dist>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S4', ROUND(AVG(CASE WHEN s4_bsp_ratio>0 THEN place_result END)*100,1), SUM(CASE WHEN s4_bsp_ratio>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S12', ROUND(AVG(CASE WHEN s12_race_shape>0 THEN place_result END)*100,1), SUM(CASE WHEN s12_race_shape>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S14', ROUND(AVG(CASE WHEN s14_going>0 THEN place_result END)*100,1), SUM(CASE WHEN s14_going>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S18', ROUND(AVG(CASE WHEN s18_place_rate>0 THEN place_result END)*100,1), SUM(CASE WHEN s18_place_rate>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        UNION ALL SELECT 'S19', ROUND(AVG(CASE WHEN s19_dist_form>0 THEN place_result END)*100,1), SUM(CASE WHEN s19_dist_form>0 THEN 1 ELSE 0 END) FROM daily_selections WHERE result_loaded=TRUE
        ORDER BY pct DESC NULLS LAST
    """)

    venue_data = query(conn, """
        SELECT course as venue, COUNT(*) as bets,
               ROUND(SUM(place_result)*100.0/NULLIF(COUNT(*),0),1) as strike,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
        FROM daily_selections WHERE result_loaded=TRUE
        GROUP BY course HAVING COUNT(*)>=3
        ORDER BY pnl DESC LIMIT 8
    """)

    daily = query(conn, """
        SELECT race_date as date, COUNT(*) as bets,
               ROUND(SUM(place_result)*100.0/COUNT(*),1) as strike,
               ROUND(SUM(COALESCE(profit_loss,0)),2) as pnl
        FROM daily_selections WHERE result_loaded=TRUE
        GROUP BY race_date ORDER BY race_date DESC LIMIT 14
    """)

    # ── Extract values ────────────────────────────────────────────────────────
    p = perf.iloc[0] if not perf.empty else None
    total = int(p.total or 0) if p is not None else 0
    placed = int(p.placed or 0) if p is not None else 0
    winners = int(p.winners or 0) if p is not None else 0
    place_pct = float(p.place_pct or 0) if p is not None else 0
    pnl_total = float(p.pnl or 0) if p is not None else 0
    avg_clv = float(p.avg_clv or 0) if p is not None else 0
    avg_odds = float(p.avg_odds or 0) if p is not None else 0
    latest_cum = float(pnl_data["cum_pnl"].iloc[-1]) if not pnl_data.empty else 0

    pnl_color = "#10b981" if pnl_total >= 0 else "#ef4444"
    pnl_arrow = "▲" if pnl_total >= 0 else "▼"

    # ── Header banner ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    .rm-header {{
        background: linear-gradient(135deg, #0a0a12 0%, #0f1729 50%, #0a0a12 100%);
        border: 1px solid #1e3a5f;
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }}
    .rm-header::before {{
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(16,185,129,0.06) 0%, transparent 70%);
        pointer-events: none;
    }}
    .rm-title {{
        font-family: 'Syne', sans-serif;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.25em;
        color: #10b981;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}
    .rm-subtitle {{
        font-family: 'Syne', sans-serif;
        font-size: 28px;
        font-weight: 800;
        color: #f0f0f8;
        margin-bottom: 20px;
    }}
    .rm-kpi-row {{
        display: flex;
        gap: 32px;
        flex-wrap: wrap;
    }}
    .rm-kpi {{
        display: flex;
        flex-direction: column;
    }}
    .rm-kpi-label {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 2px;
    }}
    .rm-kpi-value {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 22px;
        font-weight: 500;
        color: #f0f0f8;
    }}
    .rm-kpi-value.green {{ color: #10b981; }}
    .rm-kpi-value.red {{ color: #ef4444; }}

    .rm-section {{
        font-family: 'Syne', sans-serif;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #4b5563;
        margin: 20px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .rm-section::after {{
        content: '';
        flex: 1;
        height: 1px;
        background: #1f2937;
    }}

    .rm-bc-card {{
        background: #0d1117;
        border-radius: 12px;
        padding: 16px 18px;
        border: 1px solid #1f2937;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }}
    .rm-bc-card:hover {{ border-color: #374151; }}
    .rm-bc-card.bet {{ border-left: 3px solid #10b981; }}
    .rm-bc-card.caution {{ border-left: 3px solid #f59e0b; }}
    .rm-bc-card.skip {{ border-left: 3px solid #ef4444; }}
    .rm-bc-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }}
    .rm-bc-label {{ font-family: 'Syne', sans-serif; font-weight: 700; font-size: 13px; }}
    .rm-bc-count {{ font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 500; color: #f0f0f8; }}
    .rm-bc-stats {{
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 4px;
    }}
    .rm-bc-stat {{ text-align: center; }}
    .rm-bc-stat-val {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 500; }}
    .rm-bc-stat-lbl {{ font-size: 9px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; }}
    </style>

    <div class="rm-header">
        <div class="rm-title">🏇 RACEMODEL v3</div>
        <div class="rm-subtitle">Australian Thoroughbred Place Betting</div>
        <div class="rm-kpi-row">
            <div class="rm-kpi">
                <div class="rm-kpi-label">Total Bets</div>
                <div class="rm-kpi-value">{total}</div>
            </div>
            <div class="rm-kpi">
                <div class="rm-kpi-label">Place Rate</div>
                <div class="rm-kpi-value {'green' if place_pct >= 50 else 'red'}">{place_pct}%</div>
            </div>
            <div class="rm-kpi">
                <div class="rm-kpi-label">Total P&L</div>
                <div class="rm-kpi-value {'green' if pnl_total >= 0 else 'red'}">{pnl_arrow} {abs(pnl_total):.2f}u</div>
            </div>
            <div class="rm-kpi">
                <div class="rm-kpi-label">Avg CLV</div>
                <div class="rm-kpi-value {'green' if avg_clv >= 0 else 'red'}">{avg_clv:+.1f}%</div>
            </div>
            <div class="rm-kpi">
                <div class="rm-kpi-label">Avg Odds</div>
                <div class="rm-kpi-value">${avg_odds}</div>
            </div>
            <div class="rm-kpi">
                <div class="rm-kpi-label">Winners</div>
                <div class="rm-kpi-value">{winners}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Row 1: P&L Chart + Tier breakdown ─────────────────────────────────────
    st.markdown('<div class="rm-section">📈 Cumulative Performance</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])

    with col1:
        if not pnl_data.empty:
            fig = go.Figure()
            # Area fill
            fig.add_trace(go.Scatter(
                x=pnl_data["race_date"], y=pnl_data["cum_pnl"],
                mode="lines", line=dict(color="rgba(16,185,129,0)", width=0),
                fill="tozeroy", fillcolor="rgba(16,185,129,0.06)",
                showlegend=False, hoverinfo="skip"
            ))
            # Main line
            fig.add_trace(go.Scatter(
                x=pnl_data["race_date"], y=pnl_data["cum_pnl"],
                mode="lines+markers",
                line=dict(color="#10b981", width=2.5),
                marker=dict(
                    size=[10 if i == len(pnl_data)-1 else 5 for i in range(len(pnl_data))],
                    color=["#10b981" if v >= 0 else "#ef4444" for v in pnl_data["cum_pnl"]],
                    line=dict(color="#0d1117", width=2)
                ),
                customdata=pnl_data[["bets","strike"]].values,
                hovertemplate="<b>%{x}</b><br>P&L: %{y:+.2f}u<br>Bets: %{customdata[0]}<br>Strike: %{customdata[1]}%<extra></extra>"
            ))
            fig.add_hline(y=0, line_dash="dot", line_color="#374151", opacity=0.8)
            fig.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#9ca3af", family="JetBrains Mono", size=10),
                margin=dict(l=0,r=0,t=0,b=0), height=220,
                xaxis=dict(gridcolor="#1f2937", showgrid=True, zeroline=False),
                yaxis=dict(gridcolor="#1f2937", showgrid=True, zeroline=False, title="Units"),
                showlegend=False,
                hoverlabel=dict(bgcolor="#1f2937", bordercolor="#374151", font_color="#f0f0f8")
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not tier_data.empty:
            for _, row in tier_data.iterrows():
                emoji = "💎" if row.tier=="ELITE" else ("⭐" if row.tier=="MEDIUM" else "📌")
                pnl_c = "#10b981" if (row.pnl or 0)>=0 else "#ef4444"
                st.markdown(f"""
                <div style="background:#0d1117;border:1px solid #1f2937;border-radius:10px;padding:12px;margin-bottom:8px">
                <div style="font-family:'Syne',sans-serif;font-size:12px;font-weight:700;color:#f0f0f8;margin-bottom:8px">{emoji} {row.tier}</div>
                <div style="display:flex;justify-content:space-between;font-size:10px;color:#9ca3af;font-family:'JetBrains Mono',monospace">
                  <div><div style="font-size:14px;color:#f0f0f8;font-weight:500">{int(row.bets)}</div>bets</div>
                  <div><div style="font-size:14px;color:#60a5fa;font-weight:500">{row.strike}%</div>strike</div>
                  <div><div style="font-size:14px;color:{pnl_c};font-weight:500">{'+' if (row.pnl or 0)>=0 else ''}{row.pnl}u</div>p&l</div>
                </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Row 2: Signal radar + Claude Impact ───────────────────────────────────
    st.markdown('<div class="rm-section">🎯 Signal Analysis & Brain Check</div>', unsafe_allow_html=True)
    col3, col4 = st.columns([2, 1])

    with col3:
        if not sig_data.empty:
            sig_clean = sig_data.dropna(subset=["pct"])
            fig2 = go.Figure()
            colors = ["#10b981" if v >= 55 else "#f59e0b" if v >= 45 else "#ef4444" for v in sig_clean["pct"]]
            fig2.add_trace(go.Bar(
                x=sig_clean["sig"], y=sig_clean["pct"],
                marker_color=colors,
                marker_line_width=0,
                text=[f"{v:.0f}%" for v in sig_clean["pct"]],
                textposition="outside",
                textfont=dict(family="JetBrains Mono", size=11, color="#9ca3af"),
                customdata=sig_clean["fired"].values,
                hovertemplate="<b>%{x}</b><br>Strike: %{y:.1f}%<br>Fired: %{customdata}x<extra></extra>"
            ))
            fig2.add_hline(y=50, line_dash="dot", line_color="#374151", opacity=0.6,
                          annotation_text="50%", annotation_font_color="#4b5563")
            fig2.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#9ca3af", family="JetBrains Mono", size=10),
                margin=dict(l=0,r=0,t=20,b=0), height=220,
                xaxis=dict(gridcolor="#1f2937", showgrid=False),
                yaxis=dict(gridcolor="#1f2937", showgrid=True, range=[0,110], title="Place %"),
                bargap=0.3,
                hoverlabel=dict(bgcolor="#1f2937", bordercolor="#374151", font_color="#f0f0f8")
            )
            st.plotly_chart(fig2, use_container_width=True)

    with col4:
        if not bc_data.empty:
            for _, row in bc_data.iterrows():
                emoji = "✅" if row.verdict=="BET" else ("⚠️" if row.verdict=="CAUTION" else "❌")
                card_class = row.verdict.lower()
                pnl_c = "#10b981" if (row.pnl or 0)>=0 else "#ef4444"
                border_c = "#10b981" if row.verdict=="BET" else "#f59e0b" if row.verdict=="CAUTION" else "#ef4444"
                st.markdown(f"""
                <div style="background:#0d1117;border:1px solid #1f2937;border-left:3px solid {border_c};border-radius:10px;padding:14px 16px;margin-bottom:8px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                  <span style="font-family:'Syne',sans-serif;font-weight:700;font-size:12px;color:#f0f0f8">{emoji} {row.verdict}</span>
                  <span style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:500;color:#f0f0f8">{int(row.bets)}</span>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-family:'JetBrains Mono',monospace;font-size:10px">
                  <div style="color:#9ca3af">Strike<br><span style="font-size:14px;color:#60a5fa">{row.strike}%</span></div>
                  <div style="color:#9ca3af">P&L<br><span style="font-size:14px;color:{pnl_c}">{'+' if (row.pnl or 0)>=0 else ''}{row.pnl}u</span></div>
                </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Row 3: Venues + Daily results ─────────────────────────────────────────
    st.markdown('<div class="rm-section">🏟️ Venues & Daily Log</div>', unsafe_allow_html=True)
    col5, col6 = st.columns([2, 3])

    with col5:
        if not venue_data.empty:
            fig3 = go.Figure()
            venue_colors = ["#10b981" if v>=0 else "#ef4444" for v in venue_data["pnl"]]
            fig3.add_trace(go.Bar(
                y=venue_data["venue"], x=venue_data["pnl"],
                orientation="h",
                marker_color=venue_colors,
                marker_line_width=0,
                text=[f"{'+' if v>=0 else ''}{v}u" for v in venue_data["pnl"]],
                textposition="outside",
                textfont=dict(family="JetBrains Mono", size=10, color="#9ca3af"),
                customdata=venue_data[["bets","strike"]].values,
                hovertemplate="<b>%{y}</b><br>P&L: %{x:+.2f}u<br>Bets: %{customdata[0]}<br>Strike: %{customdata[1]}%<extra></extra>"
            ))
            fig3.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font=dict(color="#9ca3af", family="JetBrains Mono", size=10),
                margin=dict(l=0,r=60,t=0,b=0), height=280,
                xaxis=dict(gridcolor="#1f2937", zeroline=True, zerolinecolor="#374151"),
                yaxis=dict(gridcolor="#1f2937", showgrid=False),
                hoverlabel=dict(bgcolor="#1f2937", bordercolor="#374151", font_color="#f0f0f8")
            )
            st.plotly_chart(fig3, use_container_width=True)

    with col6:
        if not daily.empty:
            # Interactive daily table with color coding
            fig4 = go.Figure(data=[go.Table(
                columnwidth=[120, 60, 80, 80],
                header=dict(
                    values=["<b>Date</b>", "<b>Bets</b>", "<b>Strike</b>", "<b>P&L</b>"],
                    fill_color="#161b22",
                    font=dict(color="#9ca3af", family="JetBrains Mono", size=11),
                    line_color="#30363d",
                    align="left",
                    height=32
                ),
                cells=dict(
                    values=[
                        daily["date"].astype(str).tolist(),
                        daily["bets"].tolist(),
                        [f"{v}%" for v in daily["strike"].tolist()],
                        [f"{'+' if v>=0 else ''}{v}u" for v in daily["pnl"].tolist()]
                    ],
                    fill_color=[
                        ["#0d1117"] * len(daily),
                        ["#0d1117"] * len(daily),
                        ["rgba(16,185,129,0.1)" if v>=50 else "rgba(239,68,68,0.1)" for v in daily["strike"].tolist()],
                        ["rgba(16,185,129,0.1)" if v>=0 else "rgba(239,68,68,0.1)" for v in daily["pnl"].tolist()]
                    ],
                    font=dict(
                        color=[
                            ["#d1d5db"] * len(daily),
                            ["#d1d5db"] * len(daily),
                            ["#10b981" if v>=50 else "#ef4444" for v in daily["strike"].tolist()],
                            ["#10b981" if v>=0 else "#ef4444" for v in daily["pnl"].tolist()]
                        ],
                        family="JetBrains Mono", size=11
                    ),
                    line_color="#1f2937",
                    align="left",
                    height=28
                )
            )])
            fig4.update_layout(
                paper_bgcolor="#0d1117",
                margin=dict(l=0,r=0,t=0,b=0),
                height=280
            )
            st.plotly_chart(fig4, use_container_width=True)


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
               brain_check as verdict,
               CASE 
                   WHEN result_loaded = FALSE THEN '⏳ Pending'
                   WHEN win_result = 1 THEN '🏆 WON'
                   WHEN place_result = 1 THEN '✅ Placed'
                   ELSE '❌ Unplaced'
               END as outcome,
               finish_position as pos,
               ROUND(place_bsp,2) as place_bsp,
               ROUND(profit_loss,2) as pnl,
               ROUND(clv,1) as clv,
               brain_check_reason as reason,
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

        # Additional column filters
        st.markdown("**Additional Filters**")
        fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)

        with fcol1:
            outcome_filter = st.multiselect("Outcome", 
                ["🏆 WON","✅ Placed","❌ Unplaced","⏳ Pending"],
                default=["🏆 WON","✅ Placed","❌ Unplaced","⏳ Pending"],
                key="outcome_f")
            if outcome_filter:
                df = df[df['outcome'].isin(outcome_filter)]

        with fcol2:
            if 'course' in df.columns:
                venues = sorted(df['course'].dropna().unique().tolist())
                venue_sel = st.multiselect("Venue", venues, default=venues, key="venue_f")
                if venue_sel:
                    df = df[df['course'].isin(venue_sel)]

        with fcol3:
            if 'going' in df.columns:
                goings = sorted(df['going'].dropna().unique().tolist())
                going_sel = st.multiselect("Going", goings, default=goings, key="going_f")
                if going_sel:
                    df = df[df['going'].isin(going_sel)]

        with fcol4:
            min_score = st.number_input("Min Score", min_value=0, max_value=25, value=0, key="score_f")
            if min_score > 0:
                df = df[df['score'] >= min_score]

        with fcol5:
            horse_search = st.text_input("Horse name", placeholder="Search...", key="horse_f")
            if horse_search:
                df = df[df['horse'].str.lower().str.contains(horse_search.lower(), na=False)]

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
            col4.metric("Place Rate", f"{float(bsp_stats['place_pct'][0] or 0)}%")
            col5.metric("Avg Win BSP", f"${float(bsp_stats['avg_win_bsp'][0] or 0)}")
            col6.metric("Best BSP", f"${float(bsp_stats['best_bsp'][0] or 0)}")
            col7.metric("Worst BSP", f"${float(bsp_stats['worst_bsp'][0] or 0)}")
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
        st.markdown("### 📈 BSP Over Time (Win & Place)")
        if not bsp.empty and len(bsp) > 1:
            fig = go.Figure()
            date_col = "LOCAL_MEETING_DATE" if "LOCAL_MEETING_DATE" in bsp.columns else "date"
            win_col = "WIN_BSP" if "WIN_BSP" in bsp.columns else "win_bsp"
            place_col = "PLACE_BSP" if "PLACE_BSP" in bsp.columns else "place_bsp"
            result_col = "WIN_RESULT" if "WIN_RESULT" in bsp.columns else "result"
            colors = ["#34d399" if r=="WINNER" else "#f87171" for r in bsp[result_col]]
            fig.add_trace(go.Scatter(
                x=bsp[date_col], y=bsp[win_col],
                mode="lines+markers",
                line=dict(color="#60a5fa", width=2),
                marker=dict(size=10, color=colors,
                    line=dict(color="#ffffff", width=1)),
                hovertemplate="<b>%{x}</b><br>Win BSP: $%{y}<extra></extra>",
                name="Win BSP"
            ))
            # Add place BSP line if available
            if place_col in bsp.columns and bsp[place_col].notna().any():
                fig.add_trace(go.Scatter(
                    x=bsp[date_col], y=bsp[place_col],
                    mode="lines+markers",
                    line=dict(color="#fbbf24", width=2),
                    marker=dict(size=6, color="#fbbf24", symbol="diamond"),
                    name="Place BSP",
                    hovertemplate="Place BSP: $%{y}<extra></extra>"
                ))
            fig.update_layout(
                paper_bgcolor="#16161e", plot_bgcolor="#16161e",
                showlegend=True,
                legend=dict(bgcolor="#16161e", font=dict(color="#9898b0", size=11)),
                font=dict(color="#9898b0"), height=250,
                margin=dict(l=0,r=0,t=10,b=0),
                xaxis=dict(gridcolor="#2a2a38"),
                yaxis=dict(gridcolor="#2a2a38", title="BSP ($)"),
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
            # Steam summary — use actual column name from SELECT *
            steam_col = "steam_pct_10to_bsp" if "steam_pct_10to_bsp" in stream.columns else "steam_10"
            if steam_col in stream.columns:
                steamers = stream[stream[steam_col].notna() & (stream[steam_col] > 15)]
                drifters = stream[stream[steam_col].notna() & (stream[steam_col] < -15)]
            else:
                steamers = drifters = stream.iloc[0:0]
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
