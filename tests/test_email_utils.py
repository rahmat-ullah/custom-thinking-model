import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import base64

# Assuming email_utils.py and config.py are in the parent directory or accessible via PYTHONPATH
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import email_utils
import config

# Helper to create a mock email body
def create_mock_email_body(text_content=None, html_content=None):
    parts = []
    if text_content:
        parts.append({
            'mimeType': 'text/plain',
            'body': {'data': base64.urlsafe_b64encode(text_content.encode('utf-8')).decode('utf-8')}
        })
    if html_content:
        parts.append({
            'mimeType': 'text/html',
            'body': {'data': base64.urlsafe_b64encode(html_content.encode('utf-8')).decode('utf-8')}
        })
    if not parts and text_content is None and html_content is None: # Simple non-multipart email
        return {'data': base64.urlsafe_b64encode("Default body".encode('utf-8')).decode('utf-8')}
    return None # Only return parts if they exist

class TestEmailUtils(unittest.TestCase):

    def setUp(self):
        # Store original config values and override for tests
        self.original_token_path = config.GMAIL_TOKEN_PATH
        self.original_creds_path = config.GMAIL_CREDENTIALS_PATH
        config.GMAIL_TOKEN_PATH = "test_token.json"
        config.GMAIL_CREDENTIALS_PATH = "test_credentials.json"

    def tearDown(self):
        # Restore original config values
        config.GMAIL_TOKEN_PATH = self.original_token_path
        config.GMAIL_CREDENTIALS_PATH = self.original_creds_path
        # Clean up any test files created if necessary (though mocks should prevent actual file creation)
        if os.path.exists("test_token.json"):
            os.remove("test_token.json")

    @patch('email_utils.build')
    @patch('email_utils.Credentials')
    @patch('email_utils.InstalledAppFlow')
    @patch('os.path.exists')
    def test_authenticate_gmail_token_exists_valid(self, mock_os_exists, MockInstalledAppFlow, MockCredentials, mock_build):
        print("\nRunning test_authenticate_gmail_token_exists_valid")
        mock_os_exists.return_value = True  # token.json exists
        
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = True
        MockCredentials.from_authorized_user_file.return_value = mock_creds_instance
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = email_utils.authenticate_gmail()

        MockCredentials.from_authorized_user_file.assert_called_once_with(config.GMAIL_TOKEN_PATH, email_utils.SCOPES)
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_creds_instance)
        self.assertEqual(service, mock_service)
        MockInstalledAppFlow.from_client_secrets_file.assert_not_called()

    @patch('email_utils.build')
    @patch('email_utils.Credentials')
    @patch('email_utils.InstalledAppFlow')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_authenticate_gmail_token_missing_flow_runs(self, mock_file_open, mock_os_exists, MockInstalledAppFlow, MockCredentials, mock_build):
        print("\nRunning test_authenticate_gmail_token_missing_flow_runs")
        mock_os_exists.return_value = False  # token.json does not exist
        
        mock_flow_instance = MagicMock()
        mock_creds_instance_from_flow = MagicMock()
        mock_creds_instance_from_flow.to_json.return_value = '{"token": "fake_token"}'
        mock_flow_instance.run_local_server.return_value = mock_creds_instance_from_flow
        MockInstalledAppFlow.from_client_secrets_file.return_value = mock_flow_instance
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = email_utils.authenticate_gmail()

        MockInstalledAppFlow.from_client_secrets_file.assert_called_once_with(config.GMAIL_CREDENTIALS_PATH, email_utils.SCOPES)
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        mock_file_open.assert_called_once_with(config.GMAIL_TOKEN_PATH, 'w')
        mock_file_open().write.assert_called_once_with('{"token": "fake_token"}')
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_creds_instance_from_flow)
        self.assertEqual(service, mock_service)
        MockCredentials.from_authorized_user_file.assert_not_called() # Should not be called if token doesn't exist

    # Decorator removed from test_authenticate_gmail_credentials_missing
    def test_authenticate_gmail_credentials_missing(self):
        print("\nRunning test_authenticate_gmail_credentials_missing")
        # This test now solely uses context managers for patching. No decorators above its definition.
        with patch('os.path.exists') as mock_os_exists, \
             patch('email_utils.InstalledAppFlow') as MockInstalledAppFlow, \
             patch('email_utils.build') as mock_build_for_creds_missing_test: # Renamed to avoid clash if any decorator remained
            
            mock_os_exists.return_value = False # Simulate token.json not existing
            MockInstalledAppFlow.from_client_secrets_file.side_effect = FileNotFoundError("credentials.json not found")

            # Expect FileNotFoundError to be raised
            with self.assertRaises(FileNotFoundError):
                email_utils.authenticate_gmail()
            
            mock_build_for_creds_missing_test.assert_not_called() # Build should not be called

    @patch('email_utils.build') # Restored decorator for this test
    @patch('email_utils.Credentials')
    @patch('email_utils.Request') # Ensure Request is part of the email_utils namespace or correctly imported for mocking
    @patch('email_utils.InstalledAppFlow')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open) # Mock open for token saving
    def test_authenticate_gmail_token_expired_refresh_saves_token(self, mock_file_open, mock_os_exists, MockInstalledAppFlow, MockRequest, MockCredentials, mock_build): # mock_build added back to signature
        print("\nRunning test_authenticate_gmail_token_expired_refresh_saves_token")
        mock_os_exists.return_value = True # token.json exists
        
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = False
        mock_creds_instance.expired = True
        mock_creds_instance.refresh_token = "fake_refresh_token"
        mock_creds_instance.to_json.return_value = '{"refreshed_token": "mock_value"}' # Ensure to_json returns a string
        MockCredentials.from_authorized_user_file.return_value = mock_creds_instance
        
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = email_utils.authenticate_gmail()

        MockCredentials.from_authorized_user_file.assert_called_once_with(config.GMAIL_TOKEN_PATH, email_utils.SCOPES)
        mock_creds_instance.refresh.assert_called_once_with(MockRequest())
        # Check that token is saved after refresh
        mock_file_open.assert_called_once_with(config.GMAIL_TOKEN_PATH, 'w')
        mock_file_open().write.assert_called_once_with('{"refreshed_token": "mock_value"}')
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_creds_instance)
        self.assertEqual(service, mock_service)
        MockInstalledAppFlow.from_client_secrets_file.assert_not_called()

    def test_list_emails_success(self):
        print("\nRunning test_list_emails_success")
        mock_service = MagicMock()
        mock_messages_resource = MagicMock()
        mock_list_execute = MagicMock() # This mock is for the list() method itself.
        
        expected_messages = [{'id': '123', 'threadId': 'abc'}, {'id': '456', 'threadId': 'def'}]
        # The list() method returns an object that has an execute() method.
        mock_list_execute.return_value.execute.return_value = {'messages': expected_messages, 'resultSizeEstimate': 2}
        
        mock_service.users.return_value.messages.return_value.list = mock_list_execute
        
        emails = email_utils.list_emails(mock_service, user_id='test_user', query='is:unread', max_results=5)
        
        mock_list_execute.assert_called_once_with(userId='test_user', q='is:unread', maxResults=5) # list() is called with these
        mock_list_execute.return_value.execute.assert_called_once_with() # execute() is called with no args on the result of list()
        self.assertEqual(emails, expected_messages)

    def test_list_emails_no_messages(self):
        print("\nRunning test_list_emails_no_messages")
        mock_service = MagicMock()
        mock_messages_resource = MagicMock()
        mock_list_execute = MagicMock()
        
        # list().execute() returns this
        mock_list_execute.return_value.execute.return_value = {'resultSizeEstimate': 0} # No 'messages' key
        
        mock_service.users.return_value.messages.return_value.list = mock_list_execute
        
        emails = email_utils.list_emails(mock_service, query='is:read')
        
        mock_list_execute.assert_called_once_with(userId='me', q='is:read', maxResults=10)
        mock_list_execute.return_value.execute.assert_called_once_with()
        self.assertEqual(emails, []) # Should return empty list

    def test_list_emails_api_error(self):
        print("\nRunning test_list_emails_api_error")
        mock_service = MagicMock()
        mock_messages_resource = MagicMock()
        mock_list_execute = MagicMock()
        
        # list().execute() raises an error
        mock_list_execute.return_value.execute.side_effect = Exception("API Error")
        mock_service.users.return_value.messages.return_value.list = mock_list_execute
        
        # Check that it prints an error and returns None 
        with patch('builtins.print') as mock_print:
            emails = email_utils.list_emails(mock_service)
            self.assertIsNone(emails)
            mock_print.assert_any_call("An error occurred: API Error")


    def test_read_email_plain_text(self):
        print("\nRunning test_read_email_plain_text")
        mock_service = MagicMock()
        mock_message_get_execute = MagicMock()

        email_body_text = "This is a plain text email."
        encoded_body = base64.urlsafe_b64encode(email_body_text.encode('utf-8')).decode('utf-8')
        
        mock_email_data = {
            'id': 'email123',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject Plain'},
                    {'name': 'From', 'value': 'sender@example.com'}
                ],
                'mimeType': 'text/plain', # Top level is plain
                'body': {'data': encoded_body} 
            }
        }
        mock_message_get_execute.execute.return_value = mock_email_data
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_email_data
        
        email_content = email_utils.read_email(mock_service, message_id='email123', user_id='test_user')
        
        mock_service.users.return_value.messages.return_value.get.return_value.execute.assert_called_once_with()
        # We need to assert the call to get() itself, not its return_value.execute
        mock_service.users.return_value.messages.return_value.get.assert_called_once_with(userId='test_user', id='email123', format='full')
        self.assertEqual(email_content['subject'], 'Test Subject Plain')
        self.assertEqual(email_content['from'], 'sender@example.com')
        self.assertEqual(email_content['body'], email_body_text)
        self.assertEqual(email_content['id'], 'email123')

    def test_read_email_multipart_plain_and_html(self):
        print("\nRunning test_read_email_multipart_plain_and_html")
        mock_service = MagicMock()
        mock_message_get_execute = MagicMock()

        plain_text_content = "This is the plain text part."
        html_content = "<p>This is the HTML part.</p>"
        
        mock_email_data = {
            'id': 'email456',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Test Subject Multipart'},
                    {'name': 'From', 'value': 'sender2@example.com'}
                ],
                'mimeType': 'multipart/alternative',
                'parts': [
                    {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(plain_text_content.encode('utf-8')).decode('utf-8')}},
                    {'mimeType': 'text/html', 'body': {'data': base64.urlsafe_b64encode(html_content.encode('utf-8')).decode('utf-8')}}
                ]
            }
        }
        mock_message_get_execute.execute.return_value = mock_email_data
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_email_data
        
        email_content = email_utils.read_email(mock_service, message_id='email456')
        
        mock_service.users.return_value.messages.return_value.get.assert_called_once_with(userId='me', id='email456', format='full')
        self.assertEqual(email_content['subject'], 'Test Subject Multipart')
        self.assertEqual(email_content['from'], 'sender2@example.com')
        self.assertEqual(email_content['body'], plain_text_content) # Should prioritize plain text

    def test_read_email_html_only_in_multipart(self):
        print("\nRunning test_read_email_html_only_in_multipart")
        mock_service = MagicMock()
        mock_message_get_execute = MagicMock()

        html_content = "<h1>HTML Only</h1>"
        
        mock_email_data = {
            'id': 'email789',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'HTML Only Subject'},
                    {'name': 'From', 'value': 'sender3@example.com'}
                ],
                'mimeType': 'multipart/alternative',
                'parts': [
                    {'mimeType': 'text/html', 'body': {'data': base64.urlsafe_b64encode(html_content.encode('utf-8')).decode('utf-8')}}
                ]
            }
        }
        mock_message_get_execute.execute.return_value = mock_email_data
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_email_data
        
        email_content = email_utils.read_email(mock_service, message_id='email789')
        mock_service.users.return_value.messages.return_value.get.assert_called_once_with(userId='me', id='email789', format='full')
        self.assertEqual(email_content['subject'], 'HTML Only Subject')
        self.assertEqual(email_content['from'], 'sender3@example.com')
        # Current implementation prioritizes text/plain. If only HTML, body might be empty or contain HTML based on future changes.
        # As per current email_utils, if text/plain is not found, body will be empty.
        self.assertEqual(email_content['body'], "") 

    def test_read_email_no_body_data(self):
        print("\nRunning test_read_email_no_body_data")
        mock_service = MagicMock()
        mock_message_get_execute = MagicMock()
        
        mock_email_data = {
            'id': 'email-no-body',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'No Body Data'},
                    {'name': 'From', 'value': 'sender4@example.com'}
                ],
                'mimeType': 'text/plain',
                'body': {} # No 'data' key in body
            }
        }
        mock_message_get_execute.execute.return_value = mock_email_data
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_email_data
        
        email_content = email_utils.read_email(mock_service, message_id='email-no-body')
        mock_service.users.return_value.messages.return_value.get.assert_called_once_with(userId='me', id='email-no-body', format='full')
        self.assertEqual(email_content['subject'], 'No Body Data')
        self.assertEqual(email_content['from'], 'sender4@example.com')
        self.assertEqual(email_content['body'], "")

    def test_read_email_api_error(self):
        print("\nRunning test_read_email_api_error")
        mock_service = MagicMock()
        mock_message_get_execute = MagicMock()

        mock_message_get_execute.execute.side_effect = Exception("API Read Error")
        mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = Exception("API Read Error")
        
        with patch('builtins.print') as mock_print:
            email_content = email_utils.read_email(mock_service, message_id='error_email')
            self.assertIsNone(email_content)
            # Check the actual printed message from the improved error logging in email_utils
            mock_print.assert_any_call("An error occurred while reading email error_email: Exception('API Read Error')")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

# To make sure the output of tests is captured in the tool execution
# We need to run this explicitly if not run by a test runner that captures output
# For the purpose of this tool, let's assume it will be run in a way that captures stdout
# or we can programmatically capture it.
# For now, print statements in tests help to see which test is running.
# suite = unittest.TestLoader().loadTestsFromTestCase(TestEmailUtils)
# unittest.TextTestRunner(verbosity=2).run(suite)
