import unittest
from unittest.mock import patch, MagicMock, ANY
import os

# Before importing outlook_utils, set up mock environment variables
# These would normally be in config.py or actual environment
mock_env_vars = {
    "OUTLOOK_CLIENT_ID": "test_client_id",
    "OUTLOOK_CLIENT_SECRET": "test_client_secret", # Though not used by PublicClientApplication
    "OUTLOOK_TENANT_ID": "test_tenant_id",
}

# Patch os.environ before outlook_utils is imported by the test runner
# or when this module is loaded.
# If outlook_utils is imported at the top of this file *before* this patch,
# it might load the real os.environ values or defaults from its own os.environ.get calls.
# A common pattern is to import the module *under test* within test methods or setUp,
# after patches are applied. Or, ensure patches are active when the module is first loaded.
# For simplicity here, we assume the patch is effective when outlook_utils is loaded.
# If tests fail due to config, this is the area to check.

with patch.dict(os.environ, mock_env_vars, clear=True):
    from outlook_utils import OutlookService
    # Import specific msgraph models only if needed for constructing complex mock return values.
    # Often, MagicMock with configured attributes is enough.
    from msgraph.generated.models.message import Message
    from msgraph.generated.models.email_address import EmailAddress
    from msgraph.generated.models.recipient import Recipient
    from msgraph.generated.models.item_body import ItemBody
    from msgraph.generated.models.body_type import BodyType
    from msgraph.generated.me.messages.item.reply.reply_post_request_body import ReplyPostRequestBody


# Helper function to create a mock Graph API message object
def create_mock_graph_message(msg_id, subject, sender_name, sender_address, body_content, body_type_enum, body_preview=""):
    mock_msg = MagicMock(spec=Message)
    mock_msg.id = msg_id
    mock_msg.subject = subject
    
    mock_sender_email = MagicMock(spec=EmailAddress)
    mock_sender_email.name = sender_name
    mock_sender_email.address = sender_address
    
    mock_sender = MagicMock(spec=Recipient)
    mock_sender.email_address = mock_sender_email
    mock_msg.sender = mock_sender
    
    mock_body = MagicMock(spec=ItemBody)
    mock_body.content = body_content
    mock_body.content_type = body_type_enum # e.g., BodyType.Text or BodyType.HTML
    mock_msg.body = mock_body
    
    mock_msg.body_preview = body_preview
    mock_msg.is_read = False # Default
    return mock_msg

class TestOutlookService(unittest.TestCase):

    def setUp(self):
        # This ensures that each test method gets a fresh OutlookService instance
        # and that os.environ is patched for each test method's scope if needed.
        # However, the import of outlook_utils happens when this test module is loaded.
        # So, the class-level patch.dict for os.environ is crucial.
        pass

    @patch('outlook_utils.GraphServiceClient') # To verify it's called
    @patch('outlook_utils.PublicClientApplication')
    def test_auth_flow_success_new_token(self, MockPublicClientApplication, MockGraphServiceClient):
        mock_app_instance = MockPublicClientApplication.return_value
        mock_app_instance.get_accounts.return_value = [] # No accounts in cache
        
        mock_flow = {
            "user_code": "TESTCODE",
            "verification_uri": "https://login.microsoft.com/test",
            "message": "Please sign in..."
        }
        mock_app_instance.initiate_device_flow.return_value = mock_flow
        
        mock_token_result = {"access_token": "fake_access_token"}
        mock_app_instance.acquire_token_by_device_flow.return_value = mock_token_result

        with patch.dict(os.environ, mock_env_vars): # Ensure env vars for constructor
            # Explicitly pass client_id and tenant_id, even if defaults would be picked up from mock_env_vars
            service = OutlookService(client_id=mock_env_vars["OUTLOOK_CLIENT_ID"], tenant_id=mock_env_vars["OUTLOOK_TENANT_ID"])

        mock_app_instance.get_accounts.assert_called_once()
        mock_app_instance.initiate_device_flow.assert_called_once_with(scopes=["https://graph.microsoft.com/.default"])
        mock_app_instance.acquire_token_by_device_flow.assert_called_once_with(mock_flow)
        self.assertIsNotNone(service.graph_client)
        MockGraphServiceClient.assert_called_once()
        # Check if credentials callable returns the token
        graph_constructor_creds = MockGraphServiceClient.call_args[1]['credentials']
        self.assertEqual(graph_constructor_creds(), "fake_access_token")


    @patch('outlook_utils.GraphServiceClient')
    @patch('outlook_utils.PublicClientApplication')
    def test_auth_flow_success_cached_token(self, MockPublicClientApplication, MockGraphServiceClient):
        mock_app_instance = MockPublicClientApplication.return_value
        
        mock_account = MagicMock() # Simulate an account object
        mock_app_instance.get_accounts.return_value = [mock_account]
        
        mock_token_result = {"access_token": "cached_fake_access_token"}
        mock_app_instance.acquire_token_silent.return_value = mock_token_result

        with patch.dict(os.environ, mock_env_vars):
            service = OutlookService(client_id=mock_env_vars["OUTLOOK_CLIENT_ID"], tenant_id=mock_env_vars["OUTLOOK_TENANT_ID"])

        mock_app_instance.get_accounts.assert_called_once()
        mock_app_instance.acquire_token_silent.assert_called_once_with(scopes=["https://graph.microsoft.com/.default"], account=mock_account)
        mock_app_instance.initiate_device_flow.assert_not_called()
        self.assertIsNotNone(service.graph_client)
        MockGraphServiceClient.assert_called_once()
        graph_constructor_creds = MockGraphServiceClient.call_args[1]['credentials']
        self.assertEqual(graph_constructor_creds(), "cached_fake_access_token")


    @patch('outlook_utils.PublicClientApplication')
    def test_auth_flow_failure(self, MockPublicClientApplication):
        mock_app_instance = MockPublicClientApplication.return_value
        mock_app_instance.get_accounts.return_value = []
        mock_app_instance.initiate_device_flow.return_value = {"user_code": "CODE", "verification_uri": "URI"}
        mock_app_instance.acquire_token_by_device_flow.return_value = {"error": "auth_failed", "error_description": "User cancelled."}

        with patch.dict(os.environ, mock_env_vars):
            with self.assertRaisesRegex(Exception, "Authentication failed: auth_failed, User cancelled."):
                OutlookService(client_id=mock_env_vars["OUTLOOK_CLIENT_ID"], tenant_id=mock_env_vars["OUTLOOK_TENANT_ID"])
    
    @patch('outlook_utils.PublicClientApplication')
    def test_auth_flow_initiate_device_flow_failure(self, MockPublicClientApplication):
        mock_app_instance = MockPublicClientApplication.return_value
        mock_app_instance.get_accounts.return_value = []
        # Simulate initiate_device_flow failing to return 'user_code'
        mock_app_instance.initiate_device_flow.return_value = {"error": "some_error", "error_description": "Failed to create flow."}
        
        with patch.dict(os.environ, mock_env_vars):
            with self.assertRaisesRegex(ValueError, "Failed to create device flow"):
                OutlookService(client_id=mock_env_vars["OUTLOOK_CLIENT_ID"], tenant_id=mock_env_vars["OUTLOOK_TENANT_ID"])

    def _setup_mock_service_with_graph_client(self):
        """
        Helper to create a service instance with a mocked graph_client.
        This bypasses __init__ and _auth_flow, directly setting up what's needed for API call tests.
        """
        service = OutlookService.__new__(OutlookService) 
        service.client_id = mock_env_vars["OUTLOOK_CLIENT_ID"]
        service.tenant_id = mock_env_vars["OUTLOOK_TENANT_ID"] # Explicitly set tenant_id
        service.authority = f"https://login.microsoftonline.com/{service.tenant_id}" # Reconstruct authority based on set tenant_id
        service.scopes = ["https://graph.microsoft.com/.default"]
        service.graph_client = MagicMock()
        # service.app would not be initialized here, as _auth_flow is bypassed.
        # This is acceptable if tests using this helper don't rely on self.app.
        return service

    def test_list_emails_success_unread_only(self):
        service = self._setup_mock_service_with_graph_client()
        
        mock_msg1 = create_mock_graph_message("id1", "Subj1", "Sender1", "s1@test.com", "Body1", BodyType.Text, "Preview1")
        mock_response = MagicMock()
        mock_response.value = [mock_msg1]
        
        # Configure the mock get method for the mail folder messages
        service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.return_value = mock_response
        
        emails = service.list_emails(folder="inbox", count=5, unread_only=True)
        
        self.assertEqual(len(emails), 1)
        # Verify the request configuration was called correctly
        request_config_arg = service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.call_args[1]['request_configuration']
        self.assertEqual(request_config_arg.query_parameters.top, 5)
        self.assertEqual(request_config_arg.query_parameters.filter, "isRead eq false")
        self.assertIn("receivedDateTime desc", request_config_arg.query_parameters.orderby)
        self.assertEqual(emails[0].subject, "Subj1") # Check that raw message objects are returned

    def test_list_emails_success_all(self):
        service = self._setup_mock_service_with_graph_client()
        mock_msg1 = create_mock_graph_message("id1", "Subj1", "Sender1", "s1@test.com", "Body1", BodyType.Text, "Preview1")
        mock_response = MagicMock()
        mock_response.value = [mock_msg1]
        service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.return_value = mock_response

        emails = service.list_emails(folder="inbox", count=10, unread_only=False)
        self.assertEqual(len(emails), 1)
        request_config_arg = service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.call_args[1]['request_configuration']
        self.assertEqual(request_config_arg.query_parameters.top, 10)
        self.assertIsNone(request_config_arg.query_parameters.filter) # No filter for all messages

    def test_list_emails_no_emails_found(self):
        service = self._setup_mock_service_with_graph_client()
        mock_response = MagicMock()
        mock_response.value = [] # Empty list
        service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.return_value = mock_response
        
        emails = service.list_emails(folder="inbox")
        self.assertEqual(len(emails), 0)

    def test_list_emails_api_error(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.mail_folders.by_mail_folder_id.return_value.messages.get.side_effect = Exception("API Error")
        
        emails = service.list_emails(folder="inbox")
        self.assertEqual(len(emails), 0) # Should return empty list on error

    def test_read_email_success(self):
        service = self._setup_mock_service_with_graph_client()
        mock_msg = create_mock_graph_message("msg123", "Test Subject", "Test Sender", "sender@example.com", "Email body content", BodyType.Text)
        service.graph_client.me.messages.by_message_id.return_value.get.return_value = mock_msg

        email_data = service.read_email("msg123")

        self.assertIsNotNone(email_data)
        self.assertEqual(email_data['id'], "msg123")
        self.assertEqual(email_data['subject'], "Test Subject")
        self.assertEqual(email_data['sender'], "sender@example.com")
        self.assertEqual(email_data['body'], "Email body content")
        self.assertEqual(email_data['body_type'], str(BodyType.Text))
        service.graph_client.me.messages.by_message_id.assert_called_once_with("msg123")

    def test_read_email_not_found(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.get.return_value = None # Simulate not found
        
        email_data = service.read_email("nonexistent_id")
        self.assertIsNone(email_data)

    def test_read_email_api_error(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.get.side_effect = Exception("API Error")
        
        email_data = service.read_email("msg123")
        self.assertIsNone(email_data)

    def test_reply_to_email_success(self):
        service = self._setup_mock_service_with_graph_client()
        # The reply post() method does not typically return a body on success, just a 2xx status.
        service.graph_client.me.messages.by_message_id.return_value.reply.post.return_value = None 

        success = service.reply_to_email("msg123", "This is a reply.")
        self.assertTrue(success)
        
        # Check that post was called with a ReplyPostRequestBody
        call_args = service.graph_client.me.messages.by_message_id.return_value.reply.post.call_args
        self.assertIsNotNone(call_args)
        request_body = call_args[1]['body'] # body is a kwarg
        self.assertIsInstance(request_body, ReplyPostRequestBody)
        self.assertEqual(request_body.comment, "This is a reply.")


    def test_reply_to_email_api_error(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.reply.post.side_effect = Exception("API Error")
        
        success = service.reply_to_email("msg123", "This is a reply.")
        self.assertFalse(success)

    def test_mark_email_as_read_success(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.patch.return_value = None # PATCH usually returns 204 No Content

        success = service.mark_email_as_read("msg123")
        self.assertTrue(success)
        
        call_args = service.graph_client.me.messages.by_message_id.return_value.patch.call_args
        self.assertIsNotNone(call_args)
        message_update_body = call_args[1]['body'] # body is a kwarg
        self.assertIsInstance(message_update_body, Message)
        self.assertTrue(message_update_body.is_read)

    def test_mark_email_as_read_api_error(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.patch.side_effect = Exception("API Error")
        
        success = service.mark_email_as_read("msg123")
        self.assertFalse(success)

    def test_mark_email_as_unread_success(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.patch.return_value = None

        success = service.mark_email_as_unread("msg123")
        self.assertTrue(success)

        call_args = service.graph_client.me.messages.by_message_id.return_value.patch.call_args
        message_update_body = call_args[1]['body']
        self.assertIsInstance(message_update_body, Message)
        self.assertFalse(message_update_body.is_read)

    def test_mark_email_as_unread_api_error(self):
        service = self._setup_mock_service_with_graph_client()
        service.graph_client.me.messages.by_message_id.return_value.patch.side_effect = Exception("API Error")
        
        success = service.mark_email_as_unread("msg123")
        self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()
