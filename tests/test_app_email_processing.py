import unittest
from unittest.mock import patch, MagicMock, ANY

# Add the project root to the Python path to allow importing app
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions to be tested from app.py
from app import process_voice_command, process_email_command_text, handle_submit 

# Mock streamlit before it's imported by app
# This is a common pattern for testing Streamlit apps
mock_st = MagicMock()
sys.modules['streamlit'] = mock_st
sys.modules['audio_utils'] = MagicMock()
sys.modules['email_utils'] = MagicMock()
sys.modules['config'] = MagicMock() 
sys.modules['config'].ENABLE_LOGGING = False # Disable logging for tests

# Mock the DirectChat and ThinkingChat if they are globally initialized or accessed
# For now, we'll mock them where they are used if possible, or globally if app.py structure requires
sys.modules['direct_chat'] = MagicMock()
sys.modules['thinking_chat'] = MagicMock()


class TestEmailProcessing(unittest.TestCase):

    def setUp(self):
        # Reset mocks and session_state for each test
        mock_st.reset_mock()
        
        # Mock st.session_state as a dictionary
        self.mock_session_state = {}
        mock_st.session_state = self.mock_session_state
        
        # Mock VoiceEmailHandler
        self.mock_voice_email_handler = MagicMock()
        self.mock_voice_email_handler.current_email_id = None # Default
        self.mock_session_state['voice_email_handler'] = self.mock_voice_email_handler
        
        # Mock DirectChat instance if accessed via session_state or globally
        self.mock_direct_chat_instance = MagicMock()
        # If DirectChat is instantiated in app.py like st.session_state.direct_chat = DirectChat()
        # we need to ensure that st.session_state.direct_chat points to our mock
        self.mock_session_state['direct_chat'] = self.mock_direct_chat_instance

        # Mock audio_utils specifically for speak_text
        self.mock_audio_utils_speak_text = MagicMock()
        audio_utils_module = sys.modules['audio_utils']
        audio_utils_module.speak_text = self.mock_audio_utils_speak_text

        # Default states
        self.mock_session_state['talking_mode_enabled'] = False
        self.mock_session_state['waiting_for_reply_body'] = False # For voice
        self.mock_session_state['waiting_for_text_reply_body'] = False # For text
        self.mock_session_state['user_input'] = ""


    # --- Tests for process_voice_command ---

    def test_pvc_fetch_unread_default_max_results(self):
        process_voice_command("fetch unread email")
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=5)
        self.mock_audio_utils_speak_text.assert_called_with(self.mock_voice_email_handler.fetch_unread_emails_voice.return_value)

    def test_pvc_fetch_unread_with_number(self):
        process_voice_command("fetch 7 unread emails")
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=7)

    def test_pvc_fetch_unread_with_number_word(self):
        process_voice_command("get my last three emails")
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=3)

    def test_pvc_fetch_unread_with_number_word_in_phrase(self):
        process_voice_command("check my email and get the last one") # "one" should be parsed
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=1)

    def test_pvc_read_email_by_number(self):
        process_voice_command("read email number 2")
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("2")
        self.mock_audio_utils_speak_text.assert_called_with(self.mock_voice_email_handler.read_email_voice.return_value)

    def test_pvc_read_email_by_number_word_first(self):
        process_voice_command("read the first email")
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("1")
        
    def test_pvc_read_email_by_number_word_three(self):
        # Test "open email three" to ensure "open" synonym and number word "three" work
        process_voice_command("open email three")
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("3")

    def test_pvc_read_email_by_subject(self):
        process_voice_command("read email with subject meeting notes")
        # Current logic: identifier_part.split("subject",1)[-1].strip()
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("meeting notes")

    def test_pvc_read_email_by_sender(self):
        process_voice_command("read email from John Doe")
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("John Doe")

    def test_pvc_read_email_empty_identifier(self):
        # "read email" without specifying which one
        process_voice_command("read email")
        self.mock_voice_email_handler.read_email_voice.assert_not_called() # Should not call if identifier is empty after parsing attempts
        self.mock_audio_utils_speak_text.assert_called_with("Please specify which email to read, for example, 'read email number one' or 'read email from Jane'.")
        
    def test_pvc_reply_initiates_waiting_for_reply_body(self):
        self.mock_voice_email_handler.current_email_id = "email123"
        process_voice_command("reply to this email")
        self.assertTrue(self.mock_session_state['waiting_for_reply_body'])
        self.mock_audio_utils_speak_text.assert_called_with("What would you like to say in your reply?")

    def test_pvc_reply_body_processed(self):
        self.mock_session_state['waiting_for_reply_body'] = True
        self.mock_voice_email_handler.current_email_id = "email123"
        self.mock_voice_email_handler.prepare_reply_voice.return_value = "Reply sent."
        
        process_voice_command("This is my reply message.")
        
        self.assertFalse(self.mock_session_state['waiting_for_reply_body'])
        self.mock_voice_email_handler.prepare_reply_voice.assert_called_once_with("This is my reply message.")
        self.mock_audio_utils_speak_text.assert_called_with("Reply sent.")

    @patch('app.process_general_llm_input')
    def test_pvc_no_handler_email_command_calls_general_llm(self, mock_process_general_llm_input):
        self.mock_session_state['voice_email_handler'] = None
        recognized_text = "check my email"
        process_voice_command(recognized_text)
        # It should inform the user that Gmail is not connected if it detects email keywords without a handler
        self.mock_audio_utils_speak_text.assert_called_once_with("To use email commands, please first connect to Gmail using the button in the user interface.")
        mock_process_general_llm_input.assert_not_called() # Specific handling for this case

    @patch('app.process_general_llm_input')
    def test_pvc_non_email_command_calls_general_llm(self, mock_process_general_llm_input):
        recognized_text = "what is the weather today"
        process_voice_command(recognized_text)
        mock_process_general_llm_input.assert_called_once_with(recognized_text, called_from_voice=True)
        self.assertEqual(self.mock_session_state['user_input'], recognized_text)


    # --- Tests for process_email_command_text ---

    def test_pect_fetch_unread_default_max_results(self):
        self.mock_voice_email_handler.fetch_unread_emails_voice.return_value = "5 emails fetched."
        response = process_email_command_text("fetch unread email", self.mock_voice_email_handler)
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=5)
        self.assertEqual(response, "5 emails fetched.")

    def test_pect_fetch_unread_with_number(self):
        self.mock_voice_email_handler.fetch_unread_emails_voice.return_value = "7 emails fetched."
        response = process_email_command_text("fetch 7 unread emails", self.mock_voice_email_handler)
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=7)
        self.assertEqual(response, "7 emails fetched.")

    def test_pect_fetch_unread_with_number_word(self):
        self.mock_voice_email_handler.fetch_unread_emails_voice.return_value = "Three emails fetched."
        response = process_email_command_text("get my last three emails", self.mock_voice_email_handler)
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=3)
        self.assertEqual(response, "Three emails fetched.")

    def test_pect_read_email_by_number(self):
        self.mock_voice_email_handler.read_email_voice.return_value = "Email content for 2."
        response = process_email_command_text("read email 2", self.mock_voice_email_handler)
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("2")
        self.assertEqual(response, "Email content for 2.")

    def test_pect_read_email_by_number_word(self):
        self.mock_voice_email_handler.read_email_voice.return_value = "Email content for first."
        response = process_email_command_text("read the first email", self.mock_voice_email_handler)
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("1") 
        self.assertEqual(response, "Email content for first.")

    def test_pect_read_email_by_subject(self):
        self.mock_voice_email_handler.read_email_voice.return_value = "Email content for meeting notes."
        response = process_email_command_text("read email with subject meeting notes", self.mock_voice_email_handler)
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("meeting notes")
        self.assertEqual(response, "Email content for meeting notes.")

    def test_pect_read_email_by_sender(self):
        self.mock_voice_email_handler.read_email_voice.return_value = "Email content from John Doe."
        response = process_email_command_text("read email from John Doe", self.mock_voice_email_handler)
        self.mock_voice_email_handler.read_email_voice.assert_called_once_with("John Doe")
        self.assertEqual(response, "Email content from John Doe.")
        
    def test_pect_read_email_empty_identifier(self):
        response = process_email_command_text("read email", self.mock_voice_email_handler)
        self.mock_voice_email_handler.read_email_voice.assert_not_called()
        self.assertEqual(response, "Please specify which email to read, for example, 'read email number one' or 'read email from Jane'.")

    def test_pect_reply_initiates_waiting_for_text_reply_body(self):
        self.mock_voice_email_handler.current_email_id = "email456"
        response = process_email_command_text("reply to this email", self.mock_voice_email_handler)
        self.assertTrue(self.mock_session_state['waiting_for_text_reply_body'])
        self.assertEqual(response, "What would you like to say in your reply? Please type your message.")
        
    def test_pect_reply_no_current_email(self):
        self.mock_voice_email_handler.current_email_id = None # No email selected/read
        response = process_email_command_text("reply email", self.mock_voice_email_handler)
        self.assertFalse(self.mock_session_state['waiting_for_text_reply_body'])
        self.assertEqual(response, "Please read an email first before replying via text.")

    def test_pect_no_handler_returns_none(self):
        response = process_email_command_text("some random text", None) # No handler
        self.assertIsNone(response)

    def test_pect_non_email_command_returns_none(self):
        response = process_email_command_text("this is not an email command", self.mock_voice_email_handler)
        self.assertIsNone(response)
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_not_called()
        self.mock_voice_email_handler.read_email_voice.assert_not_called()


    # --- Tests for handle_submit ---
    @patch('app.process_general_llm_input') 
    def test_hs_email_command_fetch(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "fetch 10 unread emails"
        self.mock_voice_email_handler.fetch_unread_emails_voice.return_value = "Fetched 10 emails."
        
        handle_submit()
        
        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=10)
        self.mock_direct_chat_instance.add_message.assert_any_call("user", "fetch 10 unread emails")
        self.mock_direct_chat_instance.add_message.assert_any_call("assistant", "Fetched 10 emails.")
        self.assertEqual(self.mock_session_state['user_input'], "") 
        mock_process_general_llm_input.assert_not_called()
        mock_st.rerun.assert_called_once()


    @patch('app.process_general_llm_input')
    def test_hs_email_command_fetch_with_talking_mode(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "fetch unread emails"
        self.mock_session_state['talking_mode_enabled'] = True
        self.mock_voice_email_handler.fetch_unread_emails_voice.return_value = "Fetched emails."

        handle_submit()

        self.mock_voice_email_handler.fetch_unread_emails_voice.assert_called_once_with(max_results=5)
        self.mock_direct_chat_instance.add_message.assert_any_call("user", "fetch unread emails")
        self.mock_direct_chat_instance.add_message.assert_any_call("assistant", "Fetched emails.")
        self.mock_audio_utils_speak_text.assert_called_once_with("Fetched emails.")
        mock_process_general_llm_input.assert_not_called()
        mock_st.rerun.assert_called_once()

    @patch('app.process_general_llm_input')
    def test_hs_text_reply_body_processing(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "This is my detailed reply."
        self.mock_session_state['waiting_for_text_reply_body'] = True
        self.mock_voice_email_handler.current_email_id = "email789"
        self.mock_voice_email_handler.prepare_reply_voice.return_value = "Text reply sent successfully."

        handle_submit()

        self.mock_voice_email_handler.prepare_reply_voice.assert_called_once_with("This is my detailed reply.")
        self.assertFalse(self.mock_session_state['waiting_for_text_reply_body'])
        self.mock_direct_chat_instance.add_message.assert_any_call("user", "This is my detailed reply.")
        self.mock_direct_chat_instance.add_message.assert_any_call("assistant", "Text reply sent successfully.")
        mock_process_general_llm_input.assert_not_called()
        mock_st.rerun.assert_called_once()

    @patch('app.process_general_llm_input')
    def test_hs_text_reply_body_with_talking_mode(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "Okay, send it."
        self.mock_session_state['waiting_for_text_reply_body'] = True
        self.mock_session_state['talking_mode_enabled'] = True
        self.mock_voice_email_handler.current_email_id = "email789"
        self.mock_voice_email_handler.prepare_reply_voice.return_value = "Message sent."

        handle_submit()
        self.mock_audio_utils_speak_text.assert_called_once_with("Message sent.")
        mock_process_general_llm_input.assert_not_called()

    @patch('app.process_general_llm_input')
    def test_hs_non_email_command_falls_through(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "Tell me a joke."
        
        handle_submit() 

        mock_process_general_llm_input.assert_called_once_with("Tell me a joke.", called_from_voice=False)
        self.mock_direct_chat_instance.add_message.assert_not_called() 
        self.mock_audio_utils_speak_text.assert_not_called()


    @patch('app.process_general_llm_input')
    def test_hs_no_input_does_nothing(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "" # Blank input
        handle_submit()
        mock_process_general_llm_input.assert_not_called()
        self.mock_direct_chat_instance.add_message.assert_not_called()
        mock_st.rerun.assert_not_called() 

    @patch('app.process_general_llm_input')
    def test_hs_email_command_no_handler(self, mock_process_general_llm_input):
        self.mock_session_state['user_input'] = "fetch my emails"
        self.mock_session_state['voice_email_handler'] = None # No handler
        
        handle_submit()
        
        mock_process_general_llm_input.assert_called_once_with("fetch my emails", called_from_voice=False)
        self.mock_direct_chat_instance.add_message.assert_not_called()


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
