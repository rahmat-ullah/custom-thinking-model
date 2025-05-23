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
from voice_email_handler import VoiceEmailHandler # Add this import
import os # ensure os is imported

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
    st.session_state.voice_email_handler = None # Will be initialized once gmail_service is available
if "waiting_for_reply_body" not in st.session_state: # For multi-turn reply (voice)
   st.session_state.waiting_for_reply_body = False
if "waiting_for_text_reply_body" not in st.session_state: # For multi-turn reply (text)
    st.session_state.waiting_for_text_reply_body = False
if "selected_tts_voice" not in st.session_state: # For OpenAI TTS Voice Selection
    st.session_state.selected_tts_voice = "alloy" # Default voice


# --- AVAILABLE TTS VOICES ---
AVAILABLE_TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


# --- MODIFIED/NEW FUNCTIONS ---
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

    if st.session_state.talking_mode_enabled and called_from_voice:
        # Per issue: "In voice mode it shouldn't use thinking chat mode."
        # So, for non-email commands processed via voice, use DirectChat response.
        audio_utils.speak_text(direct_response, voice_id=st.session_state.selected_tts_voice)
    elif st.session_state.talking_mode_enabled and not called_from_voice:
        # This is for text input submitted while talking mode is on.
        # Original behavior was to speak both. Let's keep DirectChat for consistency in voice.
         audio_utils.speak_text(direct_response, voice_id=st.session_state.selected_tts_voice)

    st.session_state.user_input = ""


def process_voice_command(recognized_text: str):
    """Processes recognized speech: routes to email handler or general LLM."""
    text_lower = recognized_text.lower()
    handler = st.session_state.get("voice_email_handler")
    response_text = None
    email_command_handled = False

    WORD_TO_DIGIT = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
        "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10"
    }

    # Check if waiting for reply body
    if st.session_state.get("waiting_for_reply_body", False) and handler and handler.current_email_id:
        st.session_state.waiting_for_reply_body = False # Reset flag
        response_text = handler.prepare_reply_voice(recognized_text) # Entire input is reply body
        email_command_handled = True
    # Email-related command intent recognition
    elif handler: # Only if Gmail is connected and handler initialized
        if any(cmd in text_lower for cmd in ["read my unread email", "fetch unread email", "check my email", "get my unread email", "get my last email"]):
            max_results = 5 # Default
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
            if not identifier or not any(char.isdigit() for char in identifier): # if identifier is not primarily numeric
                if "subject" in identifier_part:
                     identifier = identifier_part.split("subject",1)[-1].strip()
                elif "from" in identifier_part:
                     identifier = identifier_part.split("from",1)[-1].strip()
                elif not identifier_part: # "read email" without anything after
                    identifier = "" # Will trigger the "Please specify" message

            if identifier:
                response_text = handler.read_email_voice(identifier) # identifier can be a number string or other text
            else:
                response_text = "Please specify which email to read, for example, 'read email number one' or 'read email from Jane'."
            email_command_handled = True
        elif "reply to this email" in text_lower or "reply email" in text_lower:
            if handler.current_email_id:
                response_text = "What would you like to say in your reply?"
                st.session_state.waiting_for_reply_body = True # Set flag
            else:
                response_text = "Please read an email first before replying."
            email_command_handled = True
        # No "send reply saying" - handled by waiting_for_reply_body state

    elif not handler and any(keyword in text_lower for keyword in ["email", "mail", "message", "inbox", "unread", "reply"]):
        # Email command attempted but Gmail not connected
        response_text = "To use email commands, please first connect to Gmail using the button in the user interface."
        email_command_handled = True # Handled by informing the user

    if email_command_handled:
        if response_text:
            audio_utils.speak_text(response_text, voice_id=st.session_state.selected_tts_voice)
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
        # Not an email command, or email command could not be fully processed by handler (e.g. bad parse)
        # Fallback to general LLM processing for voice.
        st.session_state.user_input = recognized_text # Show recognized text in input box
        process_general_llm_input(recognized_text, called_from_voice=True)

# --- Process Email Command Text Function ---
def process_email_command_text(text_input: str, handler: VoiceEmailHandler):
    """Processes text input for email commands."""
    text_lower = text_input.lower()
    response_text = None
    email_command_handled = False # Flag to indicate if an email command was recognized and acted upon

    WORD_TO_DIGIT = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
        "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10"
    }

    # Check if waiting for reply body (for text-based reply)
    # This check is actually done in handle_submit before calling this function.
    # Here, we focus on initial command processing.

    if any(cmd in text_lower for cmd in ["read my unread email", "fetch unread email", "check my email", "get my unread email", "get my last email"]):
        max_results = 5 # Default
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
        response_text = handler.fetch_unread_emails_voice(max_results=max_results) # Reuses voice method, which is fine as it returns text
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
            elif not identifier_part : # "read email" without anything after
                 identifier = "" 

        if identifier:
            response_text = handler.read_email_voice(identifier) # Reuses voice method
        else:
            response_text = "Please specify which email to read, for example, 'read email number one' or 'read email from Jane'."
        email_command_handled = True
    elif "reply to this email" in text_lower or "reply email" in text_lower:
        if handler.current_email_id:
            response_text = "What would you like to say in your reply? Please type your message."
            st.session_state.waiting_for_text_reply_body = True # Set flag for text reply
            # Unlike voice, we don't immediately expect the body. Text input will trigger next.
        else:
            response_text = "Please read an email first before replying via text."
        email_command_handled = True
    # No "send reply saying" for text - handled by waiting_for_text_reply_body state in handle_submit

    if email_command_handled:
        return response_text
    return None # Return None if no specific email command was handled by this function


def handle_mic_input(): # This is the main entry for voice
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
    user_text = st.session_state.user_input
    if not user_text:
        return

    handler = st.session_state.get("voice_email_handler")
    email_response_text = None
    email_command_processed_for_submit = False # Flag to skip general LLM if email handled

    if handler:
        # Check if waiting for the body of a text reply
        if st.session_state.get("waiting_for_text_reply_body", False) and handler.current_email_id:
            # User's current input is the reply body
            email_response_text = handler.prepare_reply_voice(user_text) # Re-use voice version, it just returns text
            st.session_state.waiting_for_text_reply_body = False # Reset flag
            email_command_processed_for_submit = True
        else:
            # Not waiting for a reply body, so try to process as a new email command
            # We can do a quick check for keywords to see if it *might* be an email command
            # before calling the full process_email_command_text.
            # This avoids calling it unnecessarily for every text input.
            email_keywords = ["email", "mail", "unread", "fetch", "read", "open", "reply", "inbox", "message"]
            if any(keyword in user_text.lower() for keyword in email_keywords):
                email_response_text = process_email_command_text(user_text, handler)
                if email_response_text:
                    email_command_processed_for_submit = True
        
        if email_command_processed_for_submit and email_response_text:
            # Display in DirectChat (or your chosen chat display)
            st.session_state.direct_chat.add_message("user", user_text)
            st.session_state.direct_chat.add_message("assistant", email_response_text)

            if st.session_state.talking_mode_enabled:
                audio_utils.speak_text(email_response_text, voice_id=st.session_state.selected_tts_voice)
            
            st.session_state.user_input = "" # Clear input box
            # Log this interaction if needed (similar to how process_voice_command logs)
            if config.ENABLE_LOGGING:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user_input (text_email)": user_text,
                    "handler_response": email_response_text,
                }
                current_logs = load_chat_history(config.LOG_FILE_PATH)
                current_logs.append(log_entry)
                save_chat_history(current_logs, config.LOG_FILE_PATH)
            st.rerun() # Rerun to update UI immediately
            return # Stop further processing

    # If not an email command handled by the above, or no handler, process as general input
    if not email_command_processed_for_submit:
        process_general_llm_input(user_text, called_from_voice=False) # called_from_voice=False for text input

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

# --- GMAIL INTEGRATION UI ---
st.markdown("---")
st.header("📧 Gmail Integration")

if not st.session_state.gmail_service:
    if st.button("🔗 Connect to Gmail"):
        try:
            st.session_state.gmail_service = email_utils.authenticate_gmail()
            if st.session_state.gmail_service:
                st.session_state.voice_email_handler = VoiceEmailHandler(st.session_state.gmail_service)
                st.success("Successfully connected to Gmail and voice email handler is ready!") # Update message
                st.rerun()
            else:
                st.error("Failed to connect to Gmail. Please check credentials.json and ensure you have authorized the app.")
        except FileNotFoundError:
            st.error(f"Error: The credentials file ({config.GMAIL_CREDENTIALS_PATH}) was not found. Please make sure it's in the correct location.")
        except Exception as e:
            st.error(f"An unexpected error occurred during Gmail authentication: {e}")
else: # Already connected
    st.success("✅ Connected to Gmail")
    if st.session_state.gmail_service and not st.session_state.voice_email_handler:
        st.session_state.voice_email_handler = VoiceEmailHandler(st.session_state.gmail_service)
        # Optionally add a silent confirmation or small note if handler had to be re-initialized
        print("VoiceEmailHandler re-initialized.")
    
    # --- Deprecated Email Search UI ---
    # The following UI elements for searching and displaying emails directly
    # have been deprecated in favor of voice/text commands.
    
    # search_query = st.text_input("Search query (e.g., from:sender@example.com is:unread)", key="gmail_search_query")
    # if st.button("🔍 Search Emails"):
    #     if st.session_state.gmail_service and search_query:
    #         try:
    #             st.session_state.emails_list = email_utils.list_emails(st.session_state.gmail_service, query=search_query, max_results=10)
    #             if st.session_state.emails_list is None: # list_emails returns None on error
    #                 st.warning("Could not retrieve emails. There might have been an API error or no emails matched your query.")
    #             elif not st.session_state.emails_list: # Empty list
    #                 st.info("No emails found matching your query.")
    #             st.session_state.selected_email = None # Reset selected email view
    #         except Exception as e:
    #             st.error(f"An error occurred while searching emails: {e}")
    #             st.session_state.emails_list = None
    #     elif not search_query:
    #         st.warning("Please enter a search query.")

    # # Display Emails if list exists
    # if st.session_state.emails_list:
    #     st.markdown(f"Found **{len(st.session_state.emails_list)}** emails:")
        
    #     # We'll display basic info and a button to read the full email.
    #     # To manage multiple "Read Email" buttons and their states, we'll update selected_email
    #     # when a button is clicked and then display that email.

    #     for index, email_item in enumerate(st.session_state.emails_list):
    #         try:
    #             # Fetch brief details (subject, from) for display in the list
    #             # Note: list_emails might not return full details like subject/sender directly.
    #             # For simplicity here, we'll try to get a summary.
    #             # A more robust way would be to fetch minimal headers in list_emails or do a quick get here.
                
    #             # For now, let's assume list_emails gives us enough to identify the email (like 'id')
    #             # and we'll fetch full details only when "Read Email" is clicked.
    #             # The current email_utils.list_emails returns a list of message objects which have an 'id'.
                
    #             # We need to fetch snippet or subject for display. Let's fetch the subject for each.
    #             # To avoid too many API calls, we'll first get the message object then extract subject
    #             # This is a bit inefficient here, ideally list_emails would give more info or we'd batch.
    #             # For now, let's just show ID and a button.
                
    #             msg_preview = st.session_state.gmail_service.users().messages().get(userId='me', id=email_item['id'], format='metadata', metadataHeaders=['Subject', 'From']).execute()
    #             subject_preview = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
    #             from_preview = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'From'), 'Unknown Sender')

    #             col_email, col_button = st.columns([4,1])
    #             with col_email:
    #                 st.markdown(f"**{subject_preview}** <br><small>From: {from_preview} (ID: {email_item['id']})</small>", unsafe_allow_html=True)
    #             with col_button:
    #                 if st.button(f"Read Email {index+1}", key=f"read_{email_item['id']}"):
    #                     st.session_state.selected_email_id = email_item['id'] # Store ID of email to read
    #                     # No need to call read_email here, will do it below based on selected_email_id
    #                     st.rerun() # Rerun to show the selected email

    #         except Exception as e:
    #             st.error(f"Error processing email preview for ID {email_item.get('id', 'N/A')}: {e}")


    # # Display Selected Email if an ID is set
    # if hasattr(st.session_state, 'selected_email_id') and st.session_state.selected_email_id:
    #     email_id_to_read = st.session_state.selected_email_id
    #     with st.expander(f"Email Content (ID: {email_id_to_read})", expanded=True):
    #         try:
    #             email_content = email_utils.read_email(st.session_state.gmail_service, email_id_to_read)
    #             if email_content:
    #                 st.markdown(f"**From:** {email_content['from']}")
    #                 st.markdown(f"**Subject:** {email_content['subject']}")
    #                 st.markdown("---")
    #                 st.markdown(email_content['body'], unsafe_allow_html=False) # Display body as Markdown
    #             else:
    #                 st.error("Could not read email content.")
    #         except Exception as e:
    #             st.error(f"An error occurred while reading email {email_id_to_read}: {e}")
    #         if st.button("Close Email", key=f"close_{email_id_to_read}"):
    #             st.session_state.selected_email_id = None
    #             st.rerun()


# --- END GMAIL INTEGRATION UI ---

if config.ENABLE_LOGGING:
    os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)