# streamlit_app_styled.py
"""
Streamlit dashboard for South Sudan donor allocations.

Updates:
- Always use 'Budget ($m)' as the budget column.
- Line chart aggregates budgets yearly (instead of monthly).
- Bar chart: Budget vs Main Sector
- Each visual title simplified and includes an interactive total displayed next to the title.
- Date slider in the sidebar labelled 'Date' filters by the detected date column.
- Projects by Status pie chart shows budget share (sum of Budget ($m)) instead of counts.
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
    parsed = pd.to_datetime(s, errors='coerce', dayfirst=False)
    if parsed.notna().any():
        return parsed
    cleaned = s.astype(str).str.replace(r'[^0-9\-\/\.]', '', regex=True)
    if cleaned.str.match(r'^\d{1,2}\.\d{4}$').any():
        parsed2 = pd.to_datetime(cleaned, format='%m.%Y', errors='coerce')
        if parsed2.notna().any():
            return parsed2
    parsed3 = pd.to_datetime(cleaned, errors='coerce', dayfirst=True)
    return parsed3

# --- Load data ---
df = load_data(DATA_PATH)

# --- Sidebar: filters only ---
st.sidebar.header('Filters')

if df.empty:
    st.sidebar.warning("No data loaded. Check DATA_PATH and that the GitHub file is public.")
    st.warning("No data loaded. Check the DATA_PATH and that the GitHub file is public.")
else:
    # Detection candidates
    donor_candidates = ['Donor', 'Funding Agency', 'Funder']
    status_candidates = ['Project Status', 'Status']
    project_title_candidates = ['Project Title', 'Title', 'ProjectName']
    date_candidates = [
        'From Date', 'Date', 'Start Date', 'StartDate', 'Project Start Date',
        'Project Start', 'month.year', 'Month.Year', 'Month Year'
    ]
    main_sector_candidates = ['Main Sector', 'Main sector', 'Sector', 'MainSector', 'Main_Sector']
    geo_candidates = ['Geographical focus', 'Geographical Focus', 'Geographic focus', 'Geographic Focus', 'Location', 'Region', 'Geography']

    # Fixed budget column
    budget_col = 'Budget ($m)'
    donor_col = find_first_matching_column(df, donor_candidates)
    status_col = find_first_matching_column(df, status_candidates)
    title_col = find_first_matching_column(df, project_title_candidates)
    date_col = find_first_matching_column(df, date_candidates)
    main_sector_col = find_first_matching_column(df, main_sector_candidates)
    geo_col = find_first_matching_column(df, geo_candidates)

    # Filters: only Donor and Project Status (plus new Date slider)
    donors = ['All']
    if donor_col:
        donors += sorted(df[donor_col].dropna().astype(str).unique().tolist())
    selected_donor = st.sidebar.selectbox('Donor', donors, index=0)

    statuses = ['All']
    if status_col:
        statuses += sorted(df[status_col].dropna().astype(str).unique().tolist())
    selected_status = st.sidebar.selectbox('Project Status', statuses, index=0)

    # --- Date slider for the detected date column (labelled 'Date') ---
    selected_date_range = None
    if date_col:
        parsed_all = try_parse_date_series(df[date_col])
        if parsed_all.notna().any():
            min_date = parsed_all.min().date()
            max_date = parsed_all.max().date()
            selected_date_range = st.sidebar.slider(
                'Date',
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                format="YYYY-MM-DD"
            )
        else:
            st.sidebar.info("Date column found but values not parseable for slider.")

    # --- Filtering the dataframe according to sidebar ---
    mask = pd.Series(True, index=df.index)
    if selected_donor != 'All' and donor_col:
        mask &= df[donor_col].astype(str) == selected_donor
    if selected_status != 'All' and status_col:
        mask &= df[status_col].astype(str) == selected_status
    if selected_date_range and date_col:
        parsed_for_mask = try_parse_date_series(df[date_col])
        start_ts = pd.Timestamp(selected_date_range[0])
        end_ts = pd.Timestamp(selected_date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        mask &= parsed_for_mask.between(start_ts, end_ts, inclusive="both")

    df_f = df[mask].copy()

    # --- Preprocess budget and date ---
    if budget_col in df_f.columns:
        df_f['__budget_numeric'] = pd.to_numeric(df_f[budget_col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True), errors='coerce').fillna(0.0)
    else:
        df_f['__budget_numeric'] = 0.0

    if date_col:
        df_f['__date_parsed'] = try_parse_date_series(df_f[date_col])
    else:
        df_f['__date_parsed'] = pd.NaT

    # --- KPIs ---
    st.title("South Sudan Donor Allocations")
    col1, col2, col3 = st.columns([1,1,1])
    total_budget = df_f['__budget_numeric'].sum()
    projects = df_f[title_col].nunique() if title_col in df_f.columns else len(df_f)
    donor_count = df_f[donor_col].nunique() if donor_col in df_f.columns else None
    col1.metric('Total Budget ($m)', f"{total_budget:,.2f}")
    col2.metric('Projects', projects)
    col3.metric('Donors', donor_count if donor_count is not None else 'N/A')

    # --- Charts container ---
    st.markdown('---')

    # 1) Funding by Main Sector (bar chart) — simple title + interactive total
    if main_sector_col and '__budget_numeric' in df_f.columns:
        by_sector = df_f.groupby(main_sector_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        # interactive total for this chart
        total_sector = by_sector['__budget_numeric'].sum()
        tcol, vcol = st.columns([6,1])
        tcol.markdown("### Funding by Main Sector")
        vcol.markdown(f"**Total (Budget $m):** {total_sector:,.2f}")
        fig = px.bar(
            by_sector,
            x=main_sector_col,
            y='__budget_numeric',
            text='__budget_numeric',
            labels={main_sector_col: 'Main Sector', '__budget_numeric': 'Budget ($m)'}
        )
        fig.update_traces(texttemplate='%{text:,.2f}', textposition='outside', cliponaxis=False)
        fig.update_layout(
            title=dict(text='Funding by Main Sector', x=0.5),
            xaxis_tickangle=-45,
            margin=dict(t=60, b=160, l=80, r=40)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("### Funding by Main Sector")
        st.info("Main Sector column not found — cannot draw 'Funding by Main Sector' bar chart.")

    # 2) Projects by Status (pie chart — budget share) — simple title + interactive total
    if status_col and '__budget_numeric' in df_f.columns:
        status_df = df_f.groupby(status_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        total_status = status_df['__budget_numeric'].sum()
        tcol, vcol = st.columns([6,1])
        tcol.markdown("### Projects by Status")
        vcol.markdown(f"**Total (Budget $m):** {total_status:,.2f}")
        fig2 = px.pie(
            status_df,
            names=status_col,
            values='__budget_numeric',
            title='Projects by Status',
            hole=0.35,
            labels={status_col: 'Project Status', '__budget_numeric': 'Budget ($m)'}
        )
        fig2.update_traces(textinfo='label+percent+value', textposition='inside', texttemplate='%{label}<br>%{percent}<br>%{value:,.2f}')
        fig2.update_layout(margin=dict(t=60, b=80, l=80, r=80), title=dict(text='Projects by Status', x=0.5))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.markdown("### Projects by Status")
        st.info("Project status column not found or budget column missing — cannot draw 'Projects by Status' pie chart.")

    # 3) Geographical Focus — Budget share (pie chart) — simple title + interactive total
    if geo_col and '__budget_numeric' in df_f.columns:
        geo_df = df_f.groupby(geo_col, as_index=False)['__budget_numeric'].sum().sort_values('__budget_numeric', ascending=False)
        total_geo = geo_df['__budget_numeric'].sum()
        tcol, vcol = st.columns([6,1])
        tcol.markdown("### Geographical Focus — Budget share")
        vcol.markdown(f"**Total (Budget $m):** {total_geo:,.2f}")
        fig3 = px.pie(geo_df, names=geo_col, values='__budget_numeric', title='Geographical Focus — Budget share', hole=0.35)
        fig3.update_traces(textinfo='label+percent+value', textposition='inside')
        fig3.update_layout(margin=dict(t=60, b=80, l=80, r=80), title=dict(text='Geographical Focus — Budget share', x=0.5))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.markdown("### Geographical Focus — Budget share")
        st.info("Geographical focus column not found — cannot draw geographical-budget pie chart.")

    # 4) Date vs Budget (line chart yearly) — simple title + interactive total
    st.markdown("")
    st.markdown("### Date vs Budget (Yearly)")
    if '__date_parsed' in df_f.columns and not df_f['__date_parsed'].isna().all():
        temp = df_f[df_f['__date_parsed'].notna()].copy()
        if not temp.empty:
            temp['__year'] = temp['__date_parsed'].dt.year
            yearly_df = temp.groupby('__year', as_index=False)['__budget_numeric'].sum().sort_values('__year')
            total_yearly = yearly_df['__budget_numeric'].sum()
            # show total next to the simple title
            _, vcol = st.columns([6,1])
            vcol.markdown(f"**Total (Budget $m):** {total_yearly:,.2f}")
            fig4 = px.line(yearly_df, x='__year', y='__budget_numeric', markers=True,
                           labels={'__year': 'Year', '__budget_numeric': 'Budget ($m)'})
            fig4.update_traces(mode='lines+markers+text', textposition='top center',
                               text=yearly_df['__budget_numeric'].map(lambda v: f"{v:,.2f}"))
            fig4.update_layout(title=dict(text='Date vs Budget (Yearly)', x=0.5),
                               margin=dict(t=60, b=80, l=80, r=40))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No valid date values found to build the yearly Date vs Budget line chart.")
    else:
        st.info("Date column ('From Date' preferred) not found or not parseable — cannot draw Date vs Budget line chart.")
