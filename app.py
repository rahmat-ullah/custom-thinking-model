import streamlit as st
import os
import json
from datetime import datetime
from thinking_chat import ThinkingChat
from direct_chat import DirectChat
import config
from utils import save_chat_history, load_chat_history
import audio_utils # New import

# Set page configuration
st.set_page_config(
    page_title="LLM Dual Brain - Thinking vs Direct Chat",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state
if "thinking_chat" not in st.session_state:
    st.session_state.thinking_chat = ThinkingChat()
if "direct_chat" not in st.session_state:
    st.session_state.direct_chat = DirectChat()
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "talking_mode_enabled" not in st.session_state: # New session state
    st.session_state.talking_mode_enabled = False

# --- MODIFIED/NEW FUNCTIONS ---
def process_input_for_llm(user_input_text: str):
    if user_input_text.strip():
        # Process the user input in both chats
        thinking_plan, thinking_response = st.session_state.thinking_chat.process_message(user_input_text)
        direct_response = st.session_state.direct_chat.process_message(user_input_text)
        
        # Log the conversation
        if config.ENABLE_LOGGING:
            # Ensure logs directory exists
            os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
            
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input_text, # Use the passed argument
                "thinking_plan": thinking_plan,
                "thinking_response": thinking_response,
                "direct_response": direct_response
            }
            
            # Save to log file
            current_logs = load_chat_history(config.LOG_FILE_PATH)
            current_logs.append(log_entry)
            save_chat_history(current_logs, config.LOG_FILE_PATH)

        # Speak responses if talking mode is enabled
        if st.session_state.talking_mode_enabled:
            print("Attempting to speak thinking_response...") 
            audio_utils.speak_text(f"Thinking Chat says: {thinking_response}")
            print("Attempting to speak direct_response...")
            audio_utils.speak_text(f"Direct Chat says: {direct_response}")
            
        st.session_state.user_input = "" 

def handle_submit(): 
    process_input_for_llm(st.session_state.user_input)

def handle_mic_input(): 
    st.sidebar.info("Listening...") 
    recognized_text = audio_utils.listen_to_user()
    if recognized_text:
        st.session_state.user_input = recognized_text 
        process_input_for_llm(recognized_text) 
    else:
        st.sidebar.warning("No speech detected or recognized.")
    st.rerun() 

def clear_chats():
    st.session_state.thinking_chat.clear_messages()
    st.session_state.direct_chat.clear_messages()
    st.rerun()

st.title("🧠 LLM Dual Brain - Thinking vs Direct Chat")
st.markdown("""
This application demonstrates two different approaches to LLM interactions:
- **Thinking Chat**: The LLM first plans its approach before responding
- **Direct Chat**: The LLM responds directly without explicit planning
""")

st.sidebar.header("Talking Mode")
st.session_state.talking_mode_enabled = st.sidebar.checkbox(
    "Enable Talking Mode", 
    value=st.session_state.get("talking_mode_enabled", False) 
)

if st.session_state.talking_mode_enabled:
    if st.sidebar.button("🎤 Speak"):
        handle_mic_input()
    st.sidebar.caption("Click 'Speak' then talk. Your message will appear in the input box below and be processed.")

col1, col2 = st.columns(2)

with col1:
    st.header("🤔 Thinking Chat")
    thinking_messages = st.session_state.thinking_chat.get_messages()
    thinking_container = st.container(height=400, border=True)
    with thinking_container:
        for message in thinking_messages:
            if message["role"] == "user":
                st.markdown(f"**You**: {message['content']}")
            elif message["role"] == "system":
                with st.expander("Show Thinking Process"):
                    st.markdown(f"**System Thinking**: {message['content']}")
            elif message["role"] == "assistant":
                st.markdown(f"**Assistant**: {message['content']}")
with col2:
    st.header("💬 Direct Chat")
    direct_messages = st.session_state.direct_chat.get_messages()
    direct_container = st.container(height=400, border=True)
    with direct_container:
        for message in direct_messages:
            if message["role"] == "user":
                st.markdown(f"**You**: {message['content']}")
            elif message["role"] == "assistant":
                st.markdown(f"**Assistant**: {message['content']}")
st.text_input(
    "Enter your message:",
    key="user_input",
    on_change=handle_submit 
)

col_buttons1, col_buttons2 = st.columns(2)
with col_buttons1:
    if st.button("Clear Chats"):
        clear_chats()
with col_buttons2:
    if st.button("Download Chat History") and config.ENABLE_LOGGING:
        if os.path.exists(config.LOG_FILE_PATH):
            with open(config.LOG_FILE_PATH, "r") as f:
                chat_data = f.read()
            st.download_button(
                label="Download JSON",
                data=chat_data,
                file_name="chat_history.json",
                mime="application/json"
            )
        else:
            st.error("Log file not found. Please send a message first to create it.")
st.markdown("---")
st.markdown("""
**Project Information:**
- Models used: Thinking Chat - {}, Direct Chat - {}
- Check logs at: {}
""".format(config.THINKING_MODEL, config.DIRECT_MODEL, config.LOG_FILE_PATH))

if config.ENABLE_LOGGING:
    os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)