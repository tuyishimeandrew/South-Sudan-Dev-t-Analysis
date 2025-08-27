# streamlit_app_styled.py
"""
Streamlit dashboard for South Sudan donor allocations.

Key features:
- Uses "From Date" (preferred) for the Date vs Budget line chart.
- Line chart: Date vs Budget (monthly aggregation)
- Bar charts: show value labels
- Pie charts: show labels, values and percentages
- Pie chart: Geographical focus vs Budget
- Robust detection of budget/donor/date/geo columns, with an option to manually choose columns.
- DATA_PATH points to the raw GitHub Excel URL you provided.
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

# --- Sidebar: filters and detection ---
st.sidebar.header('Filters & settings')

if df.empty:
    st.warning("No data loaded. Check the DATA_PATH and that the GitHub file is public.")
else:
    # Prefer "From Date" explicitly for the date column
    budget_candidates = ['Budget ($)', 'Budget', 'Total budget', 'Total Budget', 'Budget (USD)', 'Budget_USD', 'Amount']
    donor_candidates = ['Donor', 'Funding Agency', 'Funder']
    status_candidates = ['Project Status', 'Status']
    project_title_candidates = ['Project Title', 'Title', 'ProjectName']
    # Put 'From Date' first so it gets picked if present
    date_candidates = [
        'From Date', 'Date', 'Start Date', 'StartDate', 'Project Start Date',
        'Project Start', 'month.year', 'Month.Year', 'Month Year'
    ]
    geo_candidates = ['Geographical focus', 'Geographical Focus', 'Geographic focus', 'Geographic Focus', 'Location', 'Region', 'Geography']

    budget_col = find_first_matching_column(df, budget_candidates)
    donor_col = find_first_matching_column(df, donor_candidates)
    status_col = find_first_matching_column(df, status_candidates)
    title_col = find_first_matching_column(df, project_title_candidates)
    # This will now prefer "From Date" if present
    date_col = find_first_matching_column(df, date_candidates)
    geo_col = find_first_matching_column(df, geo_candidates)

    st.sidebar.markdown("**Detected columns:**")
    st.sidebar.write({
        "Budget": budget_col or "Not found",
        "Donor": donor_col or "Not found",
        "Date (prefers 'From Date')": date_col or "Not found",
        "Geographical focus": geo_col or "Not found",
        "Project Status": status_col or "Not found",
    })

    # Basic filters
    donors = ['All']
    if donor_col:
        donors += sorted(df[donor_col].dropna().astype(str).unique().tolist())
    selected_donor = st.sidebar.selectbox('Donor', donors, index=0)

    statuses = ['All']
    if status_col:
        statuses += sorted(df[status_col].dropna().astype(str).unique().tolist())
    selected_status = st.sidebar.selectbox('Project Status', statuses, index=0)

    # Manual override for columns (safe defaults)
    if st.sidebar.checkbox("Manually choose columns", value=False):
        cols_options = [None] + list(df.columns)
        # find index safely
        def safe_index(val):
            try:
                return cols_options.index(val)
            except Exception:
                return 0
        budget_col = st.sidebar.selectbox("Choose budget column", options=cols_options, index=safe_index(budget_col))
        date_col = st.sidebar.selectbox("Choose date column", options=cols_options, index=safe_index(date_col))
        geo_col = st.sidebar.selectbox("Choose geographical column", options=cols_options, index=safe_index(geo_col))
        donor_col = st.sidebar.selectbox("Choose donor column", options=cols_options, index=safe_index(donor_col))
        status_col = st.sidebar.selectbox("Choose status column", options=cols_options, index=safe_index(status_col))

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
    parsed_dates = None
    if date_col:
        parsed_dates = try_parse_date_series(df_f[date_col])
        # fallback (second attempt) handled inside try_parse_date_series
        df_f['__date_parsed'] = parsed_dates
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
    st.markdown('### Funding by Donor (bar chart with value labels)')
    if donor_col and '__budget_numeric' in df_f.columns:
        by_donor = df_f.groupby(donor_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        fig = px.bar(by_donor, x=donor_col, y='__budget_numeric', text='__budget_numeric', labels={'__budget_numeric': 'Budget ($)'}, title='Funding by Donor')
        # Value labels formatting
        fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_tickangle=-45, margin=dict(t=50, b=150))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Donor or budget column not found — cannot draw 'Funding by Donor' bar chart.")

    st.markdown('### Projects by Status (pie chart with values & percentages)')
    if status_col:
        fig2 = px.pie(df_f, names=status_col, title='Projects by Status', hole=0.35)
        # show labels, values and percentages
        fig2.update_traces(textinfo='label+percent+value', textposition='inside', insidetextorientation='radial')
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Project status column not found — cannot draw 'Projects by Status' pie chart.")

    st.markdown('### Geographical Focus — Budget share (pie chart with values & percentages)')
    if geo_col and '__budget_numeric' in df_f.columns:
        geo_df = df_f.groupby(geo_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        fig3 = px.pie(geo_df, names=geo_col, values='__budget_numeric', title='Geographical focus — Budget share', hole=0.35)
        fig3.update_traces(textinfo='label+percent+value', textposition='inside', insidetextorientation='radial')
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Geographical focus or budget column not found — cannot draw geographical-budget pie chart.")

    st.markdown('### Date vs Budget (line chart using From Date if available)')
    # For line chart aggregate budget by parsed date (monthly)
    if '__date_parsed' in df_f.columns and not df_f['__date_parsed'].isna().all():
        temp = df_f.copy()
        temp = temp[temp['__date_parsed'].notna()]
        if not temp.empty:
            # Aggregate by month for smoother trend
            temp['__period'] = temp['__date_parsed'].dt.to_period('M').dt.to_timestamp()
            time_df = temp.groupby('__period', as_index=False)['__budget_numeric'].sum().sort_values('__period')
            fig4 = px.line(time_df, x='__period', y='__budget_numeric', markers=True, labels={'__period': 'Date', '__budget_numeric': 'Budget ($)'}, title='Date vs Budget (monthly aggregated)')
            # show budget values at markers
            fig4.update_traces(mode='lines+markers+text', textposition='top center', text=time_df['__budget_numeric'].map(lambda v: f"{v:,.0f}"))
            fig4.update_layout(margin=dict(t=50, b=50))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No valid date values found to build the Date vs Budget line chart.")
    else:
        st.info("Date column ('From Date' preferred) not found or not parseable — cannot draw Date vs Budget line chart.")

# End of file — note: no raw data table/export displayed as requested.
