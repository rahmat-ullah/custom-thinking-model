import unittest
from unittest.mock import MagicMock, patch

# To allow importing voice_email_handler from the parent directory if tests is a subdir
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice_email_handler import VoiceEmailHandler 
from googleapiclient.errors import HttpError 

# Mock the email_utils module that voice_email_handler imports
# This assumes email_utils.py is in the same directory as voice_email_handler.py (e.g., project root)
# If patching specific functions, ensure the patch path is where it's looked up (e.g., 'voice_email_handler.email_utils.list_emails')

class TestVoiceEmailHandler(unittest.TestCase):

    def setUp(self):
        self.mock_gmail_service = MagicMock()
        # Mock the HttpError response structure needed for testing
        self.mock_http_error_response = MagicMock()
        self.mock_http_error_response.status = 0 # Default, override in tests
        
        self.handler = VoiceEmailHandler(self.mock_gmail_service)

    @patch('voice_email_handler.email_utils.list_emails') # Patched where it's used
    def test_fetch_unread_emails_voice_success(self, mock_list_emails):
        # Arrange
        mock_message_ids = [{'id': '123'}, {'id': '456'}]
        mock_list_emails.return_value = mock_message_ids
        
        mock_msg_preview_1 = {
            'payload': {'headers': [{'name': 'Subject', 'value': 'Hello'}, {'name': 'From', 'value': 'sender1@example.com'}]}
        }
        mock_msg_preview_2 = {
            'payload': {'headers': [{'name': 'Subject', 'value': 'Meeting'}, {'name': 'From', 'value': 'sender2@example.com'}]}
        }
        # This simulates the chained calls: service.users().messages().get()
        self.mock_gmail_service.users().messages().get.return_value.execute.side_effect = [mock_msg_preview_1, mock_msg_preview_2]

        # Act
        response = self.handler.fetch_unread_emails_voice(max_results=2)

        # Assert
        self.assertIn("I found 2 unread emails.", response)
        self.assertIn("Subject: Hello, From: sender1@example.com", response)
        self.assertIn("Subject: Meeting, From: sender2@example.com", response)
        self.assertEqual(len(self.handler.listed_emails), 2)
        self.assertEqual(self.handler.listed_emails[0]['subject'], 'Hello')
        mock_list_emails.assert_called_once_with(self.mock_gmail_service, query="is:unread", max_results=2)

    @patch('voice_email_handler.email_utils.list_emails')
    def test_fetch_unread_emails_voice_no_emails(self, mock_list_emails):
        mock_list_emails.return_value = []
        response = self.handler.fetch_unread_emails_voice()
        self.assertEqual(response, "You have no unread emails.")

    @patch('voice_email_handler.email_utils.list_emails')
    def test_fetch_unread_emails_voice_list_error(self, mock_list_emails):
        mock_list_emails.return_value = None 
        response = self.handler.fetch_unread_emails_voice()
        self.assertEqual(response, "Sorry, I couldn't retrieve your unread emails at the moment.")

    @patch('voice_email_handler.email_utils.list_emails')
    def test_fetch_unread_emails_voice_http_error_401(self, mock_list_emails):
        self.mock_http_error_response.status = 401
        # The HttpError needs 'content' as bytes, and 'resp' should be the mock_http_error_response itself.
        mock_list_emails.side_effect = HttpError(resp=self.mock_http_error_response, content=b'Auth error details')
        response = self.handler.fetch_unread_emails_voice()
        self.assertEqual(response, "There's an issue with Gmail authentication. Please try reconnecting to Gmail via the user interface.")
        
    @patch('voice_email_handler.email_utils.read_email')
    @patch('voice_email_handler.email_utils.mark_email_as_read')
    def test_read_email_voice_by_number_success(self, mock_mark_as_read, mock_read_email):
        self.handler.listed_emails = [
            {'id': '123', 'subject': 'Hello', 'from': 'sender1@example.com', 'number': 1},
            {'id': '456', 'subject': 'Meeting', 'from': 'sender2@example.com', 'number': 2}
        ]
        mock_email_content = {'id': '123', 'subject': 'Hello', 'from': 'sender1@example.com', 'body': 'Email body content.'}
        mock_read_email.return_value = mock_email_content

        response = self.handler.read_email_voice("1") 

        self.assertIn("Reading email from sender1@example.com. Subject: Hello. Body: Email body content.", response)
        self.assertEqual(self.handler.current_email_id, '123')
        self.assertEqual(self.handler.current_email_content, mock_email_content)
        mock_read_email.assert_called_once_with(self.mock_gmail_service, '123')
        mock_mark_as_read.assert_called_once_with(self.mock_gmail_service, '123')

    def test_read_email_voice_not_listed(self):
        self.handler.listed_emails = []
        response = self.handler.read_email_voice("1")
        self.assertEqual(response, "You haven't listed any emails yet. Try asking to fetch unread emails first.")

    def test_read_email_voice_identifier_not_found(self):
        self.handler.listed_emails = [{'id': '123', 'subject': 'Hello', 'from': 'sender1@example.com', 'number': 1}]
        response = self.handler.read_email_voice("nonexistent")
        self.assertIn("Sorry, I couldn't find an email matching 'nonexistent'", response)

    @patch('voice_email_handler.email_utils.reply_to_email')
    def test_prepare_reply_voice_success(self, mock_reply_to_email):
        self.handler.current_email_id = '123'
        self.handler.current_email_content = {'id': '123', 'subject': 'Hello', 'from': 'sender1@example.com', 'body': 'Original body.'}
        mock_reply_to_email.return_value = {'id': 'reply_msg_id'} 

        response = self.handler.prepare_reply_voice("This is my reply.")

        self.assertIn("Okay, I've sent your reply to sender1@example.com with subject Hello.", response)
        mock_reply_to_email.assert_called_once_with(self.mock_gmail_service, '123', "This is my reply.")

    def test_prepare_reply_voice_no_email_selected(self):
        response = self.handler.prepare_reply_voice("This is my reply.")
        self.assertEqual(response, "You haven't selected an email to reply to. Please read an email first.")
        
    def test_prepare_reply_voice_empty_reply_text(self):
        self.handler.current_email_id = '123'
        self.handler.current_email_content = {'id': '123', 'subject': 'Hello', 'from': 'sender1@example.com', 'body': 'Original body.'}
        response = self.handler.prepare_reply_voice("   ") 
        self.assertEqual(response, "The reply message seems to be empty. Please provide your reply.")

    @patch('voice_email_handler.email_utils.read_email') # Patch where it's used
    @patch('voice_email_handler.email_utils.mark_email_as_read') # Also patch mark_email_as_read as it's called in the same path
    def test_read_email_voice_http_error_403_on_read_email(self, mock_mark_as_read, mock_read_email): # mock_mark_as_read added
        self.handler.listed_emails = [{'id': '789', 'subject': 'Secret', 'from': 'spy@example.com', 'number': 1}]
        self.mock_http_error_response.status = 403
        # Simulate HttpError only on read_email, not on mark_email_as_read
        mock_read_email.side_effect = HttpError(resp=self.mock_http_error_response, content=b'Forbidden')
        
        response = self.handler.read_email_voice("1") # Identifier "1" corresponds to email '789'
        # Check that the error message for read_email is returned
        self.assertEqual(response, "I don't have the necessary permissions to read that email. You might need to re-authenticate with updated permissions.")
        # Ensure mark_email_as_read was NOT called because read_email failed
        mock_mark_as_read.assert_not_called()

    @patch('voice_email_handler.email_utils.read_email')
    @patch('voice_email_handler.email_utils.mark_email_as_read')
    def test_read_email_voice_http_error_403_on_mark_as_read(self, mock_mark_as_read, mock_read_email):
        self.handler.listed_emails = [{'id': '789', 'subject': 'Secret', 'from': 'spy@example.com', 'number': 1}]
        # read_email succeeds
        mock_read_email.return_value = {'id': '789', 'subject': 'Secret', 'from': 'spy@example.com', 'body': 'Secret body.'}
        
        self.mock_http_error_response.status = 403
        # mark_email_as_read fails with HttpError
        mock_mark_as_read.side_effect = HttpError(resp=self.mock_http_error_response, content=b'Forbidden on mark as read')
        
        response = self.handler.read_email_voice("1")
        
        # The function should still return the email content as reading was successful
        # The error from mark_email_as_read is printed by email_utils but not returned to voice_email_handler to alter this response string
        self.assertIn("Reading email from spy@example.com. Subject: Secret. Body: Secret body.", response)
        
        # We can check if email_utils.mark_email_as_read was called, even if it failed internally and printed an error
        mock_mark_as_read.assert_called_once_with(self.mock_gmail_service, '789')


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
