import streamlit as st
import os
import json
from datetime import datetime
from thinking_chat import ThinkingChat
from direct_chat import DirectChat
import config
from utils import save_chat_history, load_chat_history

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

# Function to handle the submit action
def handle_submit():
    user_input = st.session_state.user_input
    if user_input.strip():
        # Process the user input in both chats
        thinking_plan, thinking_response = st.session_state.thinking_chat.process_message(user_input)
        direct_response = st.session_state.direct_chat.process_message(user_input)
        
        # Log the conversation if enabled
        if config.ENABLE_LOGGING:
            # Ensure logs directory exists
            os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
            
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "thinking_plan": thinking_plan,
                "thinking_response": thinking_response,
                "direct_response": direct_response
            }
            
            # Save to log file
            current_logs = load_chat_history(config.LOG_FILE_PATH)
            current_logs.append(log_entry)
            save_chat_history(current_logs, config.LOG_FILE_PATH)
        
        # Clear the input
        st.session_state.user_input = ""

# Function to clear chat history
def clear_chats():
    st.session_state.thinking_chat.clear_messages()
    st.session_state.direct_chat.clear_messages()
    st.rerun()

# App title and description
st.title("🧠 LLM Dual Brain - Thinking vs Direct Chat")
st.markdown("""
This application demonstrates two different approaches to LLM interactions:
- **Thinking Chat**: The LLM first plans its approach before responding
- **Direct Chat**: The LLM responds directly without explicit planning
""")

# Create two columns for the chat interfaces
col1, col2 = st.columns(2)

# Thinking Chat column
with col1:
    st.header("🤔 Thinking Chat")
    
    # Display thinking chat messages
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

# Direct Chat column
with col2:
    st.header("💬 Direct Chat")
    
    # Display direct chat messages
    direct_messages = st.session_state.direct_chat.get_messages()
    direct_container = st.container(height=400, border=True)
    
    with direct_container:
        for message in direct_messages:
            if message["role"] == "user":
                st.markdown(f"**You**: {message['content']}")
            elif message["role"] == "assistant":
                st.markdown(f"**Assistant**: {message['content']}")

# User input area
st.text_input(
    "Enter your message:",
    key="user_input",
    on_change=handle_submit
)

# Control buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Clear Chats"):
        clear_chats()
with col2:
    if st.button("Download Chat History") and config.ENABLE_LOGGING:
        with open(config.LOG_FILE_PATH, "r") as f:
            chat_data = f.read()
        st.download_button(
            label="Download JSON",
            data=chat_data,
            file_name="chat_history.json",
            mime="application/json"
        )

# Display footer with info
st.markdown("---")
st.markdown("""
**Project Information:**
- Models used: Thinking Chat - {}, Direct Chat - {}
- Check logs at: {}
""".format(config.THINKING_MODEL, config.DIRECT_MODEL, config.LOG_FILE_PATH))

# Ensure logs directory exists
if config.ENABLE_LOGGING:
    os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True) 