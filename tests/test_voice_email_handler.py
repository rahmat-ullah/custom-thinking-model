import unittest
from unittest.mock import MagicMock, patch, call
import logging

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice_email_handler import VoiceEmailHandler
from googleapiclient.errors import HttpError # For Gmail specific error testing

# Mock classes similar to those in voice_email_handler.py's __main__
class MockEmailAddress:
    def __init__(self, name, address): self.name = name; self.address = address

class MockGmailService:
    def users(self): return self
    def messages(self): return self
    def get(self, userId, id, format, metadataHeaders):
        # This mock needs to be callable and then have an execute method
        mock_executable = MagicMock()
        if id == 'gmail_id_1':
            mock_executable.execute.return_value = {'payload': {'headers': [{'name': 'Subject', 'value': 'Gmail Subject 1'}, {'name': 'From', 'value': 'sender1@gmail.com'}]}}
        elif id == 'gmail_id_2':
            mock_executable.execute.return_value = {'payload': {'headers': [{'name': 'Subject', 'value': 'Gmail Subject 2'}, {'name': 'From', 'value': 'sender2@gmail.com'}]}}
        else:
            mock_executable.execute.return_value = {'payload': {'headers': [{'name': 'Subject', 'value': 'Unknown Subject'}, {'name': 'From', 'value': 'unknown@gmail.com'}]}}
        return mock_executable

    def list_emails_proxy(self, query, max_results):
        logging.debug(f"MOCK GMAIL list_emails_proxy called with query='{query}', max_results={max_results}")
        if query == "is:unread_error":
            raise HttpError(resp=MagicMock(status=500), content=b"Gmail API Error")
        if query == "is:unread_empty":
            return []
        return [{'id': 'gmail_id_1'}, {'id': 'gmail_id_2'}]

    def read_email_proxy(self, msg_id):
        logging.debug(f"MOCK GMAIL read_email_proxy called with msg_id='{msg_id}'")
        if msg_id == "gmail_id_error":
            raise HttpError(resp=MagicMock(status=404), content=b"Not Found")
        if msg_id == "gmail_id_1":
            return {'id': 'gmail_id_1', 'subject': 'Gmail Subject 1', 'sender': 'sender1@gmail.com', 'body': 'Body of Gmail 1'}
        return None

    def reply_to_email_proxy(self, msg_id, text):
        logging.debug(f"MOCK GMAIL reply_to_email_proxy called for msg_id='{msg_id}' with text='{text}'")
        if msg_id == "gmail_id_fail_reply":
            return None # Simulate failure
        return {'id': 'sent_reply_gmail_id'}

    def mark_email_as_read_proxy(self, msg_id):
        logging.debug(f"MOCK GMAIL mark_as_read_proxy called for msg_id='{msg_id}'")
        if msg_id == "gmail_id_fail_mark": return False
        return True

    def mark_email_as_unread_proxy(self, msg_id):
        logging.debug(f"MOCK GMAIL mark_as_unread_proxy called for msg_id='{msg_id}'")
        if msg_id == "gmail_id_fail_mark": return False
        return True

class MockOutlookService:
    def list_emails(self, unread_only=False, count=5):
        logging.debug(f"MOCK OUTLOOK list_emails called with unread_only={unread_only}, count={count}")
        if unread_only == "error": # Special case for testing error
            raise Exception("Outlook API Error")
        if unread_only == "empty":
            return []
            
        class Sender:
            def __init__(self, name, address): self.email_address = MockEmailAddress(name, address)
        class Message:
            def __init__(self, id_val, subject_val, sender_name, sender_addr, body_preview_val="Outlook preview", is_read=False):
                self.id = id_val; self.subject = subject_val; self.sender = Sender(sender_name, sender_addr)
                self.body_preview = body_preview_val; self.is_read = is_read
        return [
            Message("outlook_id_1", "Outlook Subject 1", "Sender1", "s1@outlook.com", "Preview 1"),
            Message("outlook_id_2", "Outlook Subject 2", "Sender2", "s2@outlook.com", "Preview 2")
        ]

    def read_email(self, message_id):
        logging.debug(f"MOCK OUTLOOK read_email called for msg_id='{message_id}'")
        if message_id == "outlook_id_error":
            raise Exception("Outlook Read Error")
        if message_id == "outlook_id_1":
            return {'id': 'outlook_id_1', 'subject': 'Outlook Subject 1', 'sender': 'Sender1 <s1@outlook.com>', 'body': 'Body of Outlook 1', 'body_type': 'HTML'}
        return None

    def reply_to_email(self, message_id, text):
        logging.debug(f"MOCK OUTLOOK reply_to_email called for msg_id='{message_id}' with text='{text}'")
        if message_id == "outlook_id_fail_reply": return False
        return True

    def mark_email_as_read(self, message_id):
        logging.debug(f"MOCK OUTLOOK mark_as_read called for msg_id='{message_id}'")
        if message_id == "outlook_id_fail_mark": return False
        return True

    def mark_email_as_unread(self, message_id):
        logging.debug(f"MOCK OUTLOOK mark_as_unread called for msg_id='{message_id}'")
        if message_id == "outlook_id_fail_mark": return False
        return True

# Patch email_utils at the class level or module level if all tests use it.
# Patching where it's looked up: 'voice_email_handler.email_utils'
@patch.multiple('voice_email_handler.email_utils',
                list_emails=MagicMock(),
                read_email=MagicMock(),
                reply_to_email=MagicMock(),
                mark_email_as_read=MagicMock(),
                mark_email_as_unread=MagicMock())
class TestVoiceEmailHandlerDualService(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=logging.DEBUG) # Enable logging for test debugging
        self.mock_gmail_service_instance = MockGmailService()
        self.mock_outlook_service_instance = MockOutlookService()

        # Point the patched email_utils functions to methods on our mock_gmail_service_instance
        # This makes VoiceEmailHandler call our mock methods when it uses email_utils.some_function(self.active_service_client,...)
        # and self.active_service_client is the gmail_service_instance.
        voice_email_handler.email_utils.list_emails.side_effect = self.mock_gmail_service_instance.list_emails_proxy
        voice_email_handler.email_utils.read_email.side_effect = self.mock_gmail_service_instance.read_email_proxy
        voice_email_handler.email_utils.reply_to_email.side_effect = self.mock_gmail_service_instance.reply_to_email_proxy
        voice_email_handler.email_utils.mark_email_as_read.side_effect = self.mock_gmail_service_instance.mark_email_as_read_proxy
        voice_email_handler.email_utils.mark_email_as_unread.side_effect = self.mock_gmail_service_instance.mark_email_as_unread_proxy
        
        # HttpError mock for Gmail
        self.mock_http_error_response = MagicMock(spec=HttpError) # More specific mock
        self.mock_http_error_response.status = 500 # Default
        self.mock_http_error_response.resp = self.mock_http_error_response # HttpError expects 'resp' to have status

        # Initialize handler, default to Gmail
        self.handler = VoiceEmailHandler(
            gmail_service=self.mock_gmail_service_instance,
            outlook_service=self.mock_outlook_service_instance,
            initial_service_type='gmail'
        )
        self.assertEqual(self.handler.active_service_type, 'gmail')

    def tearDown(self):
        # Reset mocks for other tests if necessary, especially if patchers are started in setUp
        # For @patch.multiple at class level, this is handled automatically.
        pass

    # --- Initialization Tests ---
    def test_init_default_gmail(self):
        handler = VoiceEmailHandler(gmail_service=self.mock_gmail_service_instance, outlook_service=self.mock_outlook_service_instance)
        self.assertEqual(handler.active_service_type, 'gmail')
        self.assertEqual(handler.active_service_client, self.mock_gmail_service_instance)

    def test_init_outlook_explicit(self):
        handler = VoiceEmailHandler(gmail_service=self.mock_gmail_service_instance, outlook_service=self.mock_outlook_service_instance, initial_service_type='outlook')
        self.assertEqual(handler.active_service_type, 'outlook')
        self.assertEqual(handler.active_service_client, self.mock_outlook_service_instance)

    def test_init_only_outlook_provided(self):
        handler = VoiceEmailHandler(outlook_service=self.mock_outlook_service_instance)
        self.assertEqual(handler.active_service_type, 'outlook')
        self.assertEqual(handler.active_service_client, self.mock_outlook_service_instance)

    def test_init_only_gmail_provided_outlook_requested(self):
        # If outlook requested but not provided, should fall back to gmail if available
        handler = VoiceEmailHandler(gmail_service=self.mock_gmail_service_instance, initial_service_type='outlook')
        self.assertEqual(handler.active_service_type, 'gmail')
        self.assertEqual(handler.active_service_client, self.mock_gmail_service_instance)

    def test_init_no_services(self):
        handler = VoiceEmailHandler()
        self.assertIsNone(handler.active_service_type)
        self.assertIsNone(handler.active_service_client)

    # --- Service Switching Tests ---
    def test_switch_service_to_outlook(self):
        self.handler.listed_emails = ["dummy_email"] # To check context clearing
        self.handler.current_email_id = "dummy_id"
        
        response = self.handler.switch_email_service('outlook')
        self.assertEqual(response, "Switched to Outlook.")
        self.assertEqual(self.handler.active_service_type, 'outlook')
        self.assertEqual(self.handler.active_service_client, self.mock_outlook_service_instance)
        self.assertEqual(self.handler.listed_emails, [])
        self.assertIsNone(self.handler.current_email_id)

    def test_switch_service_to_gmail(self):
        self.handler.switch_email_service('outlook') # Start with Outlook
        self.handler.listed_emails = ["dummy_email"]
        self.handler.current_email_id = "dummy_id"

        response = self.handler.switch_email_service('gmail')
        self.assertEqual(response, "Switched to Gmail.")
        self.assertEqual(self.handler.active_service_type, 'gmail')
        self.assertEqual(self.handler.active_service_client, self.mock_gmail_service_instance)
        self.assertEqual(self.handler.listed_emails, [])
        self.assertIsNone(self.handler.current_email_id)

    def test_switch_to_unavailable_service(self):
        handler_no_outlook = VoiceEmailHandler(gmail_service=self.mock_gmail_service_instance)
        response = handler_no_outlook.switch_email_service('outlook')
        self.assertEqual(response, "Outlook service is not configured. Cannot switch.")
        self.assertEqual(handler_no_outlook.active_service_type, 'gmail') # Should remain on previous

    # --- Fetch Unread Emails (Gmail - adapting existing) ---
    def test_fetch_unread_emails_gmail_success(self):
        # Ensure Gmail is active
        self.handler.switch_email_service('gmail')
        
        # Mocking the .users().messages().get().execute() chain for Gmail
        # This needs to be done on the actual mock_gmail_service_instance
        # because the handler uses self.active_service_client directly for this part.
        mock_execute = MagicMock()
        mock_execute.side_effect = [
            {'payload': {'headers': [{'name': 'Subject', 'value': 'Gmail Subject 1'}, {'name': 'From', 'value': 'sender1@gmail.com'}]}},
            {'payload': {'headers': [{'name': 'Subject', 'value': 'Gmail Subject 2'}, {'name': 'From', 'value': 'sender2@gmail.com'}]}}
        ]
        self.mock_gmail_service_instance.users().messages().get.return_value = mock_execute

        response = self.handler.fetch_unread_emails_voice(max_results=2)
        
        self.assertIn("I found 2 unread emails in Gmail.", response)
        self.assertIn("Subject: Gmail Subject 1, From: sender1@gmail.com", response)
        voice_email_handler.email_utils.list_emails.assert_called_with(self.mock_gmail_service_instance, query="is:unread", max_results=2)
        self.assertEqual(self.mock_gmail_service_instance.users().messages().get.call_count, 2)


    # --- Fetch Unread Emails (Outlook - New) ---
    def test_fetch_unread_emails_outlook_success(self):
        self.handler.switch_email_service('outlook')
        self.mock_outlook_service_instance.list_emails = MagicMock(return_value=[
            MagicMock(id='o1', subject='Outlook Subj1', sender=MagicMock(email_address=MagicMock(name='O Sender1', address='os1@test.com')), body_preview='Prev1'),
            MagicMock(id='o2', subject='Outlook Subj2', sender=MagicMock(email_address=MagicMock(name='O Sender2', address='os2@test.com')), body_preview='Prev2')
        ])
        response = self.handler.fetch_unread_emails_voice(max_results=2)
        self.assertIn("I found 2 unread emails in Outlook.", response)
        self.assertIn("Subject: Outlook Subj1, From: O Sender1", response)
        self.mock_outlook_service_instance.list_emails.assert_called_once_with(unread_only=True, count=2)
        self.assertEqual(len(self.handler.listed_emails), 2)
        self.assertEqual(self.handler.listed_emails[0]['subject'], 'Outlook Subj1')

    def test_fetch_unread_emails_outlook_no_emails(self):
        self.handler.switch_email_service('outlook')
        self.mock_outlook_service_instance.list_emails = MagicMock(return_value=[])
        response = self.handler.fetch_unread_emails_voice()
        self.assertEqual(response, "You have no unread emails in your Outlook account.")

    def test_fetch_unread_emails_outlook_api_error(self):
        self.handler.switch_email_service('outlook')
        self.mock_outlook_service_instance.list_emails = MagicMock(side_effect=Exception("Outlook API Error"))
        response = self.handler.fetch_unread_emails_voice()
        self.assertIn("Sorry, an unexpected error occurred with Outlook", response)

    # --- Read Email (Gmail - adapting existing) ---
    def test_read_email_gmail_success(self):
        self.handler.switch_email_service('gmail')
        self.handler.listed_emails = [{'id': 'gmail_id_1', 'subject': 'Gmail Subject 1', 'from': 'sender1@gmail.com', 'number': 1}]
        
        response = self.handler.read_email_voice("1")
        self.assertIn("Reading email from Gmail. From: sender1@gmail.com. Subject: Gmail Subject 1. Body: Body of Gmail 1", response)
        self.assertEqual(self.handler.current_email_id, 'gmail_id_1')
        voice_email_handler.email_utils.read_email.assert_called_with(self.mock_gmail_service_instance, 'gmail_id_1')
        voice_email_handler.email_utils.mark_email_as_read.assert_called_with(self.mock_gmail_service_instance, 'gmail_id_1')

    # --- Read Email (Outlook - New) ---
    def test_read_email_outlook_success(self):
        self.handler.switch_email_service('outlook')
        self.handler.listed_emails = [{'id': 'outlook_id_1', 'subject': 'Outlook Subject 1', 'from': 'Sender1 <s1@outlook.com>', 'number': 1}]
        self.mock_outlook_service_instance.read_email = MagicMock(return_value=
            {'id': 'outlook_id_1', 'subject': 'Outlook Subject 1', 'sender': 'Sender1 <s1@outlook.com>', 'body': 'Body of Outlook 1', 'body_type': 'HTML'}
        )
        self.mock_outlook_service_instance.mark_email_as_read = MagicMock(return_value=True)

        response = self.handler.read_email_voice("1")
        self.assertIn("Reading email from Outlook. From: Sender1 <s1@outlook.com>. Subject: Outlook Subject 1. Body: Body of Outlook 1", response)
        self.assertEqual(self.handler.current_email_id, 'outlook_id_1')
        self.mock_outlook_service_instance.read_email.assert_called_once_with('outlook_id_1')
        self.mock_outlook_service_instance.mark_email_as_read.assert_called_once_with('outlook_id_1')
        self.assertEqual(self.handler.current_email_content['sender'], 'Sender1 <s1@outlook.com>')


    # --- Send Reply (Gmail - adapting) ---
    # Original test was test_prepare_reply_voice_success, renamed to test_send_reply_voice_gmail_success
    def test_send_reply_voice_gmail_success(self):
        self.handler.switch_email_service('gmail')
        self.handler.current_email_id = 'gmail_id_1'
        self.handler.current_email_content = {'id': 'gmail_id_1', 'subject': 'Gmail Subject 1', 'sender': 'sender1@gmail.com', 'body': 'Original body.'}
        
        response = self.handler.send_reply_voice("This is my Gmail reply.")
        self.assertIn("Okay, I've sent your reply via Gmail to sender1@gmail.com about 'Gmail Subject 1'.", response)
        voice_email_handler.email_utils.reply_to_email.assert_called_with(self.mock_gmail_service_instance, 'gmail_id_1', "This is my Gmail reply.")

    # --- Send Reply (Outlook - New) ---
    def test_send_reply_voice_outlook_success(self):
        self.handler.switch_email_service('outlook')
        self.handler.current_email_id = 'outlook_id_1'
        self.handler.current_email_content = {'id': 'outlook_id_1', 'subject': 'Outlook Subject 1', 'sender': 'Sender1 <s1@outlook.com>', 'body': 'Original body.'}
        self.mock_outlook_service_instance.reply_to_email = MagicMock(return_value=True)

        response = self.handler.send_reply_voice("This is my Outlook reply.")
        self.assertIn("Okay, I've sent your reply via Outlook to Sender1 <s1@outlook.com> about 'Outlook Subject 1'.", response)
        self.mock_outlook_service_instance.reply_to_email.assert_called_once_with('outlook_id_1', "This is my Outlook reply.")

    # --- Mark as Read/Unread (Adding Outlook and ensuring Gmail uses mocks) ---
    def test_mark_as_read_gmail(self):
        self.handler.switch_email_service('gmail')
        self.handler.listed_emails = [{'id': 'gmail_id_1', 'subject': 'Test', 'from': 'test@g.com', 'number': 1}]
        response = self.handler.mark_email_as_read_voice("1")
        self.assertIn("marked as read using Gmail", response)
        voice_email_handler.email_utils.mark_email_as_read.assert_called_with(self.mock_gmail_service_instance, 'gmail_id_1')

    def test_mark_as_read_outlook(self):
        self.handler.switch_email_service('outlook')
        self.handler.listed_emails = [{'id': 'outlook_id_1', 'subject': 'Test', 'from': 'test@o.com', 'number': 1}]
        response = self.handler.mark_email_as_read_voice("1")
        self.assertIn("marked as read using Outlook", response)
        self.mock_outlook_service_instance.mark_email_as_read.assert_called_once_with('outlook_id_1')
        
    # ... similar tests for mark_as_unread for both services ...

    # --- Error Handling tests for active service ---
    def test_read_email_voice_active_service_error_gmail(self):
        self.handler.switch_email_service('gmail')
        self.handler.listed_emails = [{'id': 'gmail_id_error', 'subject': 'Error Email', 'from': 'err@example.com', 'number': 1}]
        # Mock HttpError for Gmail
        self.mock_http_error_response.status = 404
        voice_email_handler.email_utils.read_email.side_effect = HttpError(resp=self.mock_http_error_response, content=b'Not Found')
        
        response = self.handler.read_email_voice("1")
        self.assertIn("Email ID gmail_id_error not found in Gmail.", response)

    def test_read_email_voice_active_service_error_outlook(self):
        self.handler.switch_email_service('outlook')
        self.handler.listed_emails = [{'id': 'outlook_id_error', 'subject': 'Error Email', 'from': 'err@example.com', 'number': 1}]
        self.mock_outlook_service_instance.read_email = MagicMock(side_effect=Exception("Outlook Read Error"))
        
        response = self.handler.read_email_voice("1")
        self.assertIn("Unexpected error with Outlook while reading. Details: Outlook Read Error", response)

if __name__ == '__main__':
    unittest.main() # No need for argv or exit=False for standard test runs
