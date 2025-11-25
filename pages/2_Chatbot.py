import streamlit as st
import requests
import json
from datetime import datetime
import uuid
import sqlite3
from contextlib import contextmanager

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(
    page_title="AI Chatbot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# CONFIGURATION
# ==========================================================
DATABRICKS_INSTANCE = st.secrets.get('DATABRICKS_INSTANCE')
DATABRICKS_TOKEN = st.secrets.get('DB_token')
NOTEBOOK_PATH = st.secrets.get('NOTEBOOK_PATH')
VOLUME_PATH = st.secrets.get('VOLUME_PATH')
CLUSTER_ID = st.secrets.get('CLUSTER_ID')
CHATBOT_ENDPOINT = st.secrets.get('CHATBOT_ENDPOINT')

# SQLite database file
DB_FILE = "chat_history.db"

# ==========================================================
# DATABASE FUNCTIONS
# ==========================================================
@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize SQLite database with required tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create chats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_current INTEGER DEFAULT 0
            )
        """)
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id) ON DELETE CASCADE
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
            ON messages(chat_id)
        """)
        
        conn.commit()

def save_chat_to_db(chat_id, title, created_at, is_current=False):
    """Save or update a chat in the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # If this is the current chat, unset all others
        if is_current:
            cursor.execute("UPDATE chats SET is_current = 0")
        
        cursor.execute("""
            INSERT OR REPLACE INTO chats (chat_id, title, created_at, is_current)
            VALUES (?, ?, ?, ?)
        """, (chat_id, title, created_at.isoformat(), 1 if is_current else 0))
        
        conn.commit()

def save_message_to_db(chat_id, role, content):
    """Save a message to the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (chat_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (chat_id, role, content, datetime.now().isoformat()))
        conn.commit()

def load_chats_from_db():
    """Load all chats from the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        chats = {}
        current_chat_id = None
        
        for row in rows:
            chat_id = row['chat_id']
            chats[chat_id] = {
                'title': row['title'],
                'created_at': datetime.fromisoformat(row['created_at']),
                'messages': []
            }
            
            if row['is_current']:
                current_chat_id = chat_id
        
        return chats, current_chat_id

def load_messages_for_chat(chat_id):
    """Load all messages for a specific chat"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT role, content FROM messages 
            WHERE chat_id = ? 
            ORDER BY message_id ASC
        """, (chat_id,))
        rows = cursor.fetchall()
        
        return [{'role': row['role'], 'content': row['content']} for row in rows]

def delete_chat_from_db(chat_id):
    """Delete a chat and all its messages from the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        cursor.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        conn.commit()

def clear_chat_messages_db(chat_id):
    """Clear all messages for a specific chat"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.commit()

def clear_all_data_db():
    """Clear all chats and messages from the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        cursor.execute("DELETE FROM chats")
        conn.commit()

def set_current_chat_db(chat_id):
    """Set a chat as the current active chat"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chats SET is_current = 0")
        cursor.execute("UPDATE chats SET is_current = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

# ==========================================================
# INITIALIZE DATABASE AND SESSION STATE
# ==========================================================
# Initialize database
init_database()

if 'chats' not in st.session_state:
    # Load from database
    loaded_chats, loaded_chat_id = load_chats_from_db()
    
    if loaded_chats:
        # Load messages for each chat
        for chat_id in loaded_chats.keys():
            loaded_chats[chat_id]['messages'] = load_messages_for_chat(chat_id)
        
        st.session_state.chats = loaded_chats
        st.session_state.current_chat_id = loaded_chat_id or list(loaded_chats.keys())[0]
    else:
        # Create initial chat if no saved data
        initial_id = str(uuid.uuid4())
        st.session_state.chats = {
            initial_id: {
                "title": "New Chat",
                "messages": [],
                "created_at": datetime.now()
            }
        }
        st.session_state.current_chat_id = initial_id
        save_chat_to_db(initial_id, "New Chat", datetime.now(), is_current=True)

if 'awaiting_response' not in st.session_state:
    st.session_state.awaiting_response = False

if 'editing_chat_id' not in st.session_state:
    st.session_state.editing_chat_id = None

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def get_current_chat():
    """Get the current active chat"""
    return st.session_state.chats.get(st.session_state.current_chat_id, {
        "title": "New Chat",
        "messages": [],
        "created_at": datetime.now()
    })

def create_new_chat():
    """Create a new chat session"""
    new_id = str(uuid.uuid4())
    st.session_state.chats[new_id] = {
        "title": "New Chat",
        "messages": [],
        "created_at": datetime.now()
    }
    st.session_state.current_chat_id = new_id
    st.session_state.awaiting_response = False
    save_chat_to_db(new_id, "New Chat", datetime.now(), is_current=True)

def delete_chat(chat_id):
    """Delete a chat session"""
    if chat_id in st.session_state.chats:
        del st.session_state.chats[chat_id]
        delete_chat_from_db(chat_id)
        
        # If deleting current chat, switch to another or create new
        if chat_id == st.session_state.current_chat_id:
            if st.session_state.chats:
                st.session_state.current_chat_id = list(st.session_state.chats.keys())[0]
                set_current_chat_db(st.session_state.current_chat_id)
            else:
                create_new_chat()

def switch_chat(chat_id):
    """Switch to a different chat"""
    st.session_state.current_chat_id = chat_id
    st.session_state.awaiting_response = False
    set_current_chat_db(chat_id)

def update_chat_title(chat_id, first_message):
    """Auto-generate chat title from first user message"""
    title = first_message[:50] + ("..." if len(first_message) > 50 else "")
    st.session_state.chats[chat_id]["title"] = title
    save_chat_to_db(
        chat_id, 
        title, 
        st.session_state.chats[chat_id]["created_at"],
        is_current=(chat_id == st.session_state.current_chat_id)
    )

def rename_chat(chat_id, new_title):
    """Rename a chat session"""
    if new_title and new_title.strip():
        st.session_state.chats[chat_id]["title"] = new_title.strip()
        save_chat_to_db(
            chat_id,
            new_title.strip(),
            st.session_state.chats[chat_id]["created_at"],
            is_current=(chat_id == st.session_state.current_chat_id)
        )

def chat_with_bot(conversation_history):
    """Send full conversation history to chatbot and get response"""
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

        result = "\n\n---\n\n".join(texts) if texts else "No response received. Check model/endpoint status."
        return result

    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================================
# SIDEBAR - CHAT HISTORY
# ==========================================================
with st.sidebar:
    st.markdown("""
    <style>
        /* Sidebar styling - Theme adaptive */
        [data-testid="stSidebar"] {
            background-color: var(--background-color);
        }
        
        .sidebar-title {
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: var(--primary-color);
            text-align: center;
        }
        
        /* Compact button styling */
        .stButton button {
            padding: 0.4rem 0.6rem !important;
            font-size: 0.85rem !important;
            border-radius: 6px !important;
            transition: all 0.2s ease !important;
            color: var(--text-color) !important;
        }
        
        .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3) !important;
        }
        
        /* Chat item styling - using columns */
        div[data-testid="column"] {
            padding: 0.15rem 0 !important;
        }
        
        /* Remove extra spacing between elements */
        div[data-testid="stHorizontalBlock"] {
            gap: 0.3rem !important;
            margin-bottom: 0.25rem !important;
        }
        
        /* Button text color fix for theme compatibility */
        .stButton button {
            color: var(--text-color) !important;
        }
        
        .stButton button:disabled {
            color: var(--secondary-text-color) !important;
            opacity: 0.5 !important;
        }
        
        /* Compact text input - theme adaptive */
        .stTextInput > div > div > input {
            padding: 0.35rem 0.5rem !important;
            font-size: 0.85rem !important;
            border-radius: 6px !important;
            background-color: var(--secondary-background-color) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-color) !important;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: var(--primary-color) !important;
            box-shadow: 0 0 0 1px var(--primary-color) !important;
        }
        
        /* Form styling */
        .stForm {
            background-color: transparent !important;
            border: none !important;
            padding: 0 !important;
        }
        
        /* Icon buttons - smaller and grouped */
        div[data-testid="column"] button {
            min-height: 32px !important;
            height: 32px !important;
            padding: 0.25rem 0.4rem !important;
            font-size: 0.9rem !important;
        }
        
        /* Primary button styling */
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            border: none !important;
            color: white !important;
        }
        
        .stButton button[kind="primary"]:hover {
            background: linear-gradient(135deg, #7b8ff5 0%, #8a5bb5 100%) !important;
        }
        
        /* Secondary button styling - theme adaptive */
        .stButton button[kind="secondary"] {
            background-color: var(--secondary-background-color) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-color) !important;
        }
        
        .stButton button[kind="secondary"]:hover {
            background-color: var(--background-color) !important;
            border-color: var(--primary-color) !important;
        }
        
        /* Divider styling - theme adaptive */
        hr {
            margin: 0.75rem 0 !important;
            border-color: var(--border-color) !important;
        }
        
        /* Footer styling - theme adaptive */
        .footer-info {
            font-size: 0.75rem;
            color: var(--secondary-text-color);
            text-align: center;
            padding: 0.5rem;
            background-color: var(--secondary-background-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-top: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-title">💬 Chat History</div>', unsafe_allow_html=True)
    
    # New Chat Button
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        create_new_chat()
        st.rerun()
    
    st.markdown("---")
    
    # Display all chats (sorted by creation time, newest first)
    sorted_chats = sorted(
        st.session_state.chats.items(), 
        key=lambda x: x[1]["created_at"], 
        reverse=True
    )
    
    for chat_id, chat_data in sorted_chats:
        is_active = chat_id == st.session_state.current_chat_id
        
        # Check if this chat is being edited
        if st.session_state.editing_chat_id == chat_id:
            col1, col2 = st.columns([4, 1])
            with col1:
                # Create a form to handle Enter key submission
                with st.form(key=f"form_{chat_id}", clear_on_submit=False):
                    new_title = st.text_input(
                        "Rename",
                        value=chat_data['title'],
                        key=f"rename_{chat_id}",
                        label_visibility="collapsed",
                        placeholder="Enter chat name..."
                    )
                    # Hidden submit button (triggered by Enter)
                    submitted = st.form_submit_button("💾", use_container_width=True)
                    
                    if submitted:
                        rename_chat(chat_id, new_title)
                        st.session_state.editing_chat_id = None
                        st.rerun()
            
            with col2:
                # Cancel button
                if st.button("✕", key=f"cancel_{chat_id}", help="Cancel", use_container_width=True):
                    st.session_state.editing_chat_id = None
                    st.rerun()
        else:
            col1, col2, col3 = st.columns([6, 1, 1])
            
            with col1:
                # Regular chat button
                button_label = f"{'📌 ' if is_active else '💬 '}{chat_data['title']}"
                if st.button(
                    button_label,
                    key=f"chat_{chat_id}",
                    use_container_width=True,
                    disabled=is_active
                ):
                    switch_chat(chat_id)
                    st.rerun()
            
            with col2:
                # Compact edit button
                if st.button("✏️", key=f"edit_{chat_id}", help="Rename", use_container_width=True):
                    st.session_state.editing_chat_id = chat_id
                    st.rerun()
            
            with col3:
                if len(st.session_state.chats) > 1:  # Don't allow deleting last chat
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Delete", use_container_width=True):
                        if st.session_state.editing_chat_id == chat_id:
                            st.session_state.editing_chat_id = None
                        delete_chat(chat_id)
                        st.rerun()
    
    # Footer section
    st.markdown("---")
    
    # Clear all history button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
            st.session_state.show_confirm = True
    
    if st.session_state.get('show_confirm', False):
        with col2:
            if st.button("✅ Confirm", use_container_width=True, type="primary", key="confirm_clear"):
                st.session_state.chats = {}
                clear_all_data_db()
                create_new_chat()
                st.session_state.show_confirm = False
                st.rerun()
    
    st.markdown(f"""
    <div class="footer-info">
        📊 {len(st.session_state.chats)} chat session(s)<br>
        💾 SQLite Auto-saved
    </div>
    """, unsafe_allow_html=True)

# ==========================================================
# HEADER
# ==========================================================
LOGO_URL = "https://media.licdn.com/dms/image/v2/C4E0BAQGtXskL4EvJmA/company-logo_200_200/company-logo_200_200/0/1632401962756/koantek_logo?e=2147483647&v=beta&t=D4GLT1Pu2vvxLR1iKZZbUJWN7K_uaPSF0T1mZl6Le-o"

current_chat = get_current_chat()

st.markdown(f"""
<style>
    .main-header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.25rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
        filter: brightness(1.1);
    }}
    
    .main-header h1 {{
        color: #ffffff !important;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }}
    
    .main-header p {{
        color: rgba(255,255,255,0.95) !important;
        font-size: 0.875rem;
        margin: 0.25rem 0 0 0;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }}
</style>

<div class="main-header">
    <div class="header-content">
        <h1>💬 {current_chat['title']}</h1>
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
    # Display all messages from current chat
    if not current_chat["messages"]:
        st.info("👋 Start a conversation by typing a message below!")
    else:
        for msg in current_chat["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Show thinking indicator if processing
    if st.session_state.awaiting_response:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                bot_response = chat_with_bot(current_chat["messages"])
        
        # Add response to current chat history
        current_chat["messages"].append({
            "role": "assistant",
            "content": bot_response
        })
        
        # Save to database
        save_message_to_db(st.session_state.current_chat_id, "assistant", bot_response)
        
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
    # Small clear button (clears current chat only)
    if st.button(
        "🗑️", 
        key="clear_chat_btn", 
        help="Clear current chat",
        type="secondary",
        disabled=len(current_chat["messages"]) == 0 or st.session_state.awaiting_response
    ):
        current_chat["messages"] = []
        current_chat["title"] = "New Chat"
        clear_chat_messages_db(st.session_state.current_chat_id)
        save_chat_to_db(
            st.session_state.current_chat_id,
            "New Chat",
            current_chat["created_at"],
            is_current=True
        )
        st.session_state.awaiting_response = False
        st.rerun()

# Handle message submission
if prompt:
    # Update chat title if this is the first message
    if len(current_chat["messages"]) == 0:
        update_chat_title(st.session_state.current_chat_id, prompt)
    
    # Add user message immediately
    current_chat["messages"].append({
        "role": "user",
        "content": prompt
    })
    
    # Save to database
    save_message_to_db(st.session_state.current_chat_id, "user", prompt)
    
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
    <p style="color: var(--secondary-text-color); margin: 0;">Powered by Koantek • Chat history stored in SQLite</p>
</div>
""", unsafe_allow_html=True)

########################################################################################

# import streamlit as st
# import requests
# import json

# # ==========================================================
# # PAGE CONFIG
# # ==========================================================
# st.set_page_config(
#     page_title="AI Chatbot",
#     page_icon="💬",
#     layout="wide"
# )

# # ==========================================================
# # CONFIGURATION
# # ==========================================================
# DATABRICKS_INSTANCE = st.secrets.get('DATABRICKS_INSTANCE')
# DATABRICKS_TOKEN = st.secrets.get('DB_token')
# NOTEBOOK_PATH = st.secrets.get('NOTEBOOK_PATH')
# VOLUME_PATH = st.secrets.get('VOLUME_PATH')
# CLUSTER_ID = st.secrets.get('CLUSTER_ID')
# CHATBOT_ENDPOINT=st.secrets.get('CHATBOT_ENDPOINT')
# # ==========================================================
# # INITIALIZE SESSION STATE
# # ==========================================================
# if 'chat_messages' not in st.session_state:
#     st.session_state.chat_messages = []
# if 'awaiting_response' not in st.session_state:
#     st.session_state.awaiting_response = False

# # ==========================================================
# # HELPER FUNCTION
# # ==========================================================
# def chat_with_bot(conversation_history):
#     """Send full conversation history to chatbot and get response - NO TRIMMING"""
#     if not all([DATABRICKS_TOKEN, CHATBOT_ENDPOINT]):
#         return "Error: Chatbot endpoint or token is not configured."
    
#     headers = {
#         "Authorization": f"Bearer {DATABRICKS_TOKEN}",
#         "Content-Type": "application/json"
#     }

#     # Build input array from conversation history
#     input_messages = []
#     for msg in conversation_history:
#         input_messages.append({
#             "status": None,
#             "content": msg["content"],
#             "role": msg["role"],
#             "type": "message"
#         })

#     payload = {
#         "input": input_messages
#     }

#     try:
#         response = requests.post(CHATBOT_ENDPOINT, headers=headers, json=payload, timeout=300)
#         if response.status_code != 200:
#             return f"Error: {response.status_code} - {response.text}"

#         texts = []
#         raw = response.text.strip()
        
#         # Handle NDJSON
#         if '\n' in raw:
#             for line in raw.splitlines():
#                 line = line.strip()
#                 if not line:
#                     continue
#                 try:
#                     data = json.loads(line)
#                     if data.get("type") == "response.output_item.done":
#                         item = data.get("item", {})
#                         for content in item.get("content", []):
#                             if content.get("type") == "output_text":
#                                 texts.append(content.get("text", ""))
#                 except json.JSONDecodeError:
#                     continue
#         else:
#             try:
#                 data = json.loads(raw)
#                 if isinstance(data, dict) and "output" in data:
#                     for msg in data["output"]:
#                         for content in msg.get("content", []):
#                             if content.get("type") == "output_text":
#                                 texts.append(content.get("text", ""))
#             except Exception:
#                 pass

#         # Return raw result - NO TRIMMING OR CLEANUP
#         result = "\n\n---\n\n".join(texts) if texts else "No response received. Check model/endpoint status."
#         return result

#     except Exception as e:
#         return f"Error: {str(e)}"

# # ==========================================================
# # HEADER
# # ==========================================================
# LOGO_URL = "https://media.licdn.com/dms/image/v2/C4E0BAQGtXskL4EvJmA/company-logo_200_200/company-logo_200_200/0/1632401962756/koantek_logo?e=2147483647&v=beta&t=D4GLT1Pu2vvxLR1iKZZbUJWN7K_uaPSF0T1mZl6Le-o"

# st.markdown(f"""
# <style>
#     .main-header {{
#         background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#         padding: 1.25rem 1.5rem;
#         border-radius: 10px;
#         margin-bottom: 1.25rem;
#         box-shadow: 0 2px 4px rgba(0,0,0,0.1);
#         display: flex;
#         justify-content: space-between;
#         align-items: center;
#     }}
    
#     .header-content {{
#         flex: 1;
#     }}
    
#     .header-logo {{
#         height: 60px;
#         width: auto;
#         max-width: 200px;
#         object-fit: contain;
#     }}
    
#     .main-header h1 {{
#         color: white;
#         font-size: 1.5rem;
#         font-weight: 700;
#         margin: 0;
#     }}
    
#     .main-header p {{
#         color: rgba(255,255,255,0.9);
#         font-size: 0.875rem;
#         margin: 0.25rem 0 0 0;
#     }}
    
#     /* Small clear button */
#     button[kind="secondary"] {{
#         padding: 0.5rem !important;
#         font-size: 1.2rem !important;
#     }}
# </style>

# <div class="main-header">
#     <div class="header-content">
#         <h1>💬 AI Chatbot</h1>
#         <p>Ask questions about your business data</p>
#     </div>
#     <img src="{LOGO_URL}" class="header-logo" alt="Koantek Logo" onerror="this.style.display='none'">
# </div>
# """, unsafe_allow_html=True)

# # ==========================================================
# # CHATBOT UI
# # ==========================================================

# # Scrollable chat container
# chat_container = st.container(height=500)

# with chat_container:
#     # Display all messages
#     if not st.session_state.chat_messages:
#         st.info("👋 Start a conversation by typing a message below!")
#     else:
#         for msg in st.session_state.chat_messages:
#             with st.chat_message(msg["role"]):
#                 st.markdown(msg["content"])
    
#     # Show thinking indicator if processing
#     if st.session_state.awaiting_response:
#         with st.chat_message("assistant"):
#             with st.spinner("Thinking..."):
#                 bot_response = chat_with_bot(st.session_state.chat_messages)
        
#         # Add response to history
#         st.session_state.chat_messages.append({
#             "role": "assistant",
#             "content": bot_response
#         })
#         st.session_state.awaiting_response = False
#         st.rerun()

# # Fixed input area at bottom
# col1, col2 = st.columns([9, 1])

# with col1:
#     # Chat input (handles Enter key automatically)
#     prompt = st.chat_input(
#         "Type your message here...", 
#         disabled=st.session_state.awaiting_response,
#         key="chat_input_main"
#     )

# with col2:
#     # Small clear button
#     if st.button(
#         "🗑️", 
#         key="clear_chat_btn", 
#         help="Clear chat history",
#         type="secondary",
#         disabled=len(st.session_state.chat_messages) == 0 or st.session_state.awaiting_response
#     ):
#         st.session_state.chat_messages = []
#         st.session_state.awaiting_response = False
#         st.rerun()

# # Handle message submission
# if prompt:
#     # Add user message immediately
#     st.session_state.chat_messages.append({
#         "role": "user",
#         "content": prompt
#     })
    
#     # Set flag for API call
#     st.session_state.awaiting_response = True
    
#     # Immediate rerun - shows user message instantly
#     st.rerun()

# # ==========================================================
# # FOOTER
# # ==========================================================
# st.markdown("---")
# st.markdown("""
# <div style="text-align: center; font-size: 0.8rem; padding: 0.75rem;">
#     <p style="color: #6b7280;">Powered by Koantek</p>
# </div>
# """, unsafe_allow_html=True)


