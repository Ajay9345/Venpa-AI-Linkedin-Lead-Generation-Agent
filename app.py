from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from services import analytics, apify_service, exporter
from services.helpers import EXPECTED_COLUMNS, COMPANY_COLUMNS, clean_dataframe, normalize_record, normalize_company_record
from services.lead_score import apply_lead_scores, score_badge_color
from services.groq_filter import apply_groq_filter
from services.google_apify_service import GoogleApifyService
from services.google_formatter import format_google_results

load_dotenv()

st.set_page_config(
    page_title="Venpa AI Copilot — LinkedIn Lead Generation",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

for k, v in {
    "leads_df": pd.DataFrame(columns=EXPECTED_COLUMNS),
    "is_loading": False,
    "dark_mode": True,
    "last_query": "",
    "error_message": None,
    "search_count": 0,
    "active_view": "🔷 LinkedIn Leads",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def inject_css(dark: bool) -> None:
    if dark:
        bg, card_bg, text, subtext, border = "#0A0D16", "#131826", "#ECEFF7", "#8891A6", "#212838"
    else:
        bg, card_bg, text, subtext, border = "#F6F8FC", "#FFFFFF", "#10131C", "#656D80", "#E6E9F2"

    accent_from, accent_mid, accent_to = "#1E40FF", "#0EA5C4", "#00D9A6"
    accent_solid = "#2A52FF"
    amber = "#FFB020"

    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

        :root, .stApp {{
            --text-color: {text};
            --background-color: {bg};
            --secondary-background-color: {card_bg};
        }}
        [data-testid="stSidebar"] {{
            --text-color: {text};
            --background-color: {card_bg};
            --secondary-background-color: {bg};
        }}
        .stApp {{ background-color: {bg}; color: {text}; }}

        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3,
        [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
        [data-testid="stCaptionContainer"], [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"], .stTextInput label, .stTextArea label,
        .stSelectbox label, .stSlider label, .stExpander summary, .stExpander p,
        section[data-testid="stSidebar"] * {{
            color: {text};
        }}
        [data-testid="stCaptionContainer"] {{ color: {subtext} !important; }}

        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {card_bg} !important;
            color: {text} !important;
            border-color: {border} !important;
        }}

        div.stButton > button {{ color: {text}; background-color: {card_bg}; border: 1px solid {border} !important; }}
        div.stButton > button[kind="primary"] {{ color: white !important; }}

        .brand-mark {{
            display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
        }}
        .brand-mark .hex {{
            width: 22px; height: 22px; flex-shrink: 0;
            background: linear-gradient(135deg, {accent_from}, {accent_mid} 55%, {accent_to});
            clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
        }}
        .brand-mark span {{
            font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 0.95rem;
            letter-spacing: 0.12em; color: {subtext}; text-transform: uppercase;
        }}

        .app-header {{
            position: relative; overflow: hidden;
            background: linear-gradient(120deg, {accent_from} 0%, {accent_mid} 55%, {accent_to} 100%);
            border-radius: 20px; padding: 34px 40px; margin-bottom: 28px;
            box-shadow: 0 10px 30px rgba(30, 64, 255, 0.22);
        }}
        .app-header .eyebrow {{
            font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 0.72rem;
            letter-spacing: 0.16em; text-transform: uppercase; color: rgba(255,255,255,0.85); margin: 0 0 6px 0;
        }}
        .app-header h1 {{
            font-family: 'Space Grotesk', sans-serif; color: white; font-size: 2rem; font-weight: 700; margin: 0;
        }}
        .app-header p {{ color: rgba(255,255,255,0.92); font-size: 1rem; margin-top: 6px; }}

        .metric-card {{
            background: {card_bg}; border: 1px solid {border}; border-radius: 16px;
            padding: 18px 20px; transition: transform 0.15s ease, box-shadow 0.15s ease;
            border-top: 2px solid transparent;
        }}
        .metric-card:hover {{
            transform: translateY(-3px); box-shadow: 0 8px 20px rgba(30, 64, 255, 0.14);
            border-top: 2px solid {accent_mid};
        }}
        .metric-card .label {{ color: {subtext}; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
        .metric-card .value {{ font-family: 'Space Grotesk', sans-serif; color: {text}; font-size: 1.7rem; font-weight: 700; margin-top: 4px; }}

        .lead-card {{
            background: {card_bg}; border: 1px solid {border}; border-radius: 16px;
            padding: 16px 18px; margin-bottom: 12px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .lead-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.10); }}

        .badge {{ display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; color: white; }}
        .badge-green {{ background-color: #00C9A6; }}
        .badge-orange {{ background-color: {amber}; }}
        .badge-red {{ background-color: #EF4444; }}

        .welcome-box {{ text-align: center; padding: 80px 20px; color: {subtext}; }}
        .welcome-box .hex-lg {{
            width: 56px; height: 56px; margin: 0 auto 18px auto;
            background: linear-gradient(135deg, {accent_from}, {accent_mid} 55%, {accent_to});
            clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
        }}
        .welcome-box h2 {{ font-family: 'Space Grotesk', sans-serif; color: {text}; font-weight: 700; margin-bottom: 10px; }}

        section[data-testid="stSidebar"] {{ background-color: {card_bg}; border-right: 1px solid {border}; }}

        div.stButton > button {{ border-radius: 10px; font-weight: 600; border: none; transition: transform 0.1s ease; }}
        div.stButton > button:hover {{ transform: translateY(-1px); }}
        div.stButton > button[kind="primary"] {{
            background: linear-gradient(120deg, {accent_from}, {accent_mid} 55%, {accent_to});
            color: white;
        }}

        .footer-mark {{
            text-align: center; padding: 18px 0 6px 0; color: {subtext};
            font-size: 0.78rem; letter-spacing: 0.03em;
        }}
        .footer-mark b {{ color: {text}; }}
        </style>
    """, unsafe_allow_html=True)


inject_css(st.session_state.dark_mode)

header_left, header_right = st.columns([6, 1])
with header_left:
    st.markdown("""
        <div class="app-header">
            <div class="eyebrow">Venpa AI &middot; Autonomous Agents</div>
            <h1>🔷 Venpa AI Copilot</h1>
            <p>Autonomous LinkedIn lead generation — sourced, scored, and ready to work.</p>
        </div>
    """, unsafe_allow_html=True)
with header_right:
    st.write("")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("🔄", help="Refresh", use_container_width=True):
            st.rerun()
    with btn_col2:
        theme_icon = "☀️" if st.session_state.dark_mode else "🌙"
        if st.button(theme_icon, help="Toggle theme", use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

generate_clicked = clear_clicked = False
g_generate = g_clear = False
search_query, f_location, lead_type, max_results = "", "", "People", 25
f_industry = f_keyword = f_headcount = ""
f_current_title = f_past_title = f_current_co = f_past_co = ""
f_school = f_first_name = f_last_name = f_company_hq = ""
f_years_exp = f_years_co = f_seniority = f_function = f_language = ""
g_query, g_location, g_max = "", "", 20

with st.sidebar:
    st.markdown('<div class="brand-mark"><div class="hex"></div><span>Venpa AI</span></div>', unsafe_allow_html=True)

    if st.session_state.active_view == "🔷 LinkedIn Leads":
        st.markdown("### 🔍 Search Query")
        search_query = st.text_area(
            "Search Query", placeholder="Example:\nReal Estate",
            label_visibility="collapsed", height=80, disabled=st.session_state.is_loading,
        )
        st.markdown("### 📍 Location")
        f_location = st.text_input("Location", placeholder="e.g. Chennai", label_visibility="collapsed", disabled=st.session_state.is_loading)
        st.markdown("### 👥 Lead Type")
        lead_type = st.selectbox("Lead Type", ["People", "Company"], label_visibility="collapsed", disabled=st.session_state.is_loading)
        st.markdown("### 📊 Maximum Results")
        max_results = st.slider("Maximum Results", 10, 100, 25, 10, label_visibility="collapsed", disabled=st.session_state.is_loading)

        dis = st.session_state.is_loading
        with st.expander("⚙️ Filters (optional)", expanded=False):
            f_industry  = st.text_input("Industry", placeholder="e.g. Information Technology", disabled=dis)
            f_keyword   = st.text_input("Keyword", disabled=dis)
            f_headcount = st.selectbox("Company Headcount", ["","1-10","11-50","51-200","201-500","501-1000","1001-5000","5001-10000","10001+"], disabled=dis)
            if lead_type == "People":
                f_current_title = st.text_input("Current Job Title", placeholder="e.g. Software Engineer", disabled=dis)
                f_past_title    = st.text_input("Past Job Title", disabled=dis)
                f_current_co    = st.text_input("Current Company", disabled=dis)
                f_past_co       = st.text_input("Past Company", disabled=dis)
                f_school        = st.text_input("School", disabled=dis)
                f_first_name    = st.text_input("First Name", disabled=dis)
                f_last_name     = st.text_input("Last Name", disabled=dis)
                f_company_hq    = st.text_input("Company HQ Location", disabled=dis)
                f_years_exp     = st.selectbox("Years of Experience", ["", "1","2","3","4","5","6","7","8","9","10"], disabled=dis)
                f_years_co      = st.selectbox("Years at Current Company", ["", "1","2","3","4","5"], disabled=dis)
                f_seniority     = st.selectbox("Seniority Level", ["","Internship","Entry level","Associate","Mid-Senior level","Director","Executive"], disabled=dis)
                f_function      = st.text_input("Function", disabled=dis)
                f_language      = st.text_input("Profile Language", placeholder="e.g. en", disabled=dis)
            else:
                f_current_title = f_past_title = f_current_co = f_past_co = ""
                f_school = f_first_name = f_last_name = f_company_hq = ""
                f_years_exp = f_years_co = f_seniority = f_function = f_language = ""

        st.markdown("---")
        generate_clicked = st.button("🚀 Generate Leads", type="primary", use_container_width=True, disabled=dis)
        clear_clicked    = st.button("🗑️ Clear Results", use_container_width=True, disabled=dis)

        st.markdown("### 📤 Export")
        export_disabled = st.session_state.leads_df.empty or dis
        exp_col1, exp_col2, exp_col3 = st.columns(3)

        def _export_btn(col, label, data_fn, filename, mime):
            with col:
                if not export_disabled:
                    st.download_button(label, data=data_fn(st.session_state.leads_df),
                                       file_name=filename, mime=mime, use_container_width=True)
                else:
                    st.button(label, disabled=True, use_container_width=True)

        _export_btn(exp_col1, "CSV",   exporter.to_csv_bytes,   "linkedin_leads.csv",  "text/csv")
        _export_btn(exp_col2, "Excel", exporter.to_excel_bytes, "linkedin_leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        _export_btn(exp_col3, "JSON",  exporter.to_json_bytes,  "linkedin_leads.json", "application/json")

    else:
        dis = st.session_state.is_loading
        st.markdown("### 🔍 Search Query")
        g_query = st.text_input("Search Query", placeholder="Software Companies", key="g_query", label_visibility="collapsed", disabled=dis)
        st.markdown("### 📍 Location")
        g_location = st.text_input("Location", placeholder="Chennai", key="g_location", label_visibility="collapsed", disabled=dis)
        st.markdown("### 📊 Maximum Results")
        g_max = st.slider("Maximum Results", 1, 500, 20, 10, key="g_max", label_visibility="collapsed", disabled=dis)
        st.markdown("---")
        g_generate = st.button("🚀 Generate Leads", type="primary", use_container_width=True, key="g_generate", disabled=dis)
        g_clear = st.button("🗑️ Clear Results", use_container_width=True, key="g_clear", disabled=dis)

        st.markdown("### 📤 Export")
        g_export_disabled = "google_df" not in st.session_state or st.session_state["google_df"].empty
        ge1, ge2 = st.columns(2)
        if not g_export_disabled:
            ge1.download_button("CSV", st.session_state["google_df"].to_csv(index=False).encode("utf-8-sig"),
                                "google_leads.csv", "text/csv", use_container_width=True)
            ge2.download_button("Excel", exporter.to_excel_bytes(st.session_state["google_df"]),
                                "google_leads.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            ge1.button("CSV", disabled=True, use_container_width=True)
            ge2.button("Excel", disabled=True, use_container_width=True)

    st.markdown('<div class="footer-mark">Powered by <b>Venpa AI</b></div>', unsafe_allow_html=True)

if clear_clicked:
    st.session_state.leads_df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    st.session_state.error_message = None
    st.rerun()

_ERROR_MAP = {
    apify_service.MissingTokenError:   "Missing API Token",
    apify_service.InvalidTokenError:   "Invalid API Token",
    apify_service.ActorNotFoundError:  "Actor Not Found",
    apify_service.RateLimitError:      "Rate Limit Reached",
    apify_service.ApifyTimeoutError:   "Request Timed Out",
    apify_service.NoLeadsFoundError:   "No Leads Found",
    apify_service.ActorRunFailedError: "Actor Run Failed",
    apify_service.ApifyServiceError:   "Something Went Wrong",
}


def run_generation_workflow(query: str, lead_type_: str, max_results_: int, filters: dict, location_filter: str = "") -> Optional[pd.DataFrame]:
    bar = st.progress(0, text="Initializing Actor...")
    steps = [
        (10, "Initializing Actor..."),
        (25, "Searching LinkedIn..."),
        (45, "Collecting Results..."),
        (65, "Downloading Dataset..."),
        (80, "Cleaning Data..."),
        (90, "Calculating Lead Scores..."),
        (97, "Preparing Dashboard..."),
    ]
    is_company = lead_type_ == "Company"
    cols = COMPANY_COLUMNS if is_company else EXPECTED_COLUMNS
    normalizer = normalize_company_record if is_company else normalize_record
    try:
        bar.progress(*steps[0])
        bar.progress(*steps[1]); time.sleep(0.2)
        bar.progress(*steps[2])
        raw_items = apify_service.run_linkedin_search(query=query.strip(), max_results=max_results_, lead_type=lead_type_, filters=filters)
        bar.progress(*steps[3])
        df = pd.DataFrame([normalizer(i) for i in raw_items])
        for col in cols:
            if col not in df.columns and col != "Lead Score":
                df[col] = "N/A"
        df["Search Query"] = query.strip()
        bar.progress(*steps[4])
        if is_company:
            df = df[df["Company Name"].notna() & (df["Company Name"] != "N/A")].drop_duplicates(subset=["LinkedIn URL"], keep="first").reset_index(drop=True)
        else:
            df = clean_dataframe(df)
        bar.progress(*steps[5])
        if location_filter or query:
            bar.progress(88, text="Filtering by relevance (Groq AI)...")
            df = apply_groq_filter(df, query, location_filter)
        df = apply_lead_scores(df)
        bar.progress(*steps[6]); time.sleep(0.2)
        bar.progress(100, text="Done"); time.sleep(0.3)
        bar.empty()
        return df
    except Exception as exc:
        bar.empty()
        title = next((t for cls, t in _ERROR_MAP.items() if isinstance(exc, cls)), "Unexpected Error")
        st.session_state.error_message = (title, str(exc))
        return None


if generate_clicked:
    if not search_query or not search_query.strip():
        st.session_state.error_message = ("Empty Search Query", "Please enter a search query before generating leads.")
    else:
        st.session_state.is_loading = True
        st.session_state.error_message = None
        filters = {
            "location": f_location, "current_job_title": f_current_title,
            "past_job_title": f_past_title, "current_company": f_current_co,
            "past_company": f_past_co, "school": f_school,
            "industry": f_industry, "keyword": f_keyword,
            "first_name": f_first_name, "last_name": f_last_name,
            "company_hq_location": f_company_hq, "years_of_experience": f_years_exp,
            "years_at_current_company": f_years_co, "seniority": f_seniority,
            "function": f_function, "company_headcount": f_headcount,
            "profile_language": f_language,
        }
        with st.spinner("Venpa AI is working on it..."):
            result_df = run_generation_workflow(search_query, lead_type, max_results, filters, location_filter=f_location)
        st.session_state.is_loading = False
        if result_df is not None:
            st.session_state.leads_df = result_df
            st.session_state.last_query = search_query
            st.session_state.search_count += 1
        st.rerun()

if st.session_state.error_message:
    title, detail = st.session_state.error_message
    st.error(f"**{title}** — {detail}")

st.radio(
    "View", ["🔷 LinkedIn Leads", "📍 Google Leads"],
    horizontal=True, label_visibility="collapsed", key="active_view",
)

if st.session_state.active_view == "📍 Google Leads":
    if g_clear:
        st.session_state.pop("google_df", None)
        st.rerun()

    if g_generate:
        if not g_query or not g_location:
            st.warning("Please enter both Query and Location.")
        else:
            try:
                with st.spinner("Searching Google Maps..."):
                    google_service = GoogleApifyService()
                    results = google_service.run(g_query, g_location, g_max)
                    st.session_state["google_df"] = format_google_results(results)
            except Exception as e:
                st.error(str(e))

    if "google_df" in st.session_state and not st.session_state["google_df"].empty:
        g_df = st.session_state["google_df"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Leads", len(g_df))
        m2.metric("Emails", g_df["Email"].replace("", pd.NA).count())
        m3.metric("Phones", g_df["Phone"].replace("", pd.NA).count())
        m4.metric("Websites", g_df["Website"].replace("", pd.NA).count())
        st.markdown("<br>", unsafe_allow_html=True)
        g_search = st.text_input("🔎 Search within results", key="g_search")
        display_g = g_df[
            g_df.astype(str).apply(lambda c: c.str.contains(g_search, case=False, na=False)).any(axis=1)
        ] if g_search else g_df
        st.dataframe(display_g, use_container_width=True, height=500, hide_index=True)
        st.caption(f"Showing {len(display_g)} of {len(g_df)} leads")
    else:
        st.markdown("""
            <div class="welcome-box">
                <div class="hex-lg"></div>
                <h2>Google Maps Lead Generator</h2>
                <p>Enter a search query and location, then click "Generate Leads" to find business leads from Google Maps.</p>
            </div>
        """, unsafe_allow_html=True)

else:

    df = st.session_state.leads_df

    if df.empty:
        st.markdown("""
            <div class="welcome-box">
                <div class="hex-lg"></div>
                <h2>Welcome to Venpa AI Copilot</h2>
                <p>Enter a search query and click "Generate Leads" to let Venpa AI discover and score high-quality LinkedIn leads for you.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        metrics = analytics.compute_metrics(df)
        metric_defs = [
            ("Total Leads", metrics["total_leads"]),
            ("Companies Found", metrics["companies_found"]),
            ("Cities", metrics["cities"]),
            ("Decision Makers", metrics["decision_makers"]),
            ("Average Score", metrics["avg_score"]),
            ("Highest Score", metrics["highest_score"]),
            ("Lowest Score", metrics["lowest_score"]),
        ]
        metric_cols = st.columns(4)
        for i, (label, value) in enumerate(metric_defs):
            with metric_cols[i % 4]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="label">{label}</div>
                        <div class="value">{value}</div>
                    </div>
                """, unsafe_allow_html=True)
            if i % 4 == 3 and i != len(metric_defs) - 1:
                metric_cols = st.columns(4)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("## 📋 Results")

        filt_col1, filt_col2, filt_col3 = st.columns(3)
        with filt_col1:
            min_score = st.slider("Min Lead Score", 0, 100, 0)

        is_company_view = "Company Name" in df.columns

        with filt_col2:
            if is_company_view:
                industry_options = ["All"] + sorted(df["Industry"].replace("N/A", pd.NA).dropna().unique().tolist())
                company_filter = st.selectbox("Industry", industry_options)
            else:
                company_options = ["All"] + sorted(df["Company"].replace("N/A", pd.NA).dropna().unique().tolist())
                company_filter = st.selectbox("Company", company_options)
        with filt_col3:
            if is_company_view:
                size_options = ["All"] + sorted(df["Company Size"].replace("N/A", pd.NA).dropna().unique().tolist())
                designation_filter = st.selectbox("Company Size", size_options)
            else:
                desig_options = ["All"] + sorted(df["Designation"].replace("N/A", pd.NA).dropna().unique().tolist())
                designation_filter = st.selectbox("Designation", desig_options)

        search_box = st.text_input("🔎 Search within results", placeholder="Search by name, company, headline...")

        filtered_df = df[df["Lead Score"] >= min_score]
        if company_filter != "All":
            col3_field = "Industry" if is_company_view else "Company"
            filtered_df = filtered_df[filtered_df[col3_field] == company_filter]
        if designation_filter != "All":
            col4_field = "Company Size" if is_company_view else "Designation"
            filtered_df = filtered_df[filtered_df[col4_field] == designation_filter]
        if search_box:
            needle = search_box.lower()
            if is_company_view:
                mask = (
                    filtered_df["Company Name"].str.lower().str.contains(needle, na=False)
                    | filtered_df["Industry"].str.lower().str.contains(needle, na=False)
                    | filtered_df["Description"].str.lower().str.contains(needle, na=False)
                )
            else:
                mask = (
                    filtered_df["Full Name"].str.lower().str.contains(needle, na=False)
                    | filtered_df["Company"].str.lower().str.contains(needle, na=False)
                    | filtered_df["Headline"].str.lower().str.contains(needle, na=False)
                )
            filtered_df = filtered_df[mask]

        display_df = filtered_df.copy()
        display_df["Lead Score"] = display_df["Lead Score"].apply(lambda s: f"{s} ({score_badge_color(s).upper()})")

        if is_company_view:
            table_cols = ["Company Name", "Industry", "Location", "Company Size", "Followers", "Lead Score", "LinkedIn URL", "Website"]
            col_config = {
                "LinkedIn URL": st.column_config.LinkColumn("LinkedIn URL"),
                "Website": st.column_config.LinkColumn("Website"),
            }
        else:
            table_cols = ["Full Name", "Headline", "Designation", "Company", "Location", "Lead Score", "LinkedIn URL", "Company URL"]
            col_config = {
                "LinkedIn URL": st.column_config.LinkColumn("LinkedIn URL"),
                "Company URL": st.column_config.LinkColumn("Company URL"),
            }

        st.dataframe(
            display_df[[c for c in table_cols if c in display_df.columns]],
            use_container_width=True, hide_index=True,
            column_config=col_config,
            height=420,
        )
        st.caption(f"Showing {len(filtered_df)} of {len(df)} leads")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("## 📈 Analytics")

        chart_row1_col1, chart_row1_col2 = st.columns(2)
        with chart_row1_col1:
            st.pyplot(analytics.chart_leads_by_city(df))
        with chart_row1_col2:
            if is_company_view:
                st.pyplot(analytics.chart_designation_distribution(df.rename(columns={"Industry": "Designation"})))
            else:
                st.pyplot(analytics.chart_top_companies(df))

        chart_row2_col1, _ = st.columns(2)
        with chart_row2_col1:
            if not is_company_view:
                st.pyplot(analytics.chart_designation_distribution(df))

        chart_row3_col1, chart_row3_col2 = st.columns(2)
        with chart_row3_col1:
            st.pyplot(analytics.chart_lead_score_distribution(df))
        with chart_row3_col2:
            st.pyplot(analytics.chart_top_scoring_leads(df))
