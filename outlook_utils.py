import logging
import os
from msal import ConfidentialClientApplication, PublicClientApplication
from msgraph.generated.graph_service_client import GraphServiceClient
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress

# Configuration placeholders (similar to config.py)
# These should be set in a config file or environment variables
DEFAULT_CLIENT_ID = os.environ.get("OUTLOOK_CLIENT_ID")
DEFAULT_CLIENT_SECRET = os.environ.get("OUTLOOK_CLIENT_SECRET")  # For ConfidentialClientApplication
DEFAULT_TENANT_ID = os.environ.get("OUTLOOK_TENANT_ID") # Default tenant_id from environment
DEFAULT_SCOPES = ["https://graph.microsoft.com/.default"] # Or more specific scopes like "Mail.ReadWrite", "Mail.Send"

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OutlookService:
    def __init__(self, client_id: str = DEFAULT_CLIENT_ID, 
                 tenant_id: str = DEFAULT_TENANT_ID, 
                 client_secret: str = None, # Optional, mainly for confidential clients
                 scopes: list = None):
        
        if not client_id:
            raise ValueError("Outlook client_id is required.")
        if not tenant_id:
            raise ValueError("Outlook tenant_id is required.")

        self.client_id = client_id
        self.tenant_id = tenant_id
        # Use provided client_secret or default from env (though PublicClientApplication usually doesn't use it)
        self.client_secret = client_secret if client_secret is not None else DEFAULT_CLIENT_SECRET
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = scopes if scopes is not None else DEFAULT_SCOPES
        
        self.graph_client = None
        self.last_device_flow_details = None # Store device flow details if that path is taken
        
        # Initialize PublicClientApplication in __init__
        # Using PublicClientApplication for device flow or interactive auth.
        # Suitable for scenarios where a user can interactively sign in.
        # For background services or web applications, ConfidentialClientApplication is more appropriate
        # and would typically use self.client_secret.
        self.app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            # token_cache= # Optional: configure a token cache for persistence if desired
        )
        
        self._auth_flow()

    def _auth_flow(self):
        """
        Authenticates with Microsoft Graph API using MSAL.
        Tries to load existing tokens, otherwise initiates device flow or interactive flow.
        self.app (PublicClientApplication instance) must be initialized before calling this.
        For server-to-server auth (e.g. a daemon app), ConfidentialClientApplication with client secret or certificate is preferred.
        """
        if not self.app:
            raise RuntimeError("MSAL PublicClientApplication not initialized. Call __init__ first.")

        accounts = self.app.get_accounts()
        result = None

        if accounts:
            logger.info("Account(s) found in cache. Attempting to acquire token silently.")
            # Assuming the first account is the one we want to use.
            # For multi-account scenarios, you might need to iterate or provide a way to select an account.
            result = self.app.acquire_token_silent(scopes=self.scopes, account=accounts[0])

        if not result:
            logger.info("No suitable token in cache. Initiating device flow for PublicClientApplication.")
            # This flow is for PublicClientApplication.
            # For ConfidentialClientApplication, you would use acquire_token_for_client.
            flow = self.app.initiate_device_flow(scopes=self.scopes)
            if "user_code" not in flow:
                raise ValueError(
                    "Failed to create device flow. Ensure the AAD App registration"
                    " allows public client flows or that your tenant settings permit it."
                )
            
            # Return flow details for the app to display
            # The app will then need to call acquire_token_by_device_flow separately
            # For now, let's assume a blocking flow for simplicity in the initial integration,
            # but ideally, this would be handled more gracefully in a web app.
            # Returning the flow and letting app.py manage the blocking call after user sees the code.
            # However, acquire_token_by_device_flow itself is blocking.
            # A better approach for Streamlit might be:
            # 1. Initiate flow, get code.
            # 2. Display code to user.
            # 3. User authenticates.
            # 4. App then calls acquire_token_by_device_flow (which should then return quickly if user authenticated).
            # This is still tricky because the acquire_token_by_device_flow is blocking.
            # For this iteration, _auth_flow will remain blocking but will return the flow details
            # *before* the blocking call, so app.py can at least store them.
            
            st_display_data = {
                "user_code": flow.get("user_code"),
                "verification_uri": flow.get("verification_uri"),
                "message": flow.get("message") 
            }
            
            # The following print is for CLI, app.py should display this info to user
            print(f"Please sign in: {st_display_data.get('message', 'Open your browser to the verification URI and enter the user code.')}")

            # Blocks until user authenticates or flow times out
            result = self.app.acquire_token_by_device_flow(flow) 
            
            # Store the display data in the instance if needed, though app.py should handle UI
            self.last_device_flow_details = st_display_data


        if result and "access_token" in result:
            logger.info("Access token acquired successfully.")
            # Create a credential object for GraphServiceClient
            # The lambda function will be called by the SDK to get the token
            self.graph_client = GraphServiceClient(
                credentials=lambda: result.get("access_token")
            )
        elif result:
            error_description = result.get("error_description", "No error description provided.")
            logger.error(f"Failed to acquire access token: {result.get('error')}, {error_description}")
            raise Exception(f"Authentication failed: {result.get('error')}, {error_description}")
        else:
            logger.error("Authentication result was None. This should not happen if flow was initiated.")
            raise Exception("Authentication failed: No result from token acquisition process.")


    def list_emails(self, folder="inbox", count=10, unread_only=False):
        """
        Lists emails from the specified folder.
        :param folder: Mail folder to list emails from (e.g., "inbox", "sentitems").
        :param count: Number of emails to retrieve.
        :param unread_only: If True, retrieve only unread emails.
        :return: List of email messages.
        """
        if not self.graph_client:
            logger.error("Graph client not initialized. Authentication might have failed.")
            return []

        try:
            # Correct way to define request configuration for query parameters
            class MessagesRequestBuilderGetRequestConfiguration:
                def __init__(self, top=None, filter_query=None, orderby=None, select=None, expand=None):
                    self.query_parameters = self.QueryParameters(
                        top=top, filter=filter_query, orderby=orderby, select=select, expand=expand
                    )

                class QueryParameters:
                    def __init__(self, top=None, filter=None, orderby=None, select=None, expand=None):
                        self.top = top
                        self.filter = filter
                        self.orderby = orderby
                        self.select = select # Specify fields to retrieve e.g. ["subject", "sender", "receivedDateTime"]
                        self.expand = expand # For expanding navigation properties

            request_config = MessagesRequestBuilderGetRequestConfiguration(
                top=count,
                orderby=["receivedDateTime desc"],
                select=["id", "subject", "sender", "receivedDateTime", "isRead", "bodyPreview"] # Added bodyPreview
            )
            if unread_only:
                request_config.query_parameters.filter = "isRead eq false"

            # Use the folder name (e.g., "inbox", "sentitems") directly if it's a well-known folder.
            # For other folders, you might need to get their ID first.
            # Common folder names like 'inbox', 'drafts', 'sentitems', 'deleteditems' are usually recognized.
            messages_response = self.graph_client.me.mail_folders.by_mail_folder_id(folder).messages.get(request_configuration=request_config)
            
            return messages_response.value if messages_response and messages_response.value else []
        except Exception as e:
            logger.error(f"Error listing emails from folder '{folder}': {e}", exc_info=True)
            return []

    def read_email(self, message_id):
        """
        Reads the content of a specific email.
        :param message_id: ID of the email message to read.
        :return: Dictionary with email details (subject, sender, body) or None if error.
        """
        if not self.graph_client:
            logger.error("Graph client not initialized.")
            return None
        try:
            message = self.graph_client.me.messages.by_message_id(message_id).get()
            if message:
                return {
                    "subject": message.subject,
                    "id": message.id, # Include message ID
                    "subject": message.subject,
                    "sender": message.sender.email_address.address if message.sender and message.sender.email_address else "N/A",
                    "body": message.body.content if message.body else "",
                    "body_type": str(message.body.content_type) if message.body else str(BodyType.Text) # Default to Text
                }
            return None
        except Exception as e:
            logger.error(f"Error reading email {message_id}: {e}", exc_info=True)
            return None

    def reply_to_email(self, message_id, reply_text):
        """
        Sends a reply to a specific email.
        :param message_id: ID of the email message to reply to.
        :param reply_text: Text content of the reply.
        :return: True if reply sent successfully, False otherwise.
        """
        if not self.graph_client:
            logger.error("Graph client not initialized.")
            return False
        try:
            # To create a reply, we need to build a request body for the 'reply' action.
            # The 'reply' action does not take a full Message object in its request body directly,
            # but rather a 'comment' and optionally a 'message' object to embed changes.
            # Let's simplify to just sending a comment, which becomes the body of the reply.

            from msgraph.generated.me.messages.item.reply.reply_post_request_body import ReplyPostRequestBody

            request_body = ReplyPostRequestBody(
                comment=reply_text,
                # Optionally, you can include a 'message' field here to add attachments or change recipients for the reply
                # message = Message(
                #     to_recipients=[Recipient(email_address=EmailAddress(address="someone@example.com"))] # Example
                # )
            )
            
            self.graph_client.me.messages.by_message_id(message_id).reply.post(body=request_body)
            logger.info(f"Reply action initiated for email {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error replying to email {message_id}: {e}", exc_info=True)
            return False

    def mark_email_as_read(self, message_id):
        """
        Marks an email as read.
        :param message_id: ID of the email message.
        :return: True if successful, False otherwise.
        """
        if not self.graph_client:
            logger.error("Graph client not initialized.")
            return False
        try:
            # Update message to set isRead to true
            # The body for a PATCH request should be a Message object with the fields to update
            message_update = Message(is_read=True) 
            self.graph_client.me.messages.by_message_id(message_id).patch(body=message_update)
            logger.info(f"Email {message_id} marked as read.")
            return True
        except Exception as e:
            logger.error(f"Error marking email {message_id} as read: {e}", exc_info=True)
            return False

    def mark_email_as_unread(self, message_id):
        """
        Marks an email as unread.
        :param message_id: ID of the email message.
        :return: True if successful, False otherwise.
        """
        if not self.graph_client:
            logger.error("Graph client not initialized.")
            return False
        try:
            message_update = Message(is_read=False) # Note: is_read is a boolean, not a string
            self.graph_client.me.messages.by_message_id(message_id).patch(body=message_update)
            logger.info(f"Email {message_id} marked as unread.")
            return True
        except Exception as e:
            logger.error(f"Error marking email {message_id} as unread: {e}", exc_info=True)
            return False

if __name__ == '__main__':
    # Example Usage (requires environment variables to be set for authentication)
    # Ensure OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID are set in your environment
    # For ConfidentialClientApplication (web apps/services), also set OUTLOOK_CLIENT_SECRET

    logger.info("Starting Outlook Service example.")
    try:
        outlook_service = OutlookService()

        if outlook_service.graph_client:
            logger.info("Successfully authenticated with Outlook.")

            # Example: List top 5 unread emails from Inbox (using a common folder name)
            print("\nListing top 5 unread emails from Inbox...")
            try:
                unread_emails = outlook_service.list_emails(folder="inbox", unread_only=True, count=5)
                if unread_emails:
                    for email in unread_emails:
                        print(f"  ID: {email.id} | Subject: {email.subject} | Preview: {email.body_preview}")
                        # Store one ID for further tests
                        if "YOUR_TEST_MESSAGE_ID_HERE" == "YOUR_TEST_MESSAGE_ID_HERE" and email.id: # Avoid overwriting if already set
                             example_message_id = email.id 
                else:
                    print("  No unread emails found or error listing emails.")
            except Exception as e_list:
                print(f"  Error listing emails: {e_list}")
            
            # To test further, you would need a valid message ID from your Outlook account
            # Replace "YOUR_TEST_MESSAGE_ID_HERE" with an actual message ID after running list_emails
            # example_message_id = "AAMkAGVmMDEz..." # Replace this!

            if example_message_id and example_message_id != "YOUR_TEST_MESSAGE_ID_HERE":
                print(f"\n--- Operations for message ID: {example_message_id} ---")

                print(f"\nReading email {example_message_id}...")
                email_content = outlook_service.read_email(example_message_id)
                if email_content:
                    print(f"  Subject: {email_content['subject']}")
                    print(f"  From: {email_content['sender']}")
                    print(f"  Body Type: {email_content['body_type']}")
                    # print(f"  Body: {email_content['body'][:200]}...") # Print first 200 chars of body

                # Example: Mark as unread (if it was read)
                # print(f"\nMarking {example_message_id} as unread...")
                # if outlook_service.mark_email_as_unread(example_message_id):
                #     print("  Marked as unread.")
                # else:
                #     print("  Failed to mark as unread.")

                # Example: Mark as read
                print(f"\nMarking {example_message_id} as read...")
                if outlook_service.mark_email_as_read(example_message_id):
                    print("  Marked as read.")
                else:
                    print("  Failed to mark as read.")

                # Example: Reply to email (use with caution - this will send an email)
                # print(f"\nReplying to {example_message_id}...")
                # reply_body = "This is an automated test reply from OutlookService via Python script."
                # if outlook_service.reply_to_email(example_message_id, reply_body):
                #      print("  Reply sent.")
                # else:
                #      print("  Failed to send reply.")
            else:
                logger.warning(
                    "Skipping single email operations as graph_client is not available or "
                    "example_message_id is not set (e.g. no unread emails found to pick an ID)."
                )
        else:
            logger.error("Outlook Service initialization failed. graph_client is not available.")

    except Exception as e:
        logger.error(f"An error occurred in the Outlook Service example: {e}", exc_info=True)

    logger.info("Outlook Service example finished.")
