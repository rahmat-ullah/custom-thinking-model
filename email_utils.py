import os.path
import base64
import email
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

import config

# Define the SCOPES. If modifying these, delete the token.json file.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate_gmail():
    """Authenticates with the Gmail API using OAuth 2.0."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(config.GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.GMAIL_TOKEN_PATH, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(config.GMAIL_TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

def list_emails(service, user_id='me', query='', max_results=10):
    """Lists emails based on specified criteria."""
    try:
        response = service.users().messages().list(userId=user_id, q=query, maxResults=max_results).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])
        
        # # The API might return a nextPageToken if there are more messages.
        # # You can use this token to get the next page of results.
        # while 'nextPageToken' in response:
        #     page_token = response['nextPageToken']
        #     response = service.users().messages().list(userId=user_id, q=query, maxResults=max_results, pageToken=page_token).execute()
        #     messages.extend(response['messages'])
            
        return messages
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def read_email(service, message_id, user_id='me'):
    """Reads the content of a specific email."""
    try:
        message = service.users().messages().get(userId=user_id, id=message_id, format='full').execute()
        payload = message['payload']
        headers = payload.get('headers') # Use .get() for safety
        parts = payload.get('parts')

        if not headers: # Handle case where headers might be missing in mock or malformed email
            print(f"DEBUG: Headers are missing or None for message {message_id}. Payload: {payload!r}")
            headers = [] # Default to empty list to avoid error with next()

        print(f"DEBUG: Headers for message {message_id}: {headers!r}") # Debug print

        subject = next((header['value'] for header in headers if header.get('name') == 'Subject'), 'No Subject Found')
        sender = next((header['value'] for header in headers if header.get('name') == 'From'), 'No Sender Found')

        body = ""
        if parts:
            for part in parts:
                mime_type = part.get('mimeType')
                part_body = part.get('body') # Get the body object for the part
                if mime_type == 'text/plain':
                    if part_body and 'data' in part_body: # Check if body and data exist
                        data = part_body.get('data')
                        if data: # Ensure data is not None or empty before decode
                            body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif mime_type == 'text/html':
                    # We can also extract HTML content if needed
                    # if part_body and 'data' in part_body:
                    #    data = part_body.get('data')
                    #    if data:
                    #       body += base64.urlsafe_b64decode(data).decode('utf-8')
                    pass # For now, prioritize plain text
        else: # If not multipart, try to get body directly
            payload_body = payload.get('body') # Get the body object for the payload
            if payload_body and 'data' in payload_body: # Check if body and data exist
                data = payload_body.get('data')
                if data: # Ensure data is not None or empty
                     body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return {'id': message_id, 'subject': subject, 'from': sender, 'body': body.strip()}

    except Exception as e:
        print(f"An error occurred while reading email {message_id}: {e!r}") # Use !r for detailed error
        return None

def reply_to_email(service, original_message_id, reply_body_text, user_id='me'):
    """Creates and sends a reply to a given email message.

    Args:
        service: Authorized Gmail API service instance.
        original_message_id: The ID of the message to reply to.
        reply_body_text: The plain text content of the reply.
        user_id: User's email address. The special value 'me'
        can be used to indicate the authenticated user.

    Returns:
        The sent message object if successful, None otherwise.
    """
    try:
        original_msg = service.users().messages().get(userId=user_id, id=original_message_id, format='metadata', metadataHeaders=['Subject', 'From', 'To', 'Cc', 'Message-ID', 'References']).execute()
        
        original_headers = original_msg['payload']['headers']
        original_subject = next((h['value'] for h in original_headers if h['name'].lower() == 'subject'), '')
        original_from = next((h['value'] for h in original_headers if h['name'].lower() == 'from'), '')
        original_to = next((h['value'] for h in original_headers if h['name'].lower() == 'to'), '')
        original_message_id_header = next((h['value'] for h in original_headers if h['name'].lower() == 'message-id'), '')

        reply_subject = original_subject
        if not reply_subject.lower().startswith("re:"):
            reply_subject = "Re: " + reply_subject

        # Determine the recipient of the reply
        # Typically, you reply to the address in the 'From' header of the original email.
        # If the original email was sent by the current user, they might be replying to 'To'
        # This logic can be complex depending on 'Reply-To' headers, etc.
        # For simplicity, we'll reply to the original sender.
        reply_to_address = original_from

        message = MIMEText(reply_body_text)
        message['to'] = reply_to_address
        # message['from'] = # Gmail automatically sets the from address to the authenticated user.
        message['subject'] = reply_subject
        message['In-Reply-To'] = original_message_id_header
        message['References'] = next((h['value'] for h in original_headers if h['name'].lower() == 'references'), '')
        if message['References']: # Add original message id to references if they exist
             message['References'] += f" {original_message_id_header}"
        else: # Start references with original message id
             message['References'] = original_message_id_header


        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message, 'threadId': original_msg['threadId']}
        
        sent_message = service.users().messages().send(userId=user_id, body=body).execute()
        print(f"Reply sent. Message ID: {sent_message['id']}")
        return sent_message
    except Exception as e:
        print(f"An error occurred while sending reply: {e}")
        return None

def mark_email_as_read(service, message_id, user_id='me'):
    """Marks a specific email as read by removing the 'UNREAD' label.

    Args:
        service: Authorized Gmail API service instance.
        message_id: The ID of the message to mark as read.
        user_id: User's email address. The special value 'me'
        can be used to indicate the authenticated user.
    Returns:
        The modified message object if successful, None otherwise.
    """
    try:
        body = {'removeLabelIds': ['UNREAD']}
        message = service.users().messages().modify(userId=user_id, id=message_id, body=body).execute()
        print(f"Message {message_id} marked as read.")
        return message
    except Exception as e:
        print(f"An error occurred while marking email as read: {e}")
        return None

def mark_email_as_unread(service, message_id, user_id='me'):
    """Marks a specific email as unread by adding the 'UNREAD' label.

    Args:
        service: Authorized Gmail API service instance.
        message_id: The ID of the message to mark as unread.
        user_id: User's email address. The special value 'me'
        can be used to indicate the authenticated user.
    Returns:
        The modified message object if successful, None otherwise.
    """
    try:
        body = {'addLabelIds': ['UNREAD']}
        message = service.users().messages().modify(userId=user_id, id=message_id, body=body).execute()
        print(f"Message {message_id} marked as unread.")
        return message
    except Exception as e:
        print(f"An error occurred while marking email as unread: {e}")
        return None

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    # Make sure credentials.json is in the correct path (config.GMAIL_CREDENTIALS_PATH)
    # and you've gone through the OAuth flow at least once.
    
    gmail_service = authenticate_gmail()

    if gmail_service:
        print("Successfully authenticated with Gmail.")
        
        # List unread emails from a specific sender
        # query_params = "is:unread from:example@example.com" 
        query_params = "is:unread" # Example: list all unread emails
        print(f"\nListing emails with query: '{query_params}'")
        emails = list_emails(gmail_service, query=query_params, max_results=5)
        
        if emails:
            print(f"Found {len(emails)} emails.")
            for email_info in emails:
                print(f"Email ID: {email_info['id']}")
                # Optionally, read the first email found
                if email_info['id']:
                    print("\nReading details for the first email found...")
                    email_content = read_email(gmail_service, email_info['id'])
                    if email_content:
                        print(f"ID: {email_content['id']}")
                        print(f"From: {email_content['from']}")
                        print(f"Subject: {email_content['subject']}")
                        print("Body:")
                        print(email_content['body'][:500] + "..." if len(email_content['body']) > 500 else email_content['body']) # Print first 500 chars
                    break # Read only the first one for this example
        else:
            print("No emails found matching your criteria or an error occurred.")
    else:
        print("Failed to authenticate with Gmail.")
