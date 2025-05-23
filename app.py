import streamlit as st
import os
import json
from datetime import datetime
from thinking_chat import ThinkingChat
from direct_chat import DirectChat
import config
from utils import save_chat_history, load_chat_history
import audio_utils
import email_utils # Gmail integration
from outlook_utils import OutlookService # Outlook integration
from voice_email_handler import VoiceEmailHandler
import os

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
if "gmail_service" not in st.session_state: # Gmail service
    st.session_state.gmail_service = None
if "emails_list" not in st.session_state: # List of emails
    st.session_state.emails_list = None
if "selected_email" not in st.session_state: # Currently selected email to read
    st.session_state.selected_email = None
if "voice_email_handler" not in st.session_state:
    st.session_state.voice_email_handler = None
if "outlook_service" not in st.session_state: # Outlook service
    st.session_state.outlook_service = None
if "outlook_auth_flow_details" not in st.session_state: # For Outlook device flow
    st.session_state.outlook_auth_flow_details = None
if "outlook_auth_pending" not in st.session_state: # To manage Outlook auth button state
    st.session_state.outlook_auth_pending = False


if "waiting_for_reply_body" not in st.session_state: # For multi-turn reply (voice)
   st.session_state.waiting_for_reply_body = False
if "waiting_for_text_reply_body" not in st.session_state: # For multi-turn reply (text)
    st.session_state.waiting_for_text_reply_body = False
if "selected_tts_voice" not in st.session_state: # For OpenAI TTS Voice Selection
    st.session_state.selected_tts_voice = "alloy" # Default voice
if "continuous_listening_mode" not in st.session_state:
    st.session_state.continuous_listening_mode = False
if "needs_auto_listen" not in st.session_state:
    st.session_state.needs_auto_listen = False


# --- AVAILABLE TTS VOICES ---
AVAILABLE_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


# --- MODIFIED/NEW FUNCTIONS ---

# --- Auto-Listen Function ---
def trigger_auto_listen():
    """Handles the auto-listening sequence if conditions are met."""
    if not (st.session_state.get("talking_mode_enabled", False) and \
            st.session_state.get("continuous_listening_mode", False)):
        return

    st.sidebar.info("Auto-listening...")
    recognized_text = audio_utils.listen_to_user()
    st.sidebar.info("")  # Clear the listening message

    if recognized_text:
        st.session_state.user_input = recognized_text # Show what was heard
        # Directly process the command. process_voice_command will handle speaking
        # and then re-set needs_auto_listen if still applicable.
        process_voice_command(recognized_text)
    else:
        # If nothing was recognized, and we are in continuous mode,
        # we might want to immediately listen again or provide a silent cue.
        # For now, if nothing is heard, the chain stops unless an explicit action is taken.
        # Alternatively, to keep listening:
        # st.session_state.needs_auto_listen = True
        # st.rerun() # To make the script re-evaluate needs_auto_listen
        pass # Or, to re-trigger listening immediately:
             # if st.session_state.get("talking_mode_enabled", False) and \
             #    st.session_state.get("continuous_listening_mode", False):
             #    st.session_state.needs_auto_listen = True 
             #    # No rerun here, let the main script loop handle it to avoid deep recursion
    # No explicit st.rerun() here to avoid potential loops if not handled carefully.
    # process_voice_command should trigger reruns if it updates state/UI.

def process_general_llm_input(user_input_text: str, called_from_voice: bool):
    """Handles input for ThinkingChat and DirectChat, and TTS if applicable."""
    if not user_input_text.strip():
        return

    thinking_plan, thinking_response = st.session_state.thinking_chat.process_message(user_input_text)
    direct_response = st.session_state.direct_chat.process_message(user_input_text)

    if config.ENABLE_LOGGING:
        os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input_text,
            "thinking_plan": thinking_plan,
            "thinking_response": thinking_response,
            "direct_response": direct_response
        }
        current_logs = load_chat_history(config.LOG_FILE_PATH)
        current_logs.append(log_entry)
        save_chat_history(current_logs, config.LOG_FILE_PATH)

    speech_was_made = False
    if st.session_state.talking_mode_enabled and called_from_voice:
        # Per issue: "In voice mode it shouldn't use thinking chat mode."
        # So, for non-email commands processed via voice, use DirectChat response.
        audio_utils.speak_text(direct_response, voice_id=st.session_state.selected_tts_voice)
        speech_was_made = True
    elif st.session_state.talking_mode_enabled and not called_from_voice:
        # This is for text input submitted while talking mode is on.
        # Original behavior was to speak both. Let's keep DirectChat for consistency in voice.
         audio_utils.speak_text(direct_response, voice_id=st.session_state.selected_tts_voice)
         speech_was_made = True

    st.session_state.user_input = "" # Clear input after processing

    if speech_was_made and st.session_state.get("continuous_listening_mode", False):
        st.session_state.needs_auto_listen = True


def process_voice_command(recognized_text: str):
    """Processes recognized speech: routes to email handler or general LLM, or handles stop command."""
    text_lower = recognized_text.lower()
    
    # Check for stop listening commands first
    stop_phrases = ["stop listening", "exit continuous mode", "cancel continuous listening", "turn off continuous listening"]
    if any(phrase in text_lower for phrase in stop_phrases):
        if st.session_state.get("continuous_listening_mode", False):
            st.session_state.continuous_listening_mode = False
            st.session_state.needs_auto_listen = False 
            confirmation_message = "Continuous listening disabled."
            audio_utils.speak_text(confirmation_message, voice_id=st.session_state.get("selected_tts_voice", "alloy"))
            st.session_state.user_input = "" 
            st.session_state.direct_chat.add_message("user", recognized_text) 
            st.session_state.direct_chat.add_message("assistant", confirmation_message)
            st.rerun() 
            return 
        else:
            pass 

    handler = st.session_state.get("voice_email_handler")
    response_text = None
    email_command_handled = False
    active_service_name_for_voice_command = handler._get_active_service_name() if handler else "No service"


    WORD_TO_DIGIT = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
        "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10"
    }

    # Handle service switching commands first
    if "switch to gmail" in text_lower or "use gmail" in text_lower:
        if handler:
            response_text = handler.switch_email_service('gmail')
        else:
            response_text = "Email handler not initialized. Please connect to a service first."
        email_command_handled = True
    elif "switch to outlook" in text_lower or "use outlook" in text_lower:
        if handler:
            if st.session_state.get("outlook_service"):
                response_text = handler.switch_email_service('outlook')
            else:
                response_text = "Outlook service not connected. Please connect to Outlook first using the button."
        else:
            response_text = "Email handler not initialized. Please connect to a service first."
        email_command_handled = True
    # Check if waiting for reply body
    elif st.session_state.get("waiting_for_reply_body", False) and handler and handler.current_email_id:
        st.session_state.waiting_for_reply_body = False 
        response_text = handler.send_reply_voice(recognized_text) # Use send_reply_voice
        email_command_handled = True
    # Email-related command intent recognition
    elif handler and handler.active_service_client: # Check if a service is active in the handler
        if any(cmd in text_lower for cmd in ["read my unread email", "fetch unread email", "check my email", "get my unread email", "get my last email"]):
            max_results = 5 
            words = text_lower.split()
            for i, word in enumerate(words):
                if word.isdigit():
                    max_results = int(word)
                    break
                # Example: "get my last three emails" - check word before "email"
                if word in ["emails", "email"] and i > 0 and words[i-1].isdigit():
                    max_results = int(words[i-1])
                    break
                if word in ["emails", "email"] and i > 0 and words[i-1] in WORD_TO_DIGIT:
                    max_results = int(WORD_TO_DIGIT[words[i-1]])
                    break
            response_text = handler.fetch_unread_emails_voice(max_results=max_results)
            email_command_handled = True
        elif "read email" in text_lower or "open email" in text_lower:
            identifier_part = text_lower.split("read email", 1)[-1].strip() if "read email" in text_lower else text_lower.split("open email", 1)[-1].strip()
            
            identifier = None
            words = identifier_part.split()
            # Check for number words first (e.g., "read email one", "open the second email")
            # It will also catch "read email number one" if "number" is part of identifier_part
            processed_identifier_words = []
            found_num_word = False
            for word in words:
                if word in WORD_TO_DIGIT:
                    processed_identifier_words.append(WORD_TO_DIGIT[word])
                    found_num_word = True
                else:
                    processed_identifier_words.append(word)
            
            if found_num_word:
                 # Prefer the converted number word if it exists and is a simple number (e.g. "read email one")
                 # This helps distinguish "read email one" from "read email from One Two Three company"
                potential_num = "".join(filter(str.isdigit, "".join(processed_identifier_words)))
                if potential_num.isdigit() and len(potential_num) < 3 : # Avoid long accidental numbers from names
                    identifier = potential_num
            
            if not identifier: # If no number word was converted or it wasn't a simple number
                identifier = " ".join(processed_identifier_words) # Use the (potentially modified) full string

            # Fallback for "subject" or "from" if no numeric identifier was prioritized
            if not identifier or not any(char.isdigit() for char in identifier): 
                if "subject" in identifier_part:
                     identifier = identifier_part.split("subject",1)[-1].strip()
                elif "from" in identifier_part:
                     identifier = identifier_part.split("from",1)[-1].strip()
                elif not identifier_part: 
                    identifier = "" 

            if identifier:
                response_text = handler.read_email_voice(identifier) 
            else:
                response_text = f"Please specify which {active_service_name_for_voice_command} email to read, for example, 'read email number one' or 'read email from Jane'."
            email_command_handled = True
        elif "reply to this email" in text_lower or "reply email" in text_lower:
            if handler.current_email_id:
                response_text = f"What would you like to say in your reply using {active_service_name_for_voice_command}?"
                st.session_state.waiting_for_reply_body = True 
            else:
                response_text = f"Please read an {active_service_name_for_voice_command} email first before replying."
            email_command_handled = True
        # Add mark as read/unread commands
        elif "mark as read" in text_lower:
            identifier_part = text_lower.split("mark as read", 1)[-1].strip()
            if identifier_part:
                 response_text = handler.mark_email_as_read_voice(identifier_part)
            else:
                 response_text = "Please specify which email to mark as read."
            email_command_handled = True
        elif "mark as unread" in text_lower:
            identifier_part = text_lower.split("mark as unread", 1)[-1].strip()
            if identifier_part:
                 response_text = handler.mark_email_as_unread_voice(identifier_part)
            else:
                 response_text = "Please specify which email to mark as unread."
            email_command_handled = True


    elif not handler and any(keyword in text_lower for keyword in ["email", "mail", "message", "inbox", "unread", "reply", "outlook", "gmail"]):
        response_text = "To use email commands, please first connect to an email service using the buttons in the sidebar."
        email_command_handled = True 
    elif handler and not handler.active_service_client and any(keyword in text_lower for keyword in ["email", "mail", "message", "inbox", "unread", "reply"]):
        response_text = "No email service is currently active. You can say 'switch to Gmail' or 'switch to Outlook' if they are connected."
        email_command_handled = True


    speech_was_made_by_email_handler = False
    if email_command_handled:
        if response_text:
            audio_utils.speak_text(response_text, voice_id=st.session_state.selected_tts_voice)
            speech_was_made_by_email_handler = True
        # Log this interaction
        if config.ENABLE_LOGGING and recognized_text and response_text : # ensure values exist
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_input (voice_email)": recognized_text,
                "handler_response": response_text,
            }
            current_logs = load_chat_history(config.LOG_FILE_PATH)
            current_logs.append(log_entry)
            save_chat_history(current_logs, config.LOG_FILE_PATH)
    else:
        # Not an email command, or email command could not be fully processed by handler
        # Fallback to general LLM processing for voice.
        st.session_state.user_input = recognized_text 
        process_general_llm_input(recognized_text, called_from_voice=True) 
    
    if speech_was_made_by_email_handler and \
       st.session_state.get("talking_mode_enabled", False) and \
       st.session_state.get("continuous_listening_mode", False) and \
       not st.session_state.get("waiting_for_reply_body", False): # Don't auto-listen if waiting for reply
        st.session_state.needs_auto_listen = True


# --- Process Email Command Text Function ---
def process_email_command_text(text_input: str, handler: VoiceEmailHandler):
    """Processes text input for email commands."""
    text_lower = text_input.lower()
    response_text = None
    email_command_handled = False 
    active_service_name_for_text = handler._get_active_service_name() if handler else "No service"

    WORD_TO_DIGIT = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
        "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10"
    }
    
    # Service switching via text
    if "switch to gmail" in text_lower or "use gmail" in text_lower:
        if handler:
            response_text = handler.switch_email_service('gmail')
        else:
            response_text = "Email handler not initialized."
        email_command_handled = True
    elif "switch to outlook" in text_lower or "use outlook" in text_lower:
        if handler:
            if st.session_state.get("outlook_service"):
                response_text = handler.switch_email_service('outlook')
            else:
                response_text = "Outlook service not connected. Please connect to Outlook first."
        else:
            response_text = "Email handler not initialized."
        email_command_handled = True
    # Existing email commands, now checking handler.active_service_client
    elif handler and handler.active_service_client:
        if any(cmd in text_lower for cmd in ["read my unread email", "fetch unread email", "check my email", "get my unread email", "get my last email"]):
            max_results = 5 
            words = text_lower.split()
            for i, word in enumerate(words):
                if word.isdigit():
                    max_results = int(word)
                    break
                if word in ["emails", "email"] and i > 0 and words[i-1].isdigit():
                    max_results = int(words[i-1])
                    break
                if word in ["emails", "email"] and i > 0 and words[i-1] in WORD_TO_DIGIT:
                    max_results = int(WORD_TO_DIGIT[words[i-1]])
                    break
            response_text = handler.fetch_unread_emails_voice(max_results=max_results) 
            email_command_handled = True
        elif "read email" in text_lower or "open email" in text_lower:
            identifier_part = text_lower.split("read email", 1)[-1].strip() if "read email" in text_lower else text_lower.split("open email", 1)[-1].strip()
            identifier = None
            words = identifier_part.split()
        processed_identifier_words = []
        found_num_word = False
        for word in words:
            if word in WORD_TO_DIGIT:
                processed_identifier_words.append(WORD_TO_DIGIT[word])
                found_num_word = True
            else:
                processed_identifier_words.append(word)
        
        if found_num_word:
            potential_num = "".join(filter(str.isdigit, "".join(processed_identifier_words)))
            if potential_num.isdigit() and len(potential_num) < 3:
                identifier = potential_num
        
            if not identifier:
                identifier = " ".join(processed_identifier_words)

            if not identifier or not any(char.isdigit() for char in identifier):
                if "subject" in identifier_part:
                     identifier = identifier_part.split("subject",1)[-1].strip()
                elif "from" in identifier_part:
                     identifier = identifier_part.split("from",1)[-1].strip()
                elif not identifier_part : 
                     identifier = "" 

            if identifier:
                response_text = handler.read_email_voice(identifier) 
            else:
                response_text = f"Please specify which {active_service_name_for_text} email to read, for example, 'read email number one' or 'read email from Jane'."
            email_command_handled = True
        elif "reply to this email" in text_lower or "reply email" in text_lower:
            if handler.current_email_id:
                response_text = f"What would you like to say in your reply using {active_service_name_for_text}? Please type your message."
                st.session_state.waiting_for_text_reply_body = True 
            else:
                response_text = f"Please read an {active_service_name_for_text} email first before replying via text."
            email_command_handled = True
        elif "mark as read" in text_lower:
            identifier_part = text_lower.split("mark as read", 1)[-1].strip()
            if identifier_part: response_text = handler.mark_email_as_read_voice(identifier_part)
            else: response_text = "Please specify which email to mark as read."
            email_command_handled = True
        elif "mark as unread" in text_lower:
            identifier_part = text_lower.split("mark as unread", 1)[-1].strip()
            if identifier_part: response_text = handler.mark_email_as_unread_voice(identifier_part)
            else: response_text = "Please specify which email to mark as unread."
            email_command_handled = True
    elif not handler and any(keyword in text_lower for keyword in ["email", "mail", "outlook", "gmail"]): # No handler, but email keyword
        response_text = "Email services are not yet initialized. Please connect to Gmail or Outlook first."
        email_command_handled = True
    elif handler and not handler.active_service_client and any(keyword in text_lower for keyword in ["email", "mail"]): # Handler exists, but no active service
        response_text = "No email service is currently active. You can say 'switch to Gmail' or 'switch to Outlook' if they are connected."
        email_command_handled = True


    if email_command_handled:
        return response_text
    return None 


def handle_mic_input(): 
    # Clicking the "Speak" button explicitly disables continuous listening for this interaction
    if st.session_state.get("continuous_listening_mode", False):
        st.session_state.continuous_listening_mode = False
        st.session_state.needs_auto_listen = False 
        # Optionally, inform the user that continuous mode was stopped by this action.
        # For now, it's an implicit stop. The checkbox will update on rerun.
        
    st.sidebar.info("Listening...")
    recognized_text = audio_utils.listen_to_user()
    st.sidebar.info("") # Clear "Listening..."
    if recognized_text:
        st.session_state.user_input = recognized_text # Show what was heard
        if st.session_state.talking_mode_enabled:
            process_voice_command(recognized_text) # New central voice processing
        # If not talking mode, text just stays in user_input for manual submission
    else:
        st.sidebar.warning("No speech detected or recognized.")
    st.rerun()


def handle_submit(): # This is for text based submission
    user_text = st.session_state.user_input # Capture before it's potentially cleared
    
    if user_text and st.session_state.get("continuous_listening_mode", False):
        st.session_state.continuous_listening_mode = False
        st.session_state.needs_auto_listen = False
        print("Continuous listening disabled due to typing and submitting text.") 
        
    if not user_text: 
        return

    handler = st.session_state.get("voice_email_handler")
    email_response_text = None
    email_command_processed_for_submit = False 

    if handler:
        active_service_name_for_text_submit = handler._get_active_service_name()
        if st.session_state.get("waiting_for_text_reply_body", False) and handler.current_email_id:
            email_response_text = handler.send_reply_voice(user_text) # Use send_reply_voice
            st.session_state.waiting_for_text_reply_body = False 
            email_command_processed_for_submit = True
        else:
            email_keywords = ["email", "mail", "unread", "fetch", "read", "open", "reply", "inbox", "message", "outlook", "gmail", "switch"]
            if any(keyword in user_text.lower() for keyword in email_keywords):
                email_response_text = process_email_command_text(user_text, handler)
                if email_response_text: # If it was an email command (even if it's "service not active")
                    email_command_processed_for_submit = True 
        
        if email_command_processed_for_submit and email_response_text:
            st.session_state.direct_chat.add_message("user", user_text)
            st.session_state.direct_chat.add_message("assistant", email_response_text)
            speech_was_made_in_submit = False
            if st.session_state.talking_mode_enabled:
                # Avoid speaking if it was just a "what's my reply?" prompt for text.
                if not st.session_state.get("waiting_for_text_reply_body", False): # Check if we just SET the waiting flag
                    audio_utils.speak_text(email_response_text, voice_id=st.session_state.selected_tts_voice)
                    speech_was_made_in_submit = True
            
            st.session_state.user_input = "" 
            if speech_was_made_in_submit and \
               st.session_state.get("continuous_listening_mode", False) and \
               not st.session_state.get("waiting_for_text_reply_body", False): # Don't auto-listen if now waiting for text reply
                st.session_state.needs_auto_listen = True
            
            if config.ENABLE_LOGGING:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user_input (text_email)": user_text,
                    "handler_response": email_response_text,
                }
                current_logs = load_chat_history(config.LOG_FILE_PATH)
                current_logs.append(log_entry)
                save_chat_history(current_logs, config.LOG_FILE_PATH)
            st.rerun() 
            return 

    if not email_command_processed_for_submit:
        process_general_llm_input(user_text, called_from_voice=False) 

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
    st.sidebar.caption("Note: The assistant's voice is AI-generated.") # AI Voice Disclosure
    
    # Voice Selection UI
    st.sidebar.selectbox(
        "Choose Assistant Voice:",
        options=AVAILABLE_TTS_VOICES,
        key="selected_tts_voice" # This directly updates st.session_state.selected_tts_voice
    )

    st.sidebar.checkbox(
        "Enable Continuous Listening",
        key="continuous_listening_mode", # This binds it to the session state
        help="When enabled, the assistant will automatically listen for your next command after speaking."
    )

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

# --- Main script logic for auto-listening ---
if st.session_state.get("needs_auto_listen", False):
    if not st.session_state.get("waiting_for_reply_body", False) and \
       not st.session_state.get("waiting_for_text_reply_body", False) and \
       not st.session_state.get("outlook_auth_pending", False): # Don't auto-listen if pending Outlook auth
        
        st.session_state.needs_auto_listen = False 
        trigger_auto_listen()
    else:
        st.session_state.needs_auto_listen = False

# --- EMAIL INTEGRATION UI ---
st.sidebar.markdown("---")
st.sidebar.header("📧 Email Services")

# Function to initialize or update VoiceEmailHandler
def initialize_voice_email_handler():
    gmail_s = st.session_state.get("gmail_service")
    outlook_s = st.session_state.get("outlook_service")
    
    current_handler = st.session_state.get("voice_email_handler")
    initial_type = 'gmail' # Default
    if current_handler and current_handler.active_service_type:
        initial_type = current_handler.active_service_type # Preserve current active if handler exists
    elif outlook_s and not gmail_s : # If only outlook is connected initially
        initial_type = 'outlook'

    st.session_state.voice_email_handler = VoiceEmailHandler(
        gmail_service=gmail_s,
        outlook_service=outlook_s,
        initial_service_type=initial_type
    )
    print(f"VoiceEmailHandler initialized/updated. Gmail: {'Connected' if gmail_s else 'Not'}, Outlook: {'Connected' if outlook_s else 'Not'}. Active: {st.session_state.voice_email_handler.active_service_type}")


# Gmail Connection
if not st.session_state.get("gmail_service"):
    if st.sidebar.button("🔗 Connect to Gmail"):
        try:
            st.session_state.gmail_service = email_utils.authenticate_gmail()
            if st.session_state.gmail_service:
                initialize_voice_email_handler()
                st.sidebar.success("Gmail connected!")
                st.rerun()
            else:
                st.sidebar.error("Gmail connection failed.")
        except FileNotFoundError:
            st.sidebar.error(f"Gmail credentials not found at {config.GMAIL_CREDENTIALS_PATH}")
        except Exception as e:
            st.sidebar.error(f"Gmail auth error: {str(e)[:100]}...") # Show first 100 chars
else:
    st.sidebar.success("✅ Gmail Connected")
    if st.sidebar.button("Log Out Gmail"):
        st.session_state.gmail_service = None
        # Remove token.json to force re-authentication next time
        if os.path.exists(config.GMAIL_TOKEN_PATH):
            os.remove(config.GMAIL_TOKEN_PATH)
        initialize_voice_email_handler() # Re-initialize handler with gmail_service as None
        st.rerun()


# Outlook Connection
if not st.session_state.get("outlook_service"):
    if st.sidebar.button("🔗 Connect to Outlook", key="connect_outlook_btn"):
        st.session_state.outlook_auth_pending = True
        try:
            # Instantiate service - this will start auth flow and store details if device flow
            temp_outlook_service = OutlookService(
                client_id=config.OUTLOOK_CLIENT_ID, 
                client_secret=config.OUTLOOK_CLIENT_SECRET, # May not be used for public client
                tenant_id=config.OUTLOOK_TENANT_ID
            )
            if hasattr(temp_outlook_service, 'last_device_flow_details') and temp_outlook_service.last_device_flow_details:
                st.session_state.outlook_auth_flow_details = temp_outlook_service.last_device_flow_details
                # The service instance itself isn't fully authenticated yet if device flow is incomplete.
                # We store the temporary service instance to call acquire_token_by_device_flow later.
                # However, OutlookService's _auth_flow is currently blocking.
                # For now, if it returns, it means it's either authenticated or failed.
                if temp_outlook_service.graph_client:
                    st.session_state.outlook_service = temp_outlook_service
                    initialize_voice_email_handler()
                    st.session_state.outlook_auth_pending = False
                    st.session_state.outlook_auth_flow_details = None # Clear flow details
                    st.sidebar.success("Outlook connected!")
                    st.rerun()
                else: # Auth failed within OutlookService constructor
                    st.session_state.outlook_auth_pending = False
                    st.sidebar.error("Outlook connection failed during authentication.")
            elif temp_outlook_service.graph_client: # For non-device flows or if auth completed quickly
                 st.session_state.outlook_service = temp_outlook_service
                 initialize_voice_email_handler()
                 st.session_state.outlook_auth_pending = False
                 st.sidebar.success("Outlook connected!")
                 st.rerun()
            else: # Should not happen if auth_flow is blocking and fails - it should raise exception
                st.session_state.outlook_auth_pending = False
                st.sidebar.error("Outlook connection attempt did not result in an authenticated client or device flow details.")

        except Exception as e:
            st.session_state.outlook_auth_pending = False
            st.sidebar.error(f"Outlook auth error: {str(e)[:100]}...")
            # Clear any partial auth details
            st.session_state.outlook_auth_flow_details = None


    if st.session_state.get("outlook_auth_flow_details"):
        flow_info = st.session_state.outlook_auth_flow_details
        st.sidebar.info(
            f"To complete Outlook authentication, please go to: \n[{flow_info['verification_uri']}]({flow_info['verification_uri']}) \n"
            f"And enter code: **{flow_info['user_code']}**"
        )
        st.sidebar.warning("The application will be blocked until authentication is complete or times out.")
        # In a real web app, we'd avoid blocking the whole app here.
        # Since OutlookService's _auth_flow is currently blocking, the app effectively waits there.
        # If _auth_flow was non-blocking up to acquire_token_by_device_flow, we'd need a "I have authenticated" button.

else: # Outlook service exists
    st.sidebar.success("✅ Outlook Connected")
    if st.sidebar.button("Log Out Outlook"):
        st.session_state.outlook_service = None
        st.session_state.outlook_auth_flow_details = None
        st.session_state.outlook_auth_pending = False
        # For MSAL, token caching is usually handled by MSAL itself.
        # To force re-auth, clearing the MSAL token cache would be needed.
        # This is complex as it's internal to MSAL. Simplest is to restart app or re-auth.
        # For device flow, re-initiating often works.
        initialize_voice_email_handler() # Re-initialize handler
        st.rerun()

# Initialize VoiceEmailHandler if services are available but handler is not yet set
# (e.g. after initial app load if one service was already connected via cached tokens)
if not st.session_state.get("voice_email_handler") and \
   (st.session_state.get("gmail_service") or st.session_state.get("outlook_service")):
    initialize_voice_email_handler()

# Display current active service if handler is available
if st.session_state.get("voice_email_handler") and st.session_state.voice_email_handler.active_service_type:
    active_service_display_name = st.session_state.voice_email_handler._get_active_service_name()
    st.sidebar.caption(f"🗣️ Active for voice/text commands: **{active_service_display_name}**")
elif st.session_state.get("voice_email_handler"):
    st.sidebar.caption("🗣️ Voice/text: No email service active.")


# --- Deprecated Email Search UI ---
# The following UI elements for searching and displaying emails directly
    # have been deprecated in favor of voice/text commands. These are commented out.

# --- END EMAIL INTEGRATION UI ---

if config.ENABLE_LOGGING:
    os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)