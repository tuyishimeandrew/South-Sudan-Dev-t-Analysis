# streamlit_app_styled.py
"""
Streamlit dashboard for South Sudan donor allocations.

Updates:
- Bar chart now shows Budget against Main Sector (prefers 'Main Sector' or similar names).
- Each visual title includes the current filter selection (Donor and Project Status).
- Increased margins and label positioning to avoid clipping.
- Uses 'From Date' (preferred) for the line chart.
- Sidebar contains only filters (Donor and Project Status).
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import base64
from typing import Optional, List

st.set_page_config(page_title='Donor Allocations — South Sudan', layout='wide')

# --- CONFIG: set the raw GitHub URL here ---
DATA_PATH = "https://raw.githubusercontent.com/tuyishimeandrew/South-Sudan-Dev-t-Analysis/main/SS%20Raw%20Data.xlsx"
# For a local file, use something like:
# DATA_PATH = Path('static') / 'SS Raw Data.xlsx'

# --- Utility helpers ---
@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    """Load an Excel file from a local path or an http(s) RAW GitHub URL."""
    try:
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception as e:
        st.error(f"Failed to load data from {path}: {e}")
        return pd.DataFrame()
    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_first_matching_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Return the first column in df whose lowercased name matches any candidate (case-insensitive substring)."""
    if df is None or df.columns is None:
        return None
    cols_lower = {c.lower(): c for c in df.columns}
    # Exact match first
    for cand in candidates:
        if cand is None:
            continue
        cand_lower = cand.lower()
        if cand_lower in cols_lower:
            return cols_lower[cand_lower]
    # Substring match next
    for cand in candidates:
        if cand is None:
            continue
        for col in df.columns:
            if cand.lower() in str(col).lower():
                return col
    return None

def try_parse_date_series(s: pd.Series) -> pd.Series:
    """Attempt to parse a series into datetimes. Handles common formats including MM.YYYY."""
    # First try direct pd.to_datetime
    parsed = pd.to_datetime(s, errors='coerce', dayfirst=False)
    if parsed.notna().any():
        return parsed
    # Clean non-numeric characters except separators
    cleaned = s.astype(str).str.replace(r'[^0-9\-\/\.]', '', regex=True)
    # Try MM.YYYY (e.g., 01.2012)
    if cleaned.str.match(r'^\d{1,2}\.\d{4}$').any():
        parsed2 = pd.to_datetime(cleaned, format='%m.%Y', errors='coerce')
        if parsed2.notna().any():
            return parsed2
    # Try again with dayfirst
    parsed3 = pd.to_datetime(cleaned, errors='coerce', dayfirst=True)
    return parsed3

# --- Load data ---
df = load_data(DATA_PATH)

# Optional background (commented out by default)
def set_bg(image_file):
    try:
        with open(image_file, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode()
        page_bg = f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{{encoded}}");
            background-size: cover;
            background-attachment: fixed;
        }}
        .block-container {{
            background-color: rgba(255,255,255,0.86);
            border-radius: 12px;
            padding: 1.4rem;
        }}
        </style>
        """.replace("{{encoded}}", encoded)
        st.markdown(page_bg, unsafe_allow_html=True)
    except FileNotFoundError:
        pass

# set_bg("static/download.jpeg")  # optional background

# --- Sidebar: filters only ---
st.sidebar.header('Filters')

if df.empty:
    st.sidebar.warning("No data loaded. Check DATA_PATH and that the GitHub file is public.")
    st.warning("No data loaded. Check the DATA_PATH and that the GitHub file is public.")
else:
    # Detection candidates (keeps From Date preference)
    budget_candidates = ['Budget ($)', 'Budget', 'Total budget', 'Total Budget', 'Budget (USD)', 'Budget_USD', 'Amount']
    donor_candidates = ['Donor', 'Funding Agency', 'Funder']
    status_candidates = ['Project Status', 'Status']
    project_title_candidates = ['Project Title', 'Title', 'ProjectName']
    date_candidates = [
        'From Date', 'Date', 'Start Date', 'StartDate', 'Project Start Date',
        'Project Start', 'month.year', 'Month.Year', 'Month Year'
    ]
    # New: detect Main Sector column (prefer 'Main Sector')
    main_sector_candidates = ['Main Sector', 'Main sector', 'Sector', 'MainSector', 'Main_Sector']
    geo_candidates = ['Geographical focus', 'Geographical Focus', 'Geographic focus', 'Geographic Focus', 'Location', 'Region', 'Geography']

    budget_col = find_first_matching_column(df, budget_candidates)
    donor_col = find_first_matching_column(df, donor_candidates)
    status_col = find_first_matching_column(df, status_candidates)
    title_col = find_first_matching_column(df, project_title_candidates)
    # This will prefer "From Date" if present
    date_col = find_first_matching_column(df, date_candidates)
    # Detect main sector column
    main_sector_col = find_first_matching_column(df, main_sector_candidates)
    geo_col = find_first_matching_column(df, geo_candidates)

    # Filters: only Donor and Project Status
    donors = ['All']
    if donor_col:
        donors += sorted(df[donor_col].dropna().astype(str).unique().tolist())
    selected_donor = st.sidebar.selectbox('Donor', donors, index=0)

    statuses = ['All']
    if status_col:
        statuses += sorted(df[status_col].dropna().astype(str).unique().tolist())
    selected_status = st.sidebar.selectbox('Project Status', statuses, index=0)

    # helper used to include filter selections into titles
    def title_with_filters(base_title: str) -> str:
        donor_label = selected_donor if selected_donor != 'All' else 'All'
        status_label = selected_status if selected_status != 'All' else 'All'
        return f"{base_title} — Donor: {donor_label} | Status: {status_label}"

    # --- Filtering the dataframe according to sidebar ---
    mask = pd.Series(True, index=df.index)
    if selected_donor != 'All' and donor_col:
        mask &= df[donor_col].astype(str) == selected_donor
    if selected_status != 'All' and status_col:
        mask &= df[status_col].astype(str) == selected_status

    df_f = df[mask].copy()

    # --- Preprocess budget and date ---
    # Coerce budget to numeric (remove commas/currency symbols)
    if budget_col:
        df_f['__budget_numeric'] = pd.to_numeric(df_f[budget_col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce').fillna(0.0)
    else:
        df_f['__budget_numeric'] = 0.0

    # Parse date using chosen date column (prefer 'From Date' if detected)
    if date_col:
        df_f['__date_parsed'] = try_parse_date_series(df_f[date_col])
    else:
        df_f['__date_parsed'] = pd.NaT

    # --- KPIs ---
    st.title("South Sudan Donor Allocations Dashboard")
    col1, col2, col3 = st.columns([1,1,1])
    total_budget = df_f['__budget_numeric'].sum()
    projects = df_f[title_col].nunique() if title_col in df_f.columns else len(df_f)
    donor_count = df_f[donor_col].nunique() if donor_col in df_f.columns else None
    col1.metric('Total Budget ($)', f"{total_budget:,.0f}")
    col2.metric('Projects', projects)
    col3.metric('Donors', donor_count if donor_count is not None else 'N/A')

    # --- Charts container ---
    st.markdown('---')

    # 1) Funding by Main Sector (bar chart)
    st.markdown(f"### {title_with_filters('Funding by Main Sector')}")
    if main_sector_col and '__budget_numeric' in df_f.columns:
        by_sector = df_f.groupby(main_sector_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        fig = px.bar(
            by_sector,
            x=main_sector_col,
            y='__budget_numeric',
            text='__budget_numeric',
            labels={main_sector_col: 'Main Sector', '__budget_numeric': 'Budget ($)'}
        )
        # Value labels formatting and avoid clipping
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside', cliponaxis=False)
        fig.update_layout(
            title=dict(text=title_with_filters('Funding by Main Sector'), x=0.5),
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            xaxis_tickangle=-45,
            margin=dict(t=90, b=180, l=80, r=40),
            autosize=True
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Main Sector column or budget column not found — cannot draw 'Funding by Main Sector' bar chart. Detected main sector column: "
                + (main_sector_col if main_sector_col else "Not found"))

    # 2) Projects by Status (pie chart)
    st.markdown(f"### {title_with_filters('Projects by Status')}")
    if status_col:
        fig2 = px.pie(df_f, names=status_col, title=title_with_filters('Projects by Status'), hole=0.35)
        fig2.update_traces(textinfo='label+percent+value', textposition='inside', insidetextorientation='radial')
        fig2.update_layout(margin=dict(t=80, b=80, l=80, r=80), title=dict(text=title_with_filters('Projects by Status'), x=0.5), autosize=True)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Project status column not found — cannot draw 'Projects by Status' pie chart.")

    # 3) Geographical Focus — Budget share (pie chart)
    st.markdown(f"### {title_with_filters('Geographical Focus — Budget share')}")
    if geo_col and '__budget_numeric' in df_f.columns:
        geo_df = df_f.groupby(geo_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        fig3 = px.pie(geo_df, names=geo_col, values='__budget_numeric', title=title_with_filters('Geographical Focus — Budget share'), hole=0.35)
        fig3.update_traces(textinfo='label+percent+value', textposition='inside', insidetextorientation='radial')
        fig3.update_layout(margin=dict(t=80, b=80, l=80, r=80), title=dict(text=title_with_filters('Geographical Focus — Budget share'), x=0.5), autosize=True)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Geographical focus or budget column not found — cannot draw geographical-budget pie chart.")

    # 4) Date vs Budget (line chart using From Date if available)
    st.markdown(f"### {title_with_filters('Date vs Budget')}")
    if '__date_parsed' in df_f.columns and not df_f['__date_parsed'].isna().all():
        temp = df_f.copy()
        temp = temp[temp['__date_parsed'].notna()]
        if not temp.empty:
            # Aggregate by month for smoother trend
            temp['__period'] = temp['__date_parsed'].dt.to_period('M').dt.to_timestamp()
            time_df = temp.groupby('__period', as_index=False)['__budget_numeric'].sum().sort_values('__period')
            fig4 = px.line(time_df, x='__period', y='__budget_numeric', markers=True, labels={'__period': 'Date', '__budget_numeric': 'Budget ($)'})
            # show budget values at markers
            fig4.update_traces(mode='lines+markers+text', textposition='top center', text=time_df['__budget_numeric'].map(lambda v: f"{v:,.0f}"))
            fig4.update_layout(title=dict(text=title_with_filters('Date vs Budget (monthly aggregated)'), x=0.5), margin=dict(t=100, b=80, l=80, r=40), autosize=True)
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No valid date values found to build the Date vs Budget line chart.")
    else:
        st.info("Date column ('From Date' preferred) not found or not parseable — cannot draw Date vs Budget line chart.")

# End of file — note: no raw data table/export and no detected-columns/settings panel.
