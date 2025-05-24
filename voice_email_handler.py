import email_utils # To call Gmail API functions
from outlook_utils import OutlookService # To call Outlook API functions
from googleapiclient.errors import HttpError 
import logging

# We'll need audio_utils if we decide to make this handler speak directly,
# but for now, it will return text to be spoken by app.py
# import audio_utils

logger = logging.getLogger(__name__)

class VoiceEmailHandler:
    def __init__(self, gmail_service=None, outlook_service=None, initial_service_type='gmail'):
        self.gmail_service = gmail_service
        self.outlook_service = outlook_service
        self.listed_emails = []  # Stores {'id': '...', 'subject': '...', 'from': '...', 'number': ...}
        self.current_email_content = None # Stores full content of the currently selected email {'id', 'subject', 'sender', 'body'}
        self.current_email_id = None # ID of the currently selected email for operations like reply/mark
        self.active_service_client = None
        self.active_service_type = None # 'gmail' or 'outlook'

        if initial_service_type.lower() == 'outlook' and self.outlook_service:
            self.active_service_client = self.outlook_service
            self.active_service_type = 'outlook'
            logger.info("VoiceEmailHandler initialized with Outlook as active service.")
        elif self.gmail_service: # Default to gmail if available
            self.active_service_client = self.gmail_service
            self.active_service_type = 'gmail'
            logger.info("VoiceEmailHandler initialized with Gmail as active service.")
        elif self.outlook_service : # If gmail not available but outlook is
             self.active_service_client = self.outlook_service
             self.active_service_type = 'outlook'
             logger.info("VoiceEmailHandler initialized with Outlook as active service (Gmail was not provided).")
        else:
            logger.warning("VoiceEmailHandler initialized with no active email service.")
            # self.active_service_client remains None
            # self.active_service_type remains None

    def switch_email_service(self, service_type):
        """Switches the active email service to 'gmail' or 'outlook'."""
        service_type = service_type.lower()
        if service_type == 'gmail':
            if self.gmail_service:
                self.active_service_client = self.gmail_service
                self.active_service_type = 'gmail'
                self.listed_emails = [] # Clear context from other service
                self.current_email_id = None
                self.current_email_content = None
                logger.info("Switched active email service to Gmail.")
                return "Switched to Gmail."
            else:
                logger.warning("Attempted to switch to Gmail, but service not available.")
                return "Gmail service is not configured. Cannot switch."
        elif service_type == 'outlook':
            if self.outlook_service:
                self.active_service_client = self.outlook_service
                self.active_service_type = 'outlook'
                self.listed_emails = [] # Clear context from other service
                self.current_email_id = None
                self.current_email_content = None
                logger.info("Switched active email service to Outlook.")
                return "Switched to Outlook."
            else:
                logger.warning("Attempted to switch to Outlook, but service not available.")
                return "Outlook service is not configured. Cannot switch."
        else:
            logger.warning(f"Attempted to switch to unknown service type: {service_type}")
            return f"Unknown email service type '{service_type}'. Please choose Gmail or Outlook."

    def _get_active_service_name(self):
        if self.active_service_type == 'gmail':
            return "Gmail"
        elif self.active_service_type == 'outlook':
            return "Outlook"
        return "No email service"
        
    def _get_email_by_identifier(self, email_identifier):
        """Helper to find an email in listed_emails by number or keyword."""
        if not self.listed_emails:
            return None, "You haven't listed any emails yet. Try asking to fetch unread emails first."

        target_email = None
        try:
            email_number = int(email_identifier)
            target_email = next((email for email in self.listed_emails if email['number'] == email_number), None)
        except ValueError: # Not a number, try string match
            identifier_lower = str(email_identifier).lower()
            # Prioritize exact match on subject or sender if possible, then partial. For now, simple partial.
            for email in self.listed_emails:
                if identifier_lower in email['subject'].lower() or identifier_lower in email['from'].lower():
                    target_email = email
                    break
        
        if not target_email:
            return None, f"Sorry, I couldn't find an email matching '{email_identifier}' in the current list."
        return target_email, None

    def fetch_unread_emails_voice(self, max_results=5):
        """
        Fetches unread emails from the active service, stores essential details, 
        and returns a summary string for TTS.
        """
        if not self.active_service_client:
            return "No email service is active. Please connect to Gmail or Outlook first."

        service_name = self._get_active_service_name()
        logger.info(f"Fetching unread emails using {service_name} service (max_results={max_results}).")
        self.listed_emails = [] # Clear previous list for new fetch
        self.current_email_id = None
        self.current_email_content = None

        try:
            messages_raw = []
            if self.active_service_type == 'gmail':
                # Pass the service client instance to email_utils functions
                gmail_messages = email_utils.list_emails(self.active_service_client, query="is:unread", max_results=max_results)
                if gmail_messages is None:
                     return f"Sorry, I couldn't retrieve your unread emails from {service_name} at the moment."
                messages_raw = gmail_messages
            
            elif self.active_service_type == 'outlook':
                outlook_messages = self.active_service_client.list_emails(unread_only=True, count=max_results)
                messages_raw = outlook_messages 

            if not messages_raw:
                return f"You have no unread emails in your {service_name} account."
            
            email_summaries = []
            for i, msg_data in enumerate(messages_raw):
                try:
                    email_item = {'number': i + 1}
                    if self.active_service_type == 'gmail':
                        msg_preview = self.active_service_client.users().messages().get(
                            userId='me', 
                            id=msg_data['id'], 
                            format='metadata', 
                            metadataHeaders=['Subject', 'From']
                        ).execute()
                        subject = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
                        sender = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'From'), 'Unknown Sender')
                        email_item['id'] = msg_data['id']
                        email_item['subject'] = subject
                        email_item['from'] = sender
                    
                    elif self.active_service_type == 'outlook':
                        email_item['id'] = msg_data.id
                        email_item['subject'] = msg_data.subject if msg_data.subject else "No Subject"
                        sender_obj = msg_data.sender
                        if sender_obj and sender_obj.email_address:
                            email_item['from'] = sender_obj.email_address.name or sender_obj.email_address.address or "Unknown Sender"
                        else:
                            email_item['from'] = "Unknown Sender"
                        # email_item['preview'] = msg_data.body_preview # Optional

                    self.listed_emails.append(email_item)
                    email_summaries.append(f"{i+1}. Subject: {email_item['subject']}, From: {email_item['from']}")

                except Exception as e:
                    msg_id_attr = 'id' # Both Gmail (dict) and Outlook (obj) use 'id'
                    current_msg_id = getattr(msg_data, msg_id_attr, None) if hasattr(msg_data, msg_id_attr) else (msg_data.get('id', 'N/A') if isinstance(msg_data, dict) else 'N/A')

                    logger.error(f"Error processing message details for {service_name} (ID: {current_msg_id}): {e}", exc_info=True)
                    self.listed_emails.append({'id': current_msg_id, 'subject': 'Error fetching subject', 'from': 'Unknown', 'number': i + 1})
                    email_summaries.append(f"{i+1}. Could not fetch details for an email.")

            if not self.listed_emails:
                 return f"No unread emails found or there was an issue fetching details from {service_name}."

            response_text = f"I found {len(self.listed_emails)} unread emails in {service_name}. Here are the latest ones: " + ". ".join(email_summaries)
            return response_text

        except HttpError as e: 
            logger.error(f"Google API HttpError in fetch_unread_emails_voice: {e}", exc_info=True)
            if e.resp.status == 401: return "There's an issue with Gmail authentication. Please try reconnecting."
            if e.resp.status == 403: return "I don't have permissions for that Gmail action."
            return f"A Google API error occurred ({e.resp.status})."
        except Exception as e: 
            logger.error(f"An error occurred in fetch_unread_emails_voice for {service_name}: {e}", exc_info=True)
            return f"Sorry, an unexpected error occurred with {service_name}. Details: {str(e)}"

    def read_email_voice(self, email_identifier):
        """
        Reads a specific email from the active service based on its number in the list or part of subject/sender.
        Marks the email as read.
        Returns a string with the email content for TTS.
        """
        if not self.active_service_client:
            return "No email service is active."
        
        target_email, error_msg = self._get_email_by_identifier(email_identifier)
        if error_msg: return error_msg
        if not target_email: return f"Sorry, I couldn't find an email matching '{email_identifier}'." # Should be caught

        self.current_email_id = target_email['id'] # Set context for reply/mark actions
        service_name = self._get_active_service_name()
        logger.info(f"Reading email ID {self.current_email_id} using {service_name} service.")
        
        try:
            email_content_dict = None
            if self.active_service_type == 'gmail':
                email_content_dict = email_utils.read_email(self.active_service_client, self.current_email_id)
                if email_content_dict: # If read successfully
                    email_utils.mark_email_as_read(self.active_service_client, self.current_email_id)
            elif self.active_service_type == 'outlook':
                email_content_dict = self.active_service_client.read_email(self.current_email_id)
                if email_content_dict: # If read successfully
                    self.active_service_client.mark_email_as_read(self.current_email_id)
            
            if not email_content_dict: # Covers if service call returned None or empty
                return f"Sorry, I could not read the content for email from {target_email.get('from', 'N/A')} (Subject: {target_email.get('subject', 'N/A')}) using {service_name}."

            # Standardize self.current_email_content for reply function
            self.current_email_content = {
                'id': self.current_email_id, 
                'subject': email_content_dict.get('subject', 'No Subject'),
                'sender': email_content_dict.get('sender', email_content_dict.get('from', 'Unknown Sender')), # Gmail uses 'from', Outlook uses 'sender'
                'body': email_content_dict.get('body', 'No body content.')
            }
            
            response_text = f"Reading email from {service_name}. From: {self.current_email_content['sender']}. Subject: {self.current_email_content['subject']}. Body: {self.current_email_content['body']}"
            return response_text

        except HttpError as e: 
            logger.error(f"Google API HttpError for ID {self.current_email_id}: {e}", exc_info=True)
            if e.resp.status == 401: return f"Issue with {service_name} authentication."
            if e.resp.status == 403: return f"No permissions for that {service_name} action."
            if e.resp.status == 404: return f"Email ID {self.current_email_id} not found in {service_name}."
            return f"A {service_name} API error ({e.resp.status})."
        except Exception as e: 
            logger.error(f"Error in read_email_voice for {service_name} ID {self.current_email_id}: {e}", exc_info=True)
            return f"Unexpected error with {service_name} while reading. Details: {str(e)}"

    def send_reply_voice(self, reply_text): # Changed from send_prepared_reply_voice to match original intent more closely
        """
        Sends a reply to the currently selected email (set by read_email_voice).
        """
        if not self.active_service_client:
            return "No email service is active."
        if not self.current_email_id or not self.current_email_content:
            return "You haven't selected an email to reply to. Please read an email first to set the context."
        
        if not reply_text or not reply_text.strip():
            return "The reply message seems to be empty. Please provide your reply."

        service_name = self._get_active_service_name()
        original_sender = self.current_email_content.get('sender', 'the original sender')
        original_subject = self.current_email_content.get('subject', 'the original subject')
        logger.info(f"Sending reply to email ID {self.current_email_id} (Subject: {original_subject}) via {service_name}.")

        try:
            success = False
            if self.active_service_type == 'gmail':
                sent_message = email_utils.reply_to_email(
                    self.active_service_client, 
                    self.current_email_id,
                    reply_text 
                )
                success = bool(sent_message)
            elif self.active_service_type == 'outlook':
                success = self.active_service_client.reply_to_email( 
                    self.current_email_id,
                    reply_text
                )
            
            if success:
                return f"Okay, I've sent your reply via {service_name} to {original_sender} about '{original_subject}'."
            else:
                # This part might be tricky as False could mean an error or just no confirmation from SDK.
                # SDKs usually raise exceptions for errors.
                return f"Sorry, I couldn't send your reply using {service_name}. The service did not confirm success. Please try again."
        except HttpError as e: 
            logger.error(f"Google API HttpError in send_reply_voice: {e}", exc_info=True)
            if e.resp.status == 401: return f"Issue with {service_name} authentication for replying."
            if e.resp.status == 403: return f"No permissions to send replies from {service_name}."
            return f"A {service_name} API error ({e.resp.status}) occurred while replying."
        except Exception as e: 
            logger.error(f"Error in send_reply_voice for {service_name}: {e}", exc_info=True)
            return f"Unexpected error with {service_name} while sending reply. Details: {str(e)}"

    def mark_email_as_read_voice(self, email_identifier):
        if not self.active_service_client: return "No email service is active."
        
        target_email, error_msg = self._get_email_by_identifier(email_identifier)
        if error_msg: return error_msg
        if not target_email: return f"Could not find email '{email_identifier}' to mark as read."

        email_id = target_email['id']
        service_name = self._get_active_service_name()
        logger.info(f"Marking email ID {email_id} as read using {service_name}.")
        
        try:
            success = False
            if self.active_service_type == 'gmail':
                success = email_utils.mark_email_as_read(self.active_service_client, email_id)
            elif self.active_service_type == 'outlook':
                success = self.active_service_client.mark_email_as_read(email_id)
            
            return f"Email from {target_email.get('from', 'N/A')} marked as read using {service_name}." if success else f"Failed to mark email as read using {service_name}."
        except Exception as e:
            logger.error(f"Error marking email {email_id} as read for {service_name}: {e}", exc_info=True)
            return f"An error occurred with {service_name} trying to mark email as read."


    def mark_email_as_unread_voice(self, email_identifier):
        if not self.active_service_client: return "No email service is active."

        target_email, error_msg = self._get_email_by_identifier(email_identifier)
        if error_msg: return error_msg
        if not target_email: return f"Could not find email '{email_identifier}' to mark as unread."

        email_id = target_email['id']
        service_name = self._get_active_service_name()
        logger.info(f"Marking email ID {email_id} as unread using {service_name}.")

        try:
            success = False
            if self.active_service_type == 'gmail':
                success = email_utils.mark_email_as_unread(self.active_service_client, email_id)
            elif self.active_service_type == 'outlook':
                success = self.active_service_client.mark_email_as_unread(email_id)
            
            return f"Email from {target_email.get('from', 'N/A')} marked as unread using {service_name}." if success else f"Failed to mark email as unread using {service_name}."
        except Exception as e:
            logger.error(f"Error marking email {email_id} as unread for {service_name}: {e}", exc_info=True)
            return f"An error occurred with {service_name} trying to mark email as unread."


if __name__ == '__main__':
    # This section is for basic testing and won't run when imported.
    # To test this properly, you'd need mock services or actual credentials.
    print("VoiceEmailHandler module loaded. For testing, instantiate with service objects.")
    
    # Example (conceptual):
    # Define a simple EmailAddress if not available in this scope for Outlook mock
    class MockEmailAddress:
        def __init__(self, name, address): self.name = name; self.address = address

    class MockGmailService: # This will be the object passed as self.gmail_service
        # Methods that email_utils.py would call on the service object
        def users(self): return self # chain for users().messages()...
        def messages(self): return self
        def get(self, userId, id, format, metadataHeaders): 
            logger.debug(f"MOCK GMAIL GET MSG: {id}")
            # This execute needs to return the structure expected by the caller in VoiceEmailHandler
            return self 
        def execute(self): 
            logger.debug("MOCK GMAIL EXECUTE GET (for subject/sender)")
            # This is what's expected by the loop in fetch_unread_emails_voice (Gmail part)
            return {'payload': {'headers': [{'name': 'Subject', 'value': 'Test Gmail Subject'}, {'name': 'From', 'value': 'test@gmail.com'}]}}

        # Mocking the direct calls from VoiceEmailHandler that would go to email_utils
        # These need to match how email_utils functions are called, with service as first arg
        def list_emails(self, query, max_results): # This mocks email_utils.list_emails
            logger.info(f"MOCK GMAIL util.list_emails: query='{query}', max_results={max_results}")
            return [{'id': f'gmail_id_{i+1}'} for i in range(max_results)]
        
        def read_email(self, msg_id): # This mocks email_utils.read_email
            logger.info(f"MOCK GMAIL util.read_email: {msg_id}")
            return {'id': msg_id, 'subject': 'Full Mock Gmail Subject', 'sender': 'sender@gmail.com', 'body': 'Mock Gmail email body.'}
        
        def reply_to_email(self, msg_id, text): # This mocks email_utils.reply_to_email
            logger.info(f"MOCK GMAIL util.reply_to_email to {msg_id}: {text}")
            return {'id': 'sent_gmail_reply_id'} 
        
        def mark_email_as_read(self, msg_id): # This mocks email_utils.mark_email_as_read
            logger.info(f"MOCK GMAIL util.mark_as_read: {msg_id}")
            return True
        
        def mark_email_as_unread(self, msg_id): # This mocks email_utils.mark_email_as_unread
            logger.info(f"MOCK GMAIL util.mark_as_unread: {msg_id}")
            return True

    class MockOutlookService: # This will be self.outlook_service
        def list_emails(self, unread_only=False, count=5):
            logger.info(f"MOCK OUTLOOK list_emails: unread_only={unread_only}, count={count}")
            class Sender:
                def __init__(self, name, address): self.email_address = MockEmailAddress(name, address)
            class Message: # Mimics msgraph.generated.models.message.Message
                def __init__(self, id_val, subject_val, sender_name, sender_addr, body_preview_val="Outlook preview"):
                    self.id = id_val; self.subject = subject_val; self.sender = Sender(sender_name, sender_addr)
                    self.body_preview = body_preview_val
            return [Message(f"outlook_id_{i+1}", f"Outlook Subject {i+1}", f"OutlookSender{i+1}", f"sender{i+1}@outlook.com") for i in range(count)]
        
        def read_email(self, message_id): 
            logger.info(f"MOCK OUTLOOK read_email: {message_id}")
            return {'id': message_id, 'subject': 'Full Mock Outlook Subject', 'sender': 'sender@outlook.com', 'body': 'Mock Outlook email body.', 'body_type': 'HTML'}
        
        def reply_to_email(self, message_id, text): 
            logger.info(f"MOCK OUTLOOK reply_to_email to {message_id}: {text}")
            return True
        
        def mark_email_as_read(self, message_id): 
            logger.info(f"MOCK OUTLOOK mark_as_read: {message_id}")
            return True
        
        def mark_email_as_unread(self, message_id): 
            logger.info(f"MOCK OUTLOOK mark_as_unread: {message_id}")
            return True

    logging.basicConfig(level=logging.INFO) 

    print("\n--- Testing with Mock Gmail ---")
    # For Gmail, the handler expects a service object that email_utils functions can use.
    # The email_utils functions are called like: email_utils.list_emails(self.active_service_client, ...)
    # So, self.active_service_client (which is self.gmail_service) must be the mock service instance itself.
    mock_gmail_instance = MockGmailService()
    handler_gmail_active = VoiceEmailHandler(gmail_service=mock_gmail_instance, initial_service_type='gmail')
    
    # Test fetch_unread_emails_voice
    # Gmail path in fetch_unread_emails_voice:
    # 1. email_utils.list_emails(self.active_service_client, query="is:unread", max_results=max_results)
    #    - Here, self.active_service_client is mock_gmail_instance. So it calls mock_gmail_instance.list_emails(...)
    # 2. Inside loop: self.active_service_client.users().messages().get(...).execute()
    #    - This calls mock_gmail_instance.users().messages().get(...).execute()
    print(handler_gmail_active.fetch_unread_emails_voice(max_results=2))
    
    # Test read_email_voice
    # Gmail path in read_email_voice:
    # 1. email_utils.read_email(self.active_service_client, self.current_email_id)
    #    - Calls mock_gmail_instance.read_email(...)
    # 2. email_utils.mark_email_as_read(self.active_service_client, self.current_email_id)
    #    - Calls mock_gmail_instance.mark_email_as_read(...)
    print(handler_gmail_active.read_email_voice("1"))
    
    # Test send_reply_voice
    # Gmail path in send_reply_voice:
    # 1. email_utils.reply_to_email(self.active_service_client, self.current_email_id, reply_text)
    #    - Calls mock_gmail_instance.reply_to_email(...)
    print(handler_gmail_active.send_reply_voice("Test Gmail reply"))
    
    print(handler_gmail_active.mark_email_as_read_voice("1")) # Uses mock_gmail_instance.mark_email_as_read
    print(handler_gmail_active.mark_email_as_unread_voice("1")) # Uses mock_gmail_instance.mark_email_as_unread


    print("\n--- Testing with Mock Outlook ---")
    mock_outlook_instance = MockOutlookService()
    # For Outlook, methods are called directly on self.active_service_client (i.e., mock_outlook_instance)
    handler_outlook_active = VoiceEmailHandler(outlook_service=mock_outlook_instance, initial_service_type='outlook')
    print(handler_outlook_active.fetch_unread_emails_voice(max_results=2))
    print(handler_outlook_active.read_email_voice("1")) 
    print(handler_outlook_active.send_reply_voice("Test Outlook reply"))
    print(handler_outlook_active.mark_email_as_read_voice("1"))
    print(handler_outlook_active.mark_email_as_unread_voice("1"))

    print("\n--- Testing with Both, starting Gmail, then switching ---")
    handler_both = VoiceEmailHandler(gmail_service=mock_gmail_instance, outlook_service=mock_outlook_instance, initial_service_type='gmail')
    print(f"Initial service: {handler_both.active_service_type}")
    print(handler_both.fetch_unread_emails_voice(max_results=1)) 
    print(handler_both.read_email_voice("1")) 
    
    print(handler_both.switch_email_service('outlook'))
    print(f"Switched service: {handler_both.active_service_type}")
    print(handler_both.fetch_unread_emails_voice(max_results=1)) 
    print(handler_both.read_email_voice("1")) 
    print(handler_both.send_reply_voice("Test reply from switched Outlook service"))
    print(handler_both.mark_email_as_unread_voice("1")) 
    
    print(handler_both.switch_email_service('nonexistent')) 
    
    print(handler_both.switch_email_service('gmail')) 
    print(f"Switched back to: {handler_both.active_service_type}")
    print(handler_both.fetch_unread_emails_voice(max_results=1))
    print(handler_both.read_email_voice("1")) 
    print(handler_both.send_reply_voice("Test reply from switched back Gmail service"))
