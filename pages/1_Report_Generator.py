import streamlit as st
import requests
import json
import time
import pandas as pd
from datetime import datetime

# ==========================================================
# CONFIGURATION — UPDATE THESE VALUES
# ==========================================================
DATABRICKS_INSTANCE = st.secrets.get('DATABRICKS_INSTANCE')
DATABRICKS_TOKEN = st.secrets.get('DB_token')
NOTEBOOK_PATH = st.secrets.get('NOTEBOOK_PATH')
VOLUME_PATH = st.secrets.get('VOLUME_PATH')
CLUSTER_ID = st.secrets.get('CLUSTER_ID')
CHATBOT_ENDPOINT=st.secrets.get('CHATBOT_ENDPOINT')

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="AI Report Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Disable default Streamlit menu and footer
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display:none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================================
# INITIALIZE SESSION STATE
# ==========================================================
if 'monitoring_jobs' not in st.session_state:
    st.session_state.monitoring_jobs = []
if 'completed_jobs' not in st.session_state:
    st.session_state.completed_jobs = []
if 'jobs_placeholder' not in st.session_state:
    st.session_state.jobs_placeholder = None

# ==========================================================
# MODERN CSS STYLING
# ==========================================================
st.markdown("""
<style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .block-container {
        padding-top: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 1400px;
    }
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Styles */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.25rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .header-content {
        flex: 1;
    }
    
    .header-logo {
        height: 60px;
        width: auto;
        max-width: 200px;
        object-fit: contain;
    }
    
    .main-header h1 {
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 0.875rem;
        margin: 0.25rem 0 0 0;
    }
    
    /* Theme Variables */
    [data-testid="stAppViewContainer"][data-theme="dark"] {
        --background-color: #0e1117;
        --card-background: #262730;
        --text-primary: #fafafa;
        --text-secondary: #a3a8b4;
        --border-color: #464a57;
        --hover-background: #1e2029;
    }
    
    [data-testid="stAppViewContainer"][data-theme="light"] {
        --background-color: #ffffff;
        --card-background: #ffffff;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --border-color: #e5e7eb;
        --hover-background: #f9fafb;
    }
    
    /* Input & Button Styles */
    .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 2px solid var(--border-color) !important;
        padding: 0.6rem 0.875rem !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        background-color: var(--card-background) !important;
        color: var(--text-primary) !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102,126,234,0.1) !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 4px rgba(102,126,234,0.3) !important;
        width: 100% !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 12px rgba(102,126,234,0.4) !important;
    }
    
    /* Progress Box */
    .progress-box {
        background: linear-gradient(135deg, rgba(102,126,234,0.1) 0%, rgba(118,75,162,0.1) 100%);
        border: 2px solid #667eea;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .progress-icon {
        font-size: 1.5rem;
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(1.05); }
    }
    
    .progress-content {
        flex: 1;
    }
    
    .progress-text {
        font-size: 0.95rem;
        font-weight: 600;
        color: #667eea;
        margin-bottom: 0.15rem;
    }
    
    .progress-subtext {
        font-size: 0.8rem;
        color: var(--text-secondary);
    }
    
    /* Report Card Styles */
    .report-card {
        background: var(--card-background);
        border: 1px solid var(--border-color);
        border-radius: 10px;
        padding: 0.875rem 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .report-card:hover {
        box-shadow: 0 4px 8px rgba(102,126,234,0.2);
        transform: translateY(-1px);
        border-color: #667eea;
        background: var(--hover-background);
    }
    
    .report-card.new-report {
        border: 2px solid #10b981;
        background: linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(16,185,129,0.05) 100%);
        animation: highlight 2s ease-in-out;
    }
    
    @keyframes highlight {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }
    
    .report-name {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.35rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    
    .report-meta {
        display: flex;
        gap: 1rem;
        color: var(--text-secondary);
        font-size: 0.8rem;
        margin-top: 0.35rem;
    }
    
    .report-meta-item {
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }
    
    /* Download Button */
    .stDownloadButton > button {
        background: #10b981 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.45rem 1rem !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }
    
    .stDownloadButton > button:hover {
        background: #059669 !important;
        transform: scale(1.02) !important;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 1.25rem 0 0.75rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Stats Cards */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.15rem;
    }
    
    .stat-label {
        font-size: 0.8rem;
        opacity: 0.9;
    }
    
    /* Empty State */
    .empty-state {
        text-align: center;
        padding: 3rem;
        color: var(--text-secondary);
    }
    
    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }
    
    .empty-state h3 {
        color: var(--text-primary);
    }
    
    /* Filter Select */
    .stSelectbox > div > div {
        border-radius: 8px !important;
        border: 2px solid var(--border-color) !important;
        transition: all 0.2s ease !important;
        background-color: var(--card-background) !important;
    }
    
    .stSelectbox > div > div:focus-within {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102,126,234,0.1) !important;
    }
    
    /* Footer */
    .footer-text {
        color: var(--text-secondary);
    }
    
    /* Prevent page jump/flicker during rerun */
    [data-testid="stAppViewContainer"] {
        transition: none !important;
    }
    
    .main .block-container {
        transition: none !important;
    }
    
    /* Completely hide all spinners and status indicators */
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    
    .stSpinner {
        display: none !important;
    }
    
    /* Prevent opacity changes during updates */
    [data-testid="stAppViewContainer"] > .main {
        opacity: 1 !important;
    }
    
    /* Keep content visible during reruns */
    .main > div {
        opacity: 1 !important;
        visibility: visible !important;
    }
    
    /* Prevent any fade effects */
    .element-container,
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    [data-testid="column"] {
        animation: none !important;
        transition: none !important;
    }
    
    /* Force immediate rendering without transitions */
    .main, .main > div, .block-container {
        animation: none !important;
        transition: none !important;
        opacity: 1 !important;
        visibility: visible !important;
    }
    
    /* Exception: keep our custom animations */
    .chat-message {
        animation: fadeIn 0.2s ease-in !important;
    }
    
    .progress-icon {
        animation: pulse 2s ease-in-out infinite !important;
    }
    
    .report-card.new-report {
        animation: highlight 2s ease-in-out !important;
    }
    
    .stButton > button:hover,
    .report-card:hover {
        transition: all 0.2s ease !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# HELPER FUNCTIONS WITH CACHING
# ==========================================================
@st.cache_data(ttl=30)
def check_job_status(run_id):
    """Check the status of a Databricks job run"""
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    status_url = f"{DATABRICKS_INSTANCE}/api/2.1/jobs/runs/get?run_id={run_id}"
    
    try:
        response = requests.get(status_url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            state = data.get('state', {})
            life_cycle_state = state.get('life_cycle_state', 'UNKNOWN')
            result_state = state.get('result_state', None)
            
            return {
                'life_cycle_state': life_cycle_state,
                'result_state': result_state,
                'is_terminal': life_cycle_state in ['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR']
            }
    except:
        pass
    
    return None

@st.cache_data(ttl=60)
def get_report_count():
    """Get current count of PDF reports"""
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Accept": "application/json"
    }
    
    url = f"{DATABRICKS_INSTANCE}/api/2.0/fs/directories{VOLUME_PATH}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            files = response.json().get("contents", [])
            df = pd.DataFrame(files)
            if not df.empty:
                pdf_count = len(df[~df["is_directory"] & df["name"].str.endswith(".pdf")])
                return pdf_count
    except:
        pass
    
    return 0

# ==========================================================
# HEADER
# ==========================================================
LOGO_URL = "https://media.licdn.com/dms/image/v2/C4E0BAQGtXskL4EvJmA/company-logo_200_200/company-logo_200_200/0/1632401962756/koantek_logo?e=2147483647&v=beta&t=D4GLT1Pu2vvxLR1iKZZbUJWN7K_uaPSF0T1mZl6Le-o"

st.markdown(f"""
<div class="main-header">
    <div class="header-content">
        <h1>📊 AI Report Generator</h1>
        <p>Generate comprehensive business reports with AI</p>
    </div>
    <img src="{LOGO_URL}" class="header-logo" alt="Koantek Logo" onerror="this.style.display='none'">
</div>
""", unsafe_allow_html=True)

# ==========================================================
# REPORT GENERATOR
# ==========================================================
col1, col2 = st.columns([5, 1], vertical_alignment="bottom")

with col1:
    report_query = st.text_input(
        "What would you like to analyze?",
        placeholder="e.g., violation report / BU Analysis report etc.",
        label_visibility="visible",
        key="report_query"
    )

with col2:
    st.write("")
    run_btn = st.button(
        "Generate", 
        use_container_width=True,
        key="run_btn"
    )

# JOB SUBMISSION & MONITORING LOGIC
if run_btn:
    if not report_query.strip():
        st.warning("⚠️ Please enter a query to generate a report.")
    elif not all([DATABRICKS_TOKEN, DATABRICKS_INSTANCE, CLUSTER_ID, NOTEBOOK_PATH]):
        st.error("🔧 Configuration Error: Please check your Databricks settings.")
    # Prevent duplicate submissions
    elif any(job['query'] == report_query for job in st.session_state.monitoring_jobs):
        st.warning(f"⚠️ A job for '{report_query}' is already running. Please wait for it to complete.")
    else:
        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "run_name": f"ai_report_{int(time.time())}",
            "existing_cluster_id": CLUSTER_ID,
            "notebook_task": {
                "notebook_path": NOTEBOOK_PATH,
                "base_parameters": {"user_question": report_query}
            }
        }
        
        submit_url = f"{DATABRICKS_INSTANCE}/api/2.1/jobs/runs/submit"
        
        with st.spinner("🔄 Submitting job to Databricks..."):
            try:
                res = requests.post(submit_url, headers=headers, data=json.dumps(payload), timeout=30)
                
                if res.status_code == 200:
                    run_id = res.json().get("run_id")
                    st.session_state.monitoring_jobs.append({
                        'run_id': run_id,
                        'query': report_query,
                        'start_time': time.time(),
                        'initial_count': get_report_count()
                    })
                    st.success(f"✅ Job submitted successfully! Run ID: `{run_id}`")
                    st.info("💡 You can submit more queries while this one processes.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Failed to start job: {res.status_code} - {res.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Connection Error: {str(e)}")

# Job monitoring display - USING PLACEHOLDER TO UPDATE IN-PLACE
if st.session_state.monitoring_jobs:
    # Create section header once
    st.markdown("---")
    st.markdown("### 🔄 Active Jobs")
    
    # Create or use existing placeholder
    if st.session_state.jobs_placeholder is None:
        st.session_state.jobs_placeholder = st.empty()
    
    # Check statuses
    jobs_to_remove = []
    
    for idx, job in enumerate(st.session_state.monitoring_jobs):
        run_id = job['run_id']
        job_status = check_job_status(run_id)
        current_report_count = get_report_count()
        elapsed_time = int(time.time() - job['start_time'])
        
        if current_report_count > job['initial_count'] or (job_status and job_status['is_terminal'] and job_status['result_state'] == 'SUCCESS'):
            if current_report_count > job['initial_count'] or elapsed_time > 300:
                jobs_to_remove.append(idx)
                if run_id not in st.session_state.completed_jobs:
                    st.session_state.completed_jobs.append(run_id)
                    st.success(f"✅ Report generated for: {job['query']}")

        elif job_status and job_status['is_terminal'] and job_status['result_state'] != 'SUCCESS':
            jobs_to_remove.append(idx)
            st.error(f"❌ Job failed: {job['query']} - {job_status['result_state']}")
    
    # Remove completed jobs
    for idx in sorted(jobs_to_remove, reverse=True):
        st.session_state.monitoring_jobs.pop(idx)
    
    # Update placeholder with current active jobs
    if st.session_state.monitoring_jobs:
        with st.session_state.jobs_placeholder.container():
            for job in st.session_state.monitoring_jobs:
                elapsed_time = int(time.time() - job['start_time'])
                minutes, seconds = divmod(elapsed_time, 60)
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f"""
                    <div class="progress-box">
                        <div class="progress-icon">⚙️</div>
                        <div class="progress-content">
                            <div class="progress-text">{job['query']}</div>
                            <div class="progress-subtext">Run ID: {job['run_id']} • {minutes}m {seconds}s elapsed</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.write("")
                    if st.button("Cancel", key=f"cancel_{job['run_id']}", use_container_width=True):
                        st.session_state.monitoring_jobs = [j for j in st.session_state.monitoring_jobs if j['run_id'] != job['run_id']]
                        st.session_state.jobs_placeholder = None
                        st.rerun()
        time.sleep(5)
        st.rerun()
    else:
        # Clear placeholder when no jobs
        st.session_state.jobs_placeholder = None

# REPORTS SECTION
col_header, col_filter = st.columns([3, 1])
with col_header:
    st.markdown('<div class="section-header">📂 Generated Reports</div>', unsafe_allow_html=True)
with col_filter:
    st.write("")
    date_filter = st.selectbox(
        "🔍 Filter",
        ["Last 5 Reports", "Today", "Last 7 Days", "Last 30 Days", "All Reports"],
        label_visibility="collapsed",
        key="report_filter"
    )

if not all([DATABRICKS_TOKEN, DATABRICKS_INSTANCE, VOLUME_PATH]):
    st.warning("🔧 Please configure Databricks credentials to view reports.")
else:
    headers = {"Authorization": f"Bearer {DATABRICKS_TOKEN}", "Accept": "application/json"}
    url = f"{DATABRICKS_INSTANCE}/api/2.0/fs/directories{VOLUME_PATH}"
    
    try:
        with st.spinner("📥 Loading reports..."):
            response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            files = response.json().get("contents", [])
            
            if not files:
                st.markdown("""<div class="empty-state"><div class="empty-state-icon">📭</div><h3>No Reports Yet</h3><p>Generate your first report using the form above</p></div>""", unsafe_allow_html=True)
            else:
                df = pd.DataFrame(files)
                df["last_modified"] = pd.to_datetime(df["last_modified"], unit="ms")
                pdf_df = df[(~df["is_directory"]) & (df["name"].str.endswith(".pdf"))].sort_values("last_modified", ascending=False)
                
                now = datetime.now()
                if date_filter == "Today": 
                    pdf_df = pdf_df[pdf_df["last_modified"].dt.date == now.date()]
                elif date_filter == "Last 7 Days": 
                    pdf_df = pdf_df[pdf_df["last_modified"] >= now - pd.Timedelta(days=7)]
                elif date_filter == "Last 30 Days": 
                    pdf_df = pdf_df[pdf_df["last_modified"] >= now - pd.Timedelta(days=30)]
                elif date_filter == "Last 5 Reports": 
                    pdf_df = pdf_df.head(5)
                
                total_reports = len(pdf_df)
                total_size_mb = round(pdf_df["file_size"].sum() / (1024 * 1024), 2) if not pdf_df.empty else 0
                
                col1, col2, col3 = st.columns(3)
                with col1: 
                    st.markdown(f"""<div class="stat-card"><div class="stat-value">{total_reports}</div><div class="stat-label">Total Reports</div></div>""", unsafe_allow_html=True)
                with col2: 
                    st.markdown(f"""<div class="stat-card"><div class="stat-value">{total_size_mb}</div><div class="stat-label">Total Size (MB)</div></div>""", unsafe_allow_html=True)
                with col3:
                    latest = pdf_df.iloc[0]["last_modified"].strftime("%b %d") if not pdf_df.empty else "N/A"
                    st.markdown(f"""<div class="stat-card"><div class="stat-value">{latest}</div><div class="stat-label">Latest Report</div></div>""", unsafe_allow_html=True)
                
                st.write("")
                
                if pdf_df.empty:
                    st.info("📄 No reports match the selected filter.")
                else:
                    for idx, row in pdf_df.iterrows():
                        file_name, file_path = row["name"], row["path"]
                        size_kb = round(row["file_size"] / 1024, 1)
                        mod_time = row["last_modified"].strftime("%b %d, %Y %I:%M %p")
                        is_new = (datetime.now() - row["last_modified"]).total_seconds() < 30
                        
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            card_class = "report-card new-report" if is_new else "report-card"
                            new_badge = "🆕 " if is_new else ""
                            st.markdown(f"""
                            <div class="{card_class}">
                                <div class="report-name">{new_badge}📄 {file_name}</div>
                                <div class="report-meta"><div class="report-meta-item">🕒 {mod_time}</div><div class="report-meta-item">💾 {size_kb} KB</div></div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            file_api_url = f"{DATABRICKS_INSTANCE}/api/2.0/fs/files{file_path}"
                            try:
                                file_res = requests.get(file_api_url, headers=headers, timeout=60) 
                                if file_res.status_code == 200:
                                    pdf_bytes = file_res.content
                                    st.write("")
                                    st.download_button(label="⬇️ Download", data=pdf_bytes, file_name=file_name, mime="application/pdf", key=f"download_{file_name}_{idx}")
                                else: 
                                    st.error(f"Error: {file_res.status_code}")
                            except requests.exceptions.RequestException as e: 
                                st.error(f"Failed to fetch file")
        
        elif response.status_code == 404: 
            st.warning("📁 Volume path not found. Please verify your VOLUME_PATH configuration.")
        else: 
            st.error(f"❌ Error listing files: {response.status_code} - {response.text}")
    
    except requests.exceptions.RequestException as e: 
        st.error(f"❌ Connection Error: Unable to connect to Databricks. {str(e)}")

# ==========================================================
# FOOTER
# ==========================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 0.8rem; padding: 0.75rem;">
    <p class="footer-text">Powered by Koantek</p>
</div>
""", unsafe_allow_html=True)

