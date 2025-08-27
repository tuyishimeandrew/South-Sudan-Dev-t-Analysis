
# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import base64

st.set_page_config(page_title='Donor Allocations — South Sudan', layout='wide')

# --- Load data ---
@st.cache_data(show_spinner=False)
def load_data(path: str):
    df = pd.read_excel(path, sheet_name=0)
    df.columns = [c.strip() for c in df.columns]
    return df

DATA_PATH = Path('static') / 'SS Raw Data.xlsx'
df = load_data(DATA_PATH)

# --- Set background image ---
def set_bg(image_file):
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
        background-color: rgba(255,255,255,0.8);
        border-radius: 15px;
        padding: 2rem;
    }}
    </style>
    """.replace("{{encoded}}", encoded)
    st.markdown(page_bg, unsafe_allow_html=True)

set_bg("static/download.jpeg")

# --- Sidebar filters ---
st.sidebar.header('Filters')
donors = ['All'] + sorted(df['Donor'].dropna().unique().tolist()) if 'Donor' in df.columns else ['All']
statuses = ['All'] + sorted(df['Project Status'].dropna().unique().tolist()) if 'Project Status' in df.columns else ['All']

selected_donor = st.sidebar.selectbox('Donor', donors, index=0)
selected_status = st.sidebar.selectbox('Project Status', statuses, index=0)

# --- Filtering ---
mask = pd.Series([True] * len(df))
if selected_donor != 'All':
    mask &= df['Donor'] == selected_donor
if selected_status != 'All':
    mask &= df['Project Status'] == selected_status
df_f = df[mask]

# --- KPIs ---
st.title("South Sudan Donor Allocations Dashboard")
col1, col2, col3 = st.columns([1,1,1])
total_budget = df_f['Budget ($)'].sum() if 'Budget ($)' in df_f.columns else None
projects = df_f['Project Title'].nunique() if 'Project Title' in df_f.columns else len(df_f)
donor_count = df_f['Donor'].nunique() if 'Donor' in df_f.columns else None
col1.metric('Total Budget ($)', f"{total_budget:,.0f}" if total_budget is not None else 'N/A')
col2.metric('Projects', projects)
col3.metric('Donors', donor_count if donor_count is not None else 'N/A')

# --- Charts ---
st.markdown('### Funding by Donor')
if 'Donor' in df_f.columns and 'Budget ($)' in df_f.columns:
    fig = px.bar(df_f.groupby('Donor', as_index=False)['Budget ($)'].sum().sort_values('Budget ($)', ascending=False),
                 x='Donor', y='Budget ($)', title='Funding by Donor')
    st.plotly_chart(fig, use_container_width=True)

st.markdown('### Projects by Status')
if 'Project Status' in df_f.columns:
    fig2 = px.pie(df_f, names='Project Status', title='Projects by Status', hole=0.4)
    st.plotly_chart(fig2, use_container_width=True)

# --- Data table ---
st.markdown('### Data')
st.dataframe(df_f.reset_index(drop=True))
