import email_utils # To call Gmail API functions
from googleapiclient.errors import HttpError # Add this import
# We'll need audio_utils if we decide to make this handler speak directly,
# but for now, it will return text to be spoken by app.py
# import audio_utils

class VoiceEmailHandler:
    def __init__(self, gmail_service):
        self.gmail_service = gmail_service
        self.listed_emails = []  # Stores {'id': '...', 'subject': '...', 'from': '...'}
        self.current_email_content = None # Stores full content of the currently selected email
        self.current_email_id = None # ID of the currently selected email

    def fetch_unread_emails_voice(self, max_results=5):
        """
        Fetches unread emails, stores essential details, and returns a summary string for TTS.
        Only fetches a limited number of emails for the voice summary.
        """
        if not self.gmail_service:
            return "Gmail service is not available. Please connect to Gmail first."

        try:
            messages = email_utils.list_emails(self.gmail_service, query="is:unread", max_results=max_results)
            if messages is None: # Indicates an error from list_emails
                return "Sorry, I couldn't retrieve your unread emails at the moment."
            if not messages:
                return "You have no unread emails."

            self.listed_emails = [] # Clear previous list
            email_summaries = []
            for i, msg_data in enumerate(messages):
                # The list_emails function returns a list of message objects, each with an 'id'.
                # We need to fetch subject and sender for each to provide a useful summary.
                # This adds more API calls but is necessary for the desired UX.
                try:
                    msg_preview = self.gmail_service.users().messages().get(
                        userId='me', 
                        id=msg_data['id'], 
                        format='metadata', 
                        metadataHeaders=['Subject', 'From']
                    ).execute()
                    
                    subject = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
                    sender = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'From'), 'Unknown Sender')
                    
                    self.listed_emails.append({'id': msg_data['id'], 'subject': subject, 'from': sender, 'number': i + 1})
                    email_summaries.append(f"{i+1}. Subject: {subject}, From: {sender}")
                except Exception as e:
                    print(f"Error fetching details for message ID {msg_data.get('id')}: {e}")
                    # Add a placeholder if fetching details fails for one email
                    self.listed_emails.append({'id': msg_data['id'], 'subject': 'Error fetching subject', 'from': 'Unknown', 'number': i + 1})
                    email_summaries.append(f"{i+1}. Could not fetch details for an email.")


            if not self.listed_emails: # Should not happen if messages were found, but as a safeguard
                 return "No unread emails found or there was an issue fetching details."

            response_text = f"I found {len(self.listed_emails)} unread emails. Here are the latest ones: " + ". ".join(email_summaries)
            return response_text

        except HttpError as e:
            print(f"Google API HttpError in fetch_unread_emails_voice: {e}")
            if e.resp.status == 401:
                return "There's an issue with Gmail authentication. Please try reconnecting to Gmail via the user interface."
            elif e.resp.status == 403:
                return "I don't have the necessary permissions for that Gmail action. You might need to re-authenticate with updated permissions."
            return f"A Google API error occurred: {e.resp.status}. Please try again later."
        except Exception as e:
            print(f"An error occurred in fetch_unread_emails_voice: {e}")
            return f"Sorry, an unexpected error occurred while fetching your unread emails. Details: {str(e)}"

    def read_email_voice(self, email_identifier):
        """
        Reads a specific email based on its number in the list or part of subject/sender.
        Marks the email as read.
        Returns a string with the email content for TTS.
        """
        if not self.gmail_service:
            return "Gmail service is not available."
        if not self.listed_emails:
            return "You haven't listed any emails yet. Try asking to fetch unread emails first."

        target_email = None
        try:
            # Try to parse identifier as a number
            email_number = int(email_identifier)
            target_email = next((email for email in self.listed_emails if email['number'] == email_number), None)
        except ValueError:
            # Identifier is not a number, try matching subject or sender (simple partial match)
            identifier_lower = str(email_identifier).lower()
            for email in self.listed_emails:
                if identifier_lower in email['subject'].lower() or identifier_lower in email['from'].lower():
                    target_email = email
                    break
        
        if not target_email:
            return f"Sorry, I couldn't find an email matching '{email_identifier}'. Please try a number from the list or a more specific name/subject."

        self.current_email_id = target_email['id']
        try:
            email_content = email_utils.read_email(self.gmail_service, self.current_email_id)
            if not email_content:
                return f"Sorry, I could not read the content for email from {target_email['from']} with subject {target_email['subject']}."

            self.current_email_content = email_content # Store for potential reply

            # Mark as read
            email_utils.mark_email_as_read(self.gmail_service, self.current_email_id)
            
            # Prepare for TTS
            # Voice can be verbose, so consider summarizing or asking user if they want full body.
            # For now, reading subject, sender, and then body.
            response_text = f"Reading email from {email_content['from']}. Subject: {email_content['subject']}. Body: {email_content['body']}"
            return response_text

        except HttpError as e:
            print(f"Google API HttpError in read_email_voice for ID {self.current_email_id}: {e}")
            if e.resp.status == 401:
                return "There's an issue with Gmail authentication while trying to read. Please try reconnecting to Gmail."
            elif e.resp.status == 403:
                return "I don't have the necessary permissions to read that email. You might need to re-authenticate with updated permissions."
            elif e.resp.status == 404: # Not Found
                return f"Sorry, I could not find the email with ID {self.current_email_id} to read."
            return f"A Google API error occurred while reading the email: {e.resp.status}. Please try again later."
        except Exception as e:
            print(f"An error occurred in read_email_voice for ID {self.current_email_id}: {e}")
            return f"Sorry, an unexpected error occurred while reading the email. Details: {str(e)}"

    def prepare_reply_voice(self, reply_text):
        """
        Sends a reply to the currently selected email.
        Returns a confirmation string for TTS.
        """
        if not self.gmail_service:
            return "Gmail service is not available."
        if not self.current_email_id or not self.current_email_content:
            return "You haven't selected an email to reply to. Please read an email first."
        
        if not reply_text or not reply_text.strip():
            return "The reply message seems to be empty. Please provide your reply."

        try:
            sent_message = email_utils.reply_to_email(
                self.gmail_service,
                self.current_email_id,
                reply_text
            )
            if sent_message:
                # Clear current email context after replying, or ask user?
                # self.current_email_id = None
                # self.current_email_content = None
                return f"Okay, I've sent your reply to {self.current_email_content['from']} with subject {self.current_email_content['subject']}."
            else:
                return "Sorry, I couldn't send your reply. Please try again."
        except HttpError as e:
            print(f"Google API HttpError in prepare_reply_voice: {e}")
            if e.resp.status == 401:
                return "There's an issue with Gmail authentication while trying to reply. Please try reconnecting to Gmail."
            elif e.resp.status == 403:
                return "I don't have the necessary permissions to send a reply. You might need to re-authenticate with updated permissions."
            return f"A Google API error occurred while sending the reply: {e.resp.status}. Please try again later."
        except Exception as e:
            print(f"An error occurred in prepare_reply_voice: {e}")
            return f"Sorry, an unexpected error occurred while sending your reply. Details: {str(e)}"

if __name__ == '__main__':
    # This section is for basic testing and won't run when imported.
    # To test this properly, you'd need a mock Gmail service or actual credentials.
    print("VoiceEmailHandler module loaded. For testing, you would typically instantiate VoiceEmailHandler with a Gmail service object.")
    # Example (conceptual):
    # mock_service = {} # Replace with a mock or real Gmail service
    # handler = VoiceEmailHandler(mock_service)
    # print(handler.fetch_unread_emails_voice())
    # print(handler.read_email_voice("1")) # Assuming email '1' was listed
    # print(handler.prepare_reply_voice("This is a test reply."))
