"""
RACEMODEL — Daily Decision Dashboard (Streamlit)
=================================================
Mirrors the MotherDuck Daily Decision Dashboard dive.
Pulls from daily_candidates + steam_history.

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
import plotly.graph_objects as go
from datetime import date, datetime, timezone, timedelta
import math

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RACEMODEL — Daily Decision",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #f9fafb;
}
.block-container { padding: 0 !important; }
.stApp { background: #f9fafb; }

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

.rm-header {
    background: #0777b3;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 0;
}
.rm-logo {
    width: 36px; height: 36px;
    background: #fff;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 900; color: #0777b3;
    flex-shrink: 0;
}
.rm-title { font-size: 15px; font-weight: 800; color: #fff; }
.rm-sub   { font-size: 10px; color: #bae6fd; }
.rm-date  { font-size: 10px; color: #fde68a; margin-top: 2px; }

.kpi-bar {
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    padding: 8px 16px;
}
.kpi-card {
    background: #fff;
    border: 2px solid #111827;
    border-radius: 8px;
    padding: 8px 6px;
    text-align: center;
}
.kpi-icon  { font-size: 15px; }
.kpi-val   { font-size: 17px; font-weight: 800; color: #111827; line-height: 1.1; margin-top: 2px; }
.kpi-label { font-size: 8px; color: #6b7280; margin-top: 2px; font-weight: 700; letter-spacing: 0.06em; }
.kpi-sub   { font-size: 8px; color: #9ca3af; }

.section-card {
    background: #fff;
    border: 2px solid #111827;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 10px;
}
.section-hdr {
    font-size: 11px; font-weight: 700; color: #0777b3;
    margin-bottom: 8px; letter-spacing: 0.08em;
}

.bet-badge   { background:#15803d; color:#fff; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; }
.watch-badge { background:#d97706; color:#fff; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; }
.avoid-badge { background:#dc2626; color:#fff; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; }

.best-bet-card {
    background: #f0fdf4;
    border-radius: 6px;
    padding: 7px 10px;
    border-left: 3px solid #15803d;
    margin-bottom: 8px;
}
.rule-card {
    border-radius: 6px;
    padding: 7px 10px;
    margin-bottom: 6px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── Connection ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    token = os.environ.get("MOTHERDUCK_TOKEN", "")
    if not token:
        try:
            token = st.secrets["MOTHERDUCK_TOKEN"]
        except:
            pass
    if not token:
        st.error("⚠️ MOTHERDUCK_TOKEN not set.")
        st.stop()
    return duckdb.connect(f"md:my_db?motherduck_token={token}")

@st.cache_data(ttl=120)
def q(_conn, sql):
    try:
        return _conn.execute(sql).df()
    except Exception as e:
        st.warning(f"Query error: {e}")
        return pd.DataFrame()

conn = get_conn()

# ── Decision logic (mirrors dive) ──────────────────────────────────────────────
def get_decision(score, curr_odds, steam_pct, field_size):
    steam = steam_pct is not None and steam_pct >= 25
    drift = steam_pct is not None and steam_pct <= -25
    if drift or curr_odds > 8 or curr_odds < 3:
        return "AVOID"
    if score >= 6 and steam and curr_odds <= 8 and field_size < 13:
        return "BET"
    if score >= 6:
        return "WATCH"
    if score >= 5 and steam:
        return "WATCH"
    return "AVOID"

def get_reason(dec, score, steam_pct, curr_odds, field_size):
    if dec == "BET":
        return "Score ≥6 + steam ≥25% + odds $3–$8 + field <13"
    if dec == "AVOID" and steam_pct is not None and steam_pct <= -25:
        return f"Drift {steam_pct:.0f}% — market rejecting"
    if dec == "AVOID" and curr_odds > 8:
        return "Odds > $8 — outside range"
    if dec == "AVOID" and curr_odds < 3:
        return "Odds < $3 — too short"
    if dec == "WATCH" and score >= 6 and field_size >= 13:
        return f"Score ok but big field ({field_size})"
    if dec == "WATCH" and steam_pct is not None and steam_pct >= 10:
        return f"Moderate steam {steam_pct:.0f}% — monitor"
    if dec == "WATCH" and score >= 5:
        return "Near-miss — score 5–6 with steam"
    return "Watch — partial setup"

def get_move_label(pct):
    if pct is None: return "—",       "#9ca3af"
    if pct >= 25:   return "Steam",   "#15803d"
    if pct >= 10:   return "Easing",  "#4ade80"
    if pct >= -10:  return "Flat",    "#9ca3af"
    if pct >= -25:  return "Drifting","#f97316"
    return             "Drift",    "#dc2626"

def get_confidence(score, steam_pct, field_size):
    steam = steam_pct is not None and steam_pct >= 25
    if score >= 8 and steam and field_size < 13: return "High",   "#15803d"
    if score >= 7 and steam:                     return "Medium", "#d97706"
    if score >= 6:                               return "Low",    "#dc2626"
    return                                           "Skip",   "#6b7280"

# ── Date selector ──────────────────────────────────────────────────────────────
dates_df = q(conn, """
    SELECT DISTINCT race_date::VARCHAR as d
    FROM daily_candidates
    ORDER BY race_date DESC LIMIT 60
""")
dates = dates_df["d"].tolist() if not dates_df.empty else []

# ── Header ─────────────────────────────────────────────────────────────────────
col_logo, col_title, col_filters = st.columns([1, 4, 5])

with col_logo:
    st.markdown("""
    <div style='background:#0777b3;padding:12px 8px;border-radius:0'>
      <div style='width:36px;height:36px;background:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;color:#0777b3;margin:auto'>R</div>
    </div>""", unsafe_allow_html=True)

with col_title:
    st.markdown("""
    <div style='background:#0777b3;padding:12px 8px'>
      <div style='font-size:15px;font-weight:800;color:#fff'>RACEMODEL — DAILY DECISION DASHBOARD</div>
      <div style='font-size:10px;color:#bae6fd'>Actionable decisions — model, signals & price aligned.</div>
    </div>""", unsafe_allow_html=True)

with col_filters:
    st.markdown("<div style='background:#0777b3;padding:6px 8px'>", unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        sel_date = st.selectbox("Date", ["Latest"] + dates, label_visibility="collapsed")
    active_date = dates[0] if (sel_date == "Latest" or not dates) else sel_date
    date_sql = f"'{active_date}'" if active_date else "(NOW() AT TIME ZONE 'Australia/Brisbane')::DATE"
    with fc2:
        track_opt = st.selectbox("Track", ["All Tracks"], label_visibility="collapsed")
    with fc3:
        going_opt = st.selectbox("Going", ["All Going", "Good", "Soft", "Heavy", "Synth"], label_visibility="collapsed")
    with fc4:
        dec_filter = st.selectbox("Decision", ["All", "BET", "WATCH", "AVOID"], label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Build filters ──────────────────────────────────────────────────────────────
track_where = f"AND dc.course = '{track_opt}'" if track_opt != "All Tracks" else ""
going_where = f"AND dc.going = '{going_opt}'" if going_opt != "All Going" else ""

# ── Main query (mirrors dive) ──────────────────────────────────────────────────
data = q(conn, f"""
    WITH steam_cte AS (
        SELECT horse, course,
            MIN(morning_odds) as morning_odds,
            ROUND((MIN(morning_odds) - MIN(current_odds)) / NULLIF(MIN(morning_odds),0) * 100, 1) as steam_pct
        FROM steam_history
        WHERE race_date = {date_sql}
        GROUP BY horse, course
    )
    SELECT dc.horse, dc.course, dc.race_number, dc.score, dc.odds,
           COALESCE(dc.current_odds, dc.odds) as current_odds,
           dc.field_size, dc.going, dc.finish_position, dc.place_result,
           dc.s1_last_start as s1, dc.s2_form as s2, dc.s3_course_dist as s3,
           dc.s4_bsp_ratio as s4, dc.s5_draw as s5, dc.s14_going as s14,
           dc.s15_market as s15, dc.s18_place_rate as s18, dc.s19_dist_form as s19,
           dc.brain_check, dc.brain_check_reason,
           sh.morning_odds, sh.steam_pct
    FROM daily_candidates dc
    LEFT JOIN steam_cte sh
        ON LOWER(TRIM(dc.horse)) = LOWER(TRIM(sh.horse))
        AND LOWER(TRIM(dc.course)) = LOWER(TRIM(sh.course))
    WHERE dc.race_date = {date_sql}
    {track_where} {going_where}
    AND (
        (dc.score >= 6 AND COALESCE(dc.current_odds, dc.odds) BETWEEN 2.5 AND 10)
        OR (dc.score >= 5 AND sh.steam_pct >= 25 AND COALESCE(dc.current_odds, dc.odds) BETWEEN 3 AND 8)
        OR (dc.score >= 5.5 AND COALESCE(dc.current_odds, dc.odds) BETWEEN 3 AND 10)
    )
    ORDER BY dc.score DESC
""")

# ── Enrich data ────────────────────────────────────────────────────────────────
if not data.empty:
    data["steam_pct"]   = pd.to_numeric(data["steam_pct"], errors="coerce")
    data["score"]       = pd.to_numeric(data["score"], errors="coerce").fillna(0)
    data["current_odds"]= pd.to_numeric(data["current_odds"], errors="coerce").fillna(0)
    data["field_size"]  = pd.to_numeric(data["field_size"], errors="coerce").fillna(0)

    data["decision"]    = data.apply(lambda r: get_decision(r.score, r.current_odds, r.steam_pct if pd.notna(r.steam_pct) else None, r.field_size), axis=1)
    data["reason"]      = data.apply(lambda r: get_reason(r.decision, r.score, r.steam_pct if pd.notna(r.steam_pct) else None, r.current_odds, r.field_size), axis=1)
    data["move_label"]  = data["steam_pct"].apply(lambda x: get_move_label(x if pd.notna(x) else None)[0])
    data["move_color"]  = data["steam_pct"].apply(lambda x: get_move_label(x if pd.notna(x) else None)[1])
    data["conf_label"]  = data.apply(lambda r: get_confidence(r.score, r.steam_pct if pd.notna(r.steam_pct) else None, r.field_size)[0], axis=1)
    data["conf_color"]  = data.apply(lambda r: get_confidence(r.score, r.steam_pct if pd.notna(r.steam_pct) else None, r.field_size)[1], axis=1)

    # Top 3 positive signals
    sig_cols = {"s1":"S1","s2":"S2","s3":"S3","s4":"S4","s5":"S5","s14":"S14","s15":"S15","s18":"S18","s19":"S19"}
    def top_sigs(row):
        hits = [(lbl, row[col]) for col, lbl in sig_cols.items() if pd.notna(row.get(col)) and row.get(col, 0) > 0]
        hits.sort(key=lambda x: x[1], reverse=True)
        return ", ".join(h[0] for h in hits[:3]) or "—"
    data["top_sigs"] = data.apply(top_sigs, axis=1)

    # Apply decision filter
    if dec_filter != "All":
        view = data[data["decision"] == dec_filter]
    else:
        view = data
else:
    view = pd.DataFrame()

# ── KPI calculations ───────────────────────────────────────────────────────────
bet_count   = len(data[data["decision"] == "BET"])   if not data.empty else 0
watch_count = len(data[data["decision"] == "WATCH"]) if not data.empty else 0
avoid_count = len(data[data["decision"] == "AVOID"]) if not data.empty else 0
total_q     = len(data)

race_groups = data.groupby(["course","race_number"]) if not data.empty else {}
race_count  = data[["course","race_number"]].drop_duplicates().shape[0] if not data.empty else 0
no_bet_races= 0
if not data.empty:
    for (c,r), grp in data.groupby(["course","race_number"]):
        if not any(grp["decision"].isin(["BET","WATCH"])):
            no_bet_races += 1

avg_score = round(data["score"].mean(), 2) if not data.empty else 0
steam_vals = data["steam_pct"].dropna() if not data.empty else pd.Series()
avg_move  = round(steam_vals.mean(), 1) if len(steam_vals) > 0 else None
odds_vals = data["current_odds"][data["current_odds"] > 0] if not data.empty else pd.Series()
avg_odds  = round(odds_vals.mean(), 2) if len(odds_vals) > 0 else 0

gauge_angle = max(-90, min(90, (avg_move or 0) * 3))
gauge_color = "#9ca3af" if avg_move is None else "#15803d" if avg_move >= 20 else "#d97706" if avg_move >= 0 else "#dc2626"
gauge_label = "Neutral" if avg_move is None else "Strong Steam" if avg_move >= 20 else "Easing Up" if avg_move >= 10 else "Flat" if avg_move >= 0 else "Drifting" if avg_move >= -25 else "Strong Drift"

best_bet = data[data["decision"] == "BET"].sort_values("score", ascending=False).head(1) if not data.empty else pd.DataFrame()

# ── KPI Bar ────────────────────────────────────────────────────────────────────
st.markdown("<div style='padding: 8px 16px; background:#fff; border-bottom:1px solid #e5e7eb'>", unsafe_allow_html=True)
k1,k2,k3,k4,k5,k6,k7,k8,k9 = st.columns(9)

def kpi_card(icon, label, val, sub, color="#111827"):
    return f"""
    <div class='kpi-card'>
      <div class='kpi-icon'>{icon}</div>
      <div class='kpi-val' style='color:{color}'>{val}</div>
      <div class='kpi-label'>{label}</div>
      <div class='kpi-sub'>{sub}</div>
    </div>"""

move_str = f"{'+' if (avg_move or 0) >= 0 else ''}{avg_move:.1f}%" if avg_move is not None else "—"
move_col = "#15803d" if (avg_move or 0) >= 0 else "#dc2626"

k1.markdown(kpi_card("🏁","RACES",       race_count,         "Today"),          unsafe_allow_html=True)
k2.markdown(kpi_card("⭐","CANDIDATES",  total_q,            "Actionable",      "#d97706"), unsafe_allow_html=True)
k3.markdown(kpi_card("✅","BET",         bet_count,          "Clean pass",      "#15803d"), unsafe_allow_html=True)
k4.markdown(kpi_card("👁️","WATCH",       watch_count,        "Monitor",         "#d97706"), unsafe_allow_html=True)
k5.markdown(kpi_card("❌","AVOID",       avoid_count,        "Skip",            "#dc2626"), unsafe_allow_html=True)
k6.markdown(kpi_card("🚫","NO BET RACES",no_bet_races,       "Skip races",      "#6b7280"), unsafe_allow_html=True)
k7.markdown(kpi_card("📈","AVG SCORE",   avg_score,          "Qualifiers"),                  unsafe_allow_html=True)
k8.markdown(kpi_card("📊","AVG MOVE",    move_str,           "All runners",     move_col),  unsafe_allow_html=True)
k9.markdown(kpi_card("💰","AVG ODDS",    f"${avg_odds}",     "All runners",     "#d97706"), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ── Date display ───────────────────────────────────────────────────────────────
if active_date:
    st.markdown(f"<div style='padding:4px 16px;background:#0f172a;font-size:10px;color:#fde68a'>📅 {active_date}</div>", unsafe_allow_html=True)

# ── Main content ───────────────────────────────────────────────────────────────
st.markdown("<div style='padding:10px 16px'>", unsafe_allow_html=True)
left_col, right_col = st.columns([3, 1])

with left_col:

    # ── Race Confidence Overview ───────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-hdr'>RACE CONFIDENCE OVERVIEW</div>", unsafe_allow_html=True)

    if not data.empty:
        race_rows = []
        for (course, rnum), grp in data.groupby(["course","race_number"]):
            best = grp.sort_values("score", ascending=False).iloc[0]
            conf_lbl, conf_col = get_confidence(best.score, best.steam_pct if pd.notna(best.steam_pct) else None, best.field_size)
            race_rows.append({
                "R#":     f"R{rnum}",
                "Track":  course,
                "Fld":    int(best.field_size),
                "6+":     int((grp["score"] >= 6).sum()) or None,
                "⚡":     int((grp["steam_pct"] >= 25).sum()) if grp["steam_pct"].notna().any() else None,
                "📉":     int((grp["steam_pct"] <= -25).sum()) if grp["steam_pct"].notna().any() else None,
                "✅":     int((grp["decision"] == "BET").sum()) or None,
                "Conf":   conf_lbl,
                "_conf_col": conf_col,
            })

        race_df = pd.DataFrame(race_rows)

        def style_race_table(df):
            conf_map = {"High":"#15803d","Medium":"#d97706","Low":"#dc2626","Skip":"#6b7280"}
            styled = df.drop(columns=["_conf_col"]).style
            def color_conf(val):
                c = conf_map.get(val, "#6b7280")
                return f"color:{c};font-weight:700"
            def color_num(val):
                if pd.isna(val) or val == 0: return "color:#d1d5db"
                return "color:#15803d;font-weight:700"
            styled = styled.applymap(color_conf, subset=["Conf"])
            styled = styled.applymap(color_num, subset=["6+","⚡","📉","✅"])
            return styled

        display_df = race_df.drop(columns=["_conf_col"])
        display_df = display_df.fillna("—")
        st.dataframe(
            display_df.style.applymap(
                lambda v: "color:#15803d;font-weight:700" if v not in ["—", None] and str(v).replace(".","").isdigit() and float(str(v)) > 0 else "color:#9ca3af",
                subset=["6+","⚡","📉","✅"]
            ).applymap(
                lambda v: f"color:{'#15803d' if v=='High' else '#d97706' if v=='Medium' else '#dc2626' if v=='Low' else '#6b7280'};font-weight:700",
                subset=["Conf"]
            ),
            use_container_width=True,
            hide_index=True,
            height=min(400, 36 + len(race_df) * 35)
        )
    else:
        st.info("No race data for selected date")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Candidates Table ───────────────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)

    dec_cols = st.columns([4, 1, 1, 1, 1])
    with dec_cols[0]:
        st.markdown("<div class='section-hdr' style='margin-bottom:0'>TODAY'S CANDIDATES</div>", unsafe_allow_html=True)
    with dec_cols[1]:
        if st.button(f"All ({total_q})", key="f_all", type="secondary" if dec_filter != "All" else "primary"):
            st.query_params["dec"] = "All"
    with dec_cols[2]:
        if st.button(f"✅ BET ({bet_count})", key="f_bet"):
            st.query_params["dec"] = "BET"
    with dec_cols[3]:
        if st.button(f"👁 WATCH ({watch_count})", key="f_watch"):
            st.query_params["dec"] = "WATCH"
    with dec_cols[4]:
        if st.button(f"❌ AVOID ({avoid_count})", key="f_avoid"):
            st.query_params["dec"] = "AVOID"

    if not view.empty:
        dec_colors = {"BET":"#15803d","WATCH":"#d97706","AVOID":"#dc2626"}

        display_cols = {
            "horse":        "Horse",
            "race_number":  "R#",
            "course":       "Track",
            "score":        "Score",
            "current_odds": "Odds",
            "morning_odds": "Morn",
            "steam_pct":    "Move%",
            "move_label":   "Move",
            "field_size":   "Field",
            "top_sigs":     "Signals",
            "decision":     "Decision",
            "brain_check":  "Brain ✓",
            "reason":       "Reason",
            "finish_position": "Pos",
        }

        tbl = view[list(display_cols.keys())].copy()
        tbl.columns = list(display_cols.values())
        tbl["Score"]   = tbl["Score"].round(2)
        tbl["Odds"]    = tbl["Odds"].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "—")
        tbl["Morn"]    = tbl["Morn"].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else "—")
        tbl["Move%"]   = tbl["Move%"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
        tbl["Field"]   = tbl["Field"].apply(lambda x: int(x) if pd.notna(x) else "—")
        tbl["Pos"]     = tbl["Pos"].apply(lambda x: int(x) if pd.notna(x) else "—")
        tbl["Brain ✓"] = tbl["Brain ✓"].fillna("—")

        def style_table(df):
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            for i, row in df.iterrows():
                dec = row["Decision"]
                c = dec_colors.get(dec, "#6b7280")
                styles.at[i, "Decision"] = f"background:{c};color:#fff;font-weight:700;border-radius:4px;padding:2px 8px"
                bc = row.get("Brain ✓","—")
                if bc == "BET":
                    styles.at[i, "Brain ✓"] = "color:#15803d;font-weight:700"
                elif bc == "CAUTION":
                    styles.at[i, "Brain ✓"] = "color:#d97706;font-weight:700"
                elif bc == "SKIP":
                    styles.at[i, "Brain ✓"] = "color:#dc2626;font-weight:700"
            return styles

        st.dataframe(
            tbl.style.apply(style_table, axis=None),
            use_container_width=True,
            hide_index=True,
            height=min(600, 36 + len(tbl) * 35)
        )
        st.markdown(
            "<div style='font-size:9px;color:#9ca3af;margin-top:4px'>"
            "BET = Score≥6 + Odds $3–$8 + Steam≥25% + Field&lt;13 ▪ "
            "WATCH = score/steam partial ▪ AVOID = drift≥25% or odds outside range"
            "</div>",
            unsafe_allow_html=True
        )
    else:
        st.info("No candidates match current filters")
    st.markdown("</div>", unsafe_allow_html=True)


with right_col:

    # ── Decision Rules ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-hdr'>DECISION RULES</div>", unsafe_allow_html=True)
    for icon, color, title, desc in [
        ("✅","#15803d","BET",  "Score≥6 + Odds $3–$8 + Steam≥25% + Field<13"),
        ("👁️","#d97706","WATCH","Score≥6 partial, or score 5–6 + steam≥25%"),
        ("❌","#dc2626","AVOID","Drift≥25% or odds outside $3–$8"),
    ]:
        st.markdown(f"""
        <div style='background:{color}08;border-left:3px solid {color};border-radius:6px;
             padding:7px 10px;margin-bottom:6px;display:flex;gap:8px;align-items:flex-start'>
          <span style='font-size:14px;flex-shrink:0'>{icon}</span>
          <div>
            <div style='font-weight:700;color:{color};font-size:10px'>{title}</div>
            <div style='font-size:9px;color:#6b7280;margin-top:1px'>{desc}</div>
          </div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Market Momentum Gauge ──────────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-hdr'>MARKET MOMENTUM</div>", unsafe_allow_html=True)

    angle_rad = (gauge_angle - 90) * math.pi / 180
    needle_x2 = 90 + 52 * math.cos(angle_rad)
    needle_y2 = 90 + 52 * math.sin(angle_rad)

    gauge_svg = f"""
    <div style='text-align:center'>
    <svg width='180' height='110' viewBox='0 0 180 110'>
      <path d='M 20 90 A 70 70 0 0 1 160 90' fill='none' stroke='#f3f4f6' stroke-width='14' stroke-linecap='round'/>
      <path d='M 20 90 A 70 70 0 0 1 55 28'  fill='none' stroke='#fecaca' stroke-width='14' stroke-linecap='round'/>
      <path d='M 55 28 A 70 70 0 0 1 125 28' fill='none' stroke='#fef3c7' stroke-width='14' stroke-linecap='round'/>
      <path d='M 125 28 A 70 70 0 0 1 160 90' fill='none' stroke='#dcfce7' stroke-width='14' stroke-linecap='round'/>
      <line x1='90' y1='90' x2='{needle_x2:.1f}' y2='{needle_y2:.1f}' stroke='#111827' stroke-width='2.5' stroke-linecap='round'/>
      <circle cx='90' cy='90' r='4' fill='#111827'/>
      <text x='14' y='96' font-size='8' fill='#dc2626' font-weight='700'>Drift</text>
      <text x='145' y='96' font-size='8' fill='#15803d' font-weight='700'>Steam</text>
    </svg>
    <div style='font-size:22px;font-weight:800;color:{gauge_color};margin-top:-8px'>{move_str}</div>
    <div style='font-size:10px;color:{gauge_color};font-weight:600;margin-top:2px'>{gauge_label}</div>
    </div>"""
    st.markdown(gauge_svg, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Today's Summary ────────────────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-hdr'>TODAY'S SUMMARY</div>", unsafe_allow_html=True)

    if not best_bet.empty:
        bb = best_bet.iloc[0]
        st.markdown(f"""
        <div class='best-bet-card'>
          <div style='font-size:9px;color:#15803d;font-weight:700'>⭐ Best Bet</div>
          <div style='font-size:10px;font-weight:700;margin-top:2px'>{bb['horse']}</div>
          <div style='font-size:9px;color:#6b7280'>R{bb['race_number']} {bb['course']} · Score {bb['score']:.2f} · ${bb['current_odds']:.2f}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style='background:#f9fafb;border-radius:6px;padding:7px 10px;border-left:3px solid {gauge_color};margin-bottom:8px'>
      <div style='font-size:9px;color:{gauge_color};font-weight:700'>📊 Market</div>
      <div style='font-size:10px;font-weight:700;margin-top:1px'>{gauge_label} · {move_str}</div>
    </div>""", unsafe_allow_html=True)

    # Donut chart
    tot = max(bet_count + watch_count + avoid_count, 1)
    fig_donut = go.Figure(go.Pie(
        values=[bet_count, watch_count, avoid_count],
        labels=["BET","WATCH","AVOID"],
        hole=0.6,
        marker_colors=["#15803d","#d97706","#dc2626"],
        textinfo="none",
        hovertemplate="%{label}: %{value}<extra></extra>"
    ))
    fig_donut.update_layout(
        showlegend=False,
        margin=dict(l=0,r=0,t=0,b=0),
        height=120,
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=f"<b>{tot}</b>",
            x=0.5, y=0.5, font_size=18, showarrow=False, font_color="#111827"
        )]
    )
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar":False})

    for color, label, n in [("#15803d","BET",bet_count),("#d97706","WATCH",watch_count),("#dc2626","AVOID",avoid_count)]:
        pct = round(n/tot*100) if tot > 0 else 0
        st.markdown(f"""
        <div style='display:flex;align-items:center;gap:6px;font-size:9px;margin-bottom:3px'>
          <div style='width:8px;height:8px;border-radius:2px;background:{color};flex-shrink:0'></div>
          <span style='color:#6b7280'>{label} {n} ({pct}%)</span>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ── At a Glance ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-hdr'>AT A GLANCE</div>", unsafe_allow_html=True)
    gl1, gl2, gl3 = st.columns(3)
    glance = [
        ("✅","Bet",         bet_count,   "#15803d"),
        ("👁️","Watch",       watch_count, "#d97706"),
        ("❌","Avoid",       avoid_count, "#dc2626"),
        ("🚫","No Bet",     no_bet_races,"#6b7280"),
        ("⭐","Candidates", total_q,      "#d97706"),
        ("📈","Avg Score",  avg_score,    "#0777b3"),
    ]
    for i, (icon, label, val, color) in enumerate(glance):
        col = [gl1, gl2, gl3][i % 3]
        col.markdown(f"""
        <div style='background:#f9fafb;border-radius:6px;padding:6px 8px;text-align:center;
             border:1px solid #e5e7eb;margin-bottom:6px'>
          <div style='font-size:14px'>{icon}</div>
          <div style='font-size:15px;font-weight:800;color:{color};line-height:1.1'>{val}</div>
          <div style='font-size:8px;color:#9ca3af;margin-top:2px'>{label}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
