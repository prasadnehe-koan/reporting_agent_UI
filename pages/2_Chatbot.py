import streamlit as st
import requests
import json

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="AI Chatbot",
    page_icon="💬",
    layout="wide"
)

# ==========================================================
# CONFIGURATION
# ==========================================================
DATABRICKS_INSTANCE = st.secrets.get('DATABRICKS_INSTANCE')
DATABRICKS_TOKEN = st.secrets.get('DB_token')
NOTEBOOK_PATH = st.secrets.get('NOTEBOOK_PATH')
VOLUME_PATH = st.secrets.get('VOLUME_PATH')
CLUSTER_ID = st.secrets.get('CLUSTER_ID')
CHATBOT_ENDPOINT=st.secrets.get('CHATBOT_ENDPOINT')
# ==========================================================
# INITIALIZE SESSION STATE
# ==========================================================
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'awaiting_response' not in st.session_state:
    st.session_state.awaiting_response = False

# ==========================================================
# HELPER FUNCTION
# ==========================================================
def chat_with_bot(conversation_history):
    """Send full conversation history to chatbot and get response - NO TRIMMING"""
    if not all([DATABRICKS_TOKEN, CHATBOT_ENDPOINT]):
        return "Error: Chatbot endpoint or token is not configured."
    
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Build input array from conversation history
    input_messages = []
    for msg in conversation_history:
        input_messages.append({
            "status": None,
            "content": msg["content"],
            "role": msg["role"],
            "type": "message"
        })

    payload = {
        "input": input_messages
    }

    try:
        response = requests.post(CHATBOT_ENDPOINT, headers=headers, json=payload, timeout=300)
        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"

        texts = []
        raw = response.text.strip()
        
        # Handle NDJSON
        if '\n' in raw:
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "response.output_item.done":
                        item = data.get("item", {})
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                texts.append(content.get("text", ""))
                except json.JSONDecodeError:
                    continue
        else:
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and "output" in data:
                    for msg in data["output"]:
                        for content in msg.get("content", []):
                            if content.get("type") == "output_text":
                                texts.append(content.get("text", ""))
            except Exception:
                pass

        # Return raw result - NO TRIMMING OR CLEANUP
        result = "\n\n---\n\n".join(texts) if texts else "No response received. Check model/endpoint status."
        return result

    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================================
# HEADER
# ==========================================================
LOGO_URL = "https://media.licdn.com/dms/image/v2/C4E0BAQGtXskL4EvJmA/company-logo_200_200/company-logo_200_200/0/1632401962756/koantek_logo?e=2147483647&v=beta&t=D4GLT1Pu2vvxLR1iKZZbUJWN7K_uaPSF0T1mZl6Le-o"

st.markdown(f"""
<style>
    .main-header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.25rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    
    .header-content {{
        flex: 1;
    }}
    
    .header-logo {{
        height: 60px;
        width: auto;
        max-width: 200px;
        object-fit: contain;
    }}
    
    .main-header h1 {{
        color: white;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }}
    
    .main-header p {{
        color: rgba(255,255,255,0.9);
        font-size: 0.875rem;
        margin: 0.25rem 0 0 0;
    }}
    
    /* Small clear button */
    button[kind="secondary"] {{
        padding: 0.5rem !important;
        font-size: 1.2rem !important;
    }}
</style>

<div class="main-header">
    <div class="header-content">
        <h1>💬 AI Chatbot</h1>
        <p>Ask questions about your business data</p>
    </div>
    <img src="{LOGO_URL}" class="header-logo" alt="Koantek Logo" onerror="this.style.display='none'">
</div>
""", unsafe_allow_html=True)

# ==========================================================
# CHATBOT UI
# ==========================================================

# Scrollable chat container
chat_container = st.container(height=500)

with chat_container:
    # Display all messages
    if not st.session_state.chat_messages:
        st.info("👋 Start a conversation by typing a message below!")
    else:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Show thinking indicator if processing
    if st.session_state.awaiting_response:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                bot_response = chat_with_bot(st.session_state.chat_messages)
        
        # Add response to history
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": bot_response
        })
        st.session_state.awaiting_response = False
        st.rerun()

# Fixed input area at bottom
col1, col2 = st.columns([9, 1])

with col1:
    # Chat input (handles Enter key automatically)
    prompt = st.chat_input(
        "Type your message here...", 
        disabled=st.session_state.awaiting_response,
        key="chat_input_main"
    )

with col2:
    # Small clear button
    if st.button(
        "🗑️", 
        key="clear_chat_btn", 
        help="Clear chat history",
        type="secondary",
        disabled=len(st.session_state.chat_messages) == 0 or st.session_state.awaiting_response
    ):
        st.session_state.chat_messages = []
        st.session_state.awaiting_response = False
        st.rerun()

# Handle message submission
if prompt:
    # Add user message immediately
    st.session_state.chat_messages.append({
        "role": "user",
        "content": prompt
    })
    
    # Set flag for API call
    st.session_state.awaiting_response = True
    
    # Immediate rerun - shows user message instantly
    st.rerun()

# ==========================================================
# FOOTER
# ==========================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; font-size: 0.8rem; padding: 0.75rem;">
    <p style="color: #6b7280;">Powered by Koantek</p>
</div>
""", unsafe_allow_html=True)
