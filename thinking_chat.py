import openai
import os
from typing import List, Dict, Any, Tuple
import config
import streamlit as st # For accessing session_state
from email_utils import authenticate_gmail, list_emails, read_email # Gmail functions

class ThinkingChat:
    def __init__(self):
        """Initialize the ThinkingChat class."""
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.THINKING_MODEL
        self.messages = []
        self.thinking_history = []
        
        # Load the planner prompt
        with open("prompts/planner_prompt.txt", "r") as f:
            self.planner_prompt = f.read()

    def handle_email_query(self, user_query: str) -> Tuple[str, str]:
        """Handles email-related queries by interacting with email_utils."""
        plan = "Plan: Process email-related query.\n"
        
        if not hasattr(st.session_state, 'gmail_service') or not st.session_state.gmail_service:
            plan += "1. Check Gmail authentication status: Not authenticated.\n"
            plan += "2. Respond to user: Advise to connect to Gmail via UI."
            return plan, "Please connect to Gmail first through the UI before I can help with emails."

        plan += "1. Check Gmail authentication status: Authenticated.\n"
        service = st.session_state.gmail_service
        query_lower = user_query.lower()

        try:
            if "read email" in query_lower:
                # Attempt to extract email ID. This is a very basic extraction.
                # Example: "read email id 12345abc" or "read email with id 12345abc"
                parts = query_lower.split()
                email_id = None
                for i, part in enumerate(parts):
                    if part == "id" and i + 1 < len(parts):
                        email_id = parts[i+1]
                        break
                    # if it's just "read email <id>"
                    if part == "email" and i + 1 < len(parts) and "id" not in query_lower :
                         # check if parts[i+1] could be an id (alphanumeric)
                         if parts[i+1].isalnum() and len(parts[i+1]) > 10 : # Basic check for typical ID format
                            email_id = parts[i+1]
                            break
                
                if email_id:
                    plan += f"2. Parse intent: Read email with ID '{email_id}'.\n"
                    plan += f"3. Call email_utils.read_email for ID '{email_id}'.\n"
                    email_content = read_email(service, email_id)
                    if email_content:
                        plan += "4. Format email content for display."
                        response = f"Subject: {email_content['subject']}\nFrom: {email_content['from']}\n\nBody:\n{email_content['body']}"
                        return plan, response
                    else:
                        plan += "4. Email not found or error reading email."
                        return plan, f"Could not read email with ID '{email_id}'. Please check the ID or try again."
                else:
                    plan += "2. Parse intent: Read email, but ID not found in query.\n"
                    plan += "3. Respond to user: Ask for email ID."
                    return plan, "Please specify the ID of the email you want to read. For example: 'read email id <your_email_id>'"

            elif "list emails" in query_lower or "search email" in query_lower or "find email" in query_lower:
                plan += "2. Parse intent: List/Search emails.\n"
                # Basic query extraction, assumes the part after "list emails" or "search emails" is the query for Gmail
                search_terms = ""
                if "list emails" in query_lower:
                    search_terms = query_lower.split("list emails", 1)[-1].strip()
                    if not search_terms or search_terms == "latest": # Default for "list my latest emails"
                        search_terms = "is:unread" # Default to unread, or you can use "" for all
                elif "search email" in query_lower:
                     search_terms = query_lower.split("search email", 1)[-1].strip()
                     if "for" in search_terms and search_terms.startswith("for "):
                         search_terms = search_terms.split("for ",1)[-1].strip()

                elif "find email" in query_lower:
                    search_terms = query_lower.split("find email", 1)[-1].strip()
                    if "for" in search_terms and search_terms.startswith("for "):
                         search_terms = search_terms.split("for ",1)[-1].strip()


                # Simple max_results extraction, e.g., "list 5 latest emails"
                max_results = 5 # Default
                parts = query_lower.split()
                for i, part in enumerate(parts):
                    if part.isdigit() and i > 0 and parts[i-1] in ["list", "show", "get", "fetch"]:
                        max_results = int(part)
                        break
                
                plan += f"3. Determine search query: '{search_terms if search_terms else 'all emails'}' with max results: {max_results}.\n"
                plan += f"4. Call email_utils.list_emails.\n"
                
                emails = list_emails(service, query=search_terms if search_terms else "", max_results=max_results)
                if emails:
                    response_lines = [f"Found {len(emails)} emails:"]
                    for i, mail_info in enumerate(emails):
                        # Fetch subject and sender for each email for a better summary
                        # This adds more API calls but is more user-friendly.
                        # Consider optimizing if performance becomes an issue.
                        try:
                            msg_preview = service.users().messages().get(userId='me', id=mail_info['id'], format='metadata', metadataHeaders=['Subject', 'From']).execute()
                            subject = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
                            sender = next((header['value'] for header in msg_preview['payload']['headers'] if header['name'] == 'From'), 'Unknown Sender')
                            response_lines.append(f"{i+1}. Subject: {subject} | From: {sender} (ID: {mail_info['id']})")
                        except Exception as e:
                            response_lines.append(f"{i+1}. Could not fetch details for email ID: {mail_info['id']}. Error: {e}")
                    plan += "5. Format list of emails for display."
                    return plan, "\n".join(response_lines)
                elif emails == []: # Explicitly check for empty list
                    plan += "5. No emails found matching criteria."
                    return plan, "No emails found matching your criteria."
                else: # emails is None, indicating an error in list_emails
                    plan += "5. Error occurred while listing emails."
                    return plan, "Sorry, I couldn't retrieve your emails at the moment. There might have been an error."
            else:
                plan += "2. Parse intent: Unknown email action.\n"
                plan += "3. Respond to user: Inform that the specific email query is not understood."
                return plan, "I can help with listing or reading emails. For example, try 'list my 5 latest unread emails' or 'read email id <email_id>'."

        except Exception as e:
            error_message = f"An error occurred while handling email query: {str(e)}"
            print(error_message) # Log to console
            plan += f"X. Error encountered: {error_message}"
            return plan, f"Sorry, I encountered an error while processing your email request: {e}"

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat history."""
        self.messages.append({"role": role, "content": content})
    
    def add_thinking(self, content: str) -> None:
        """Add a thinking step to the thinking history."""
        self.thinking_history.append(content)
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages in the chat history."""
        return self.messages
    
    def get_thinking_history(self) -> List[str]:
        """Get the thinking history."""
        return self.thinking_history
    
    def clear_messages(self) -> None:
        """Clear all messages in the chat history."""
        self.messages = []
        self.thinking_history = []
    
    def generate_thinking_plan(self, user_input: str) -> str:
        """Generate a thinking plan for the user input."""
        try:
            # Create messages for the planning step
            planning_messages = [
                {"role": "system", "content": self.planner_prompt},
                {"role": "user", "content": user_input}
            ]
            
            # Send the planning request to OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=planning_messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract the thinking plan
            thinking_plan = response.choices[0].message.content
            
            # Add to thinking history
            self.add_thinking(thinking_plan)
            
            return thinking_plan
        
        except Exception as e:
            error_message = f"Error generating thinking plan: {str(e)}"
            print(error_message)
            self.add_thinking(error_message)
            return error_message
    
    def generate_final_response(self, user_input: str, thinking_plan: str) -> str:
        """Generate the final response based on the thinking plan."""
        try:
            # Create messages for the final response
            system_prompt = f"""You are a helpful assistant. Use the following thinking plan to guide your response to the user:

{thinking_plan}

Respond directly to the user's query using this plan, but do NOT mention that you're following a plan or include the plan in your response."""
            
            final_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            # Send the final response request to OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=final_messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Extract the final response
            final_response = response.choices[0].message.content
            
            return final_response
        
        except Exception as e:
            error_message = f"Error generating final response: {str(e)}"
            print(error_message)
            return error_message
    
    def process_message(self, user_input: str) -> Tuple[str, str]:
        """Process user input through the thinking process and generate a response."""
        self.add_message("user", user_input)

        # Check for email-related keywords
        email_keywords = ["email", "gmail", "mail", "inbox", "message", "sender", "subject"]
        is_email_query = any(keyword in user_input.lower() for keyword in email_keywords)

        if is_email_query:
            # Handle email query
            thinking_plan, final_response = self.handle_email_query(user_input)
            self.add_message("system", thinking_plan) # Log the plan from email_handler
            self.add_message("assistant", final_response)
            return thinking_plan, final_response
        else:
            # Original non-email processing
            thinking_plan = self.generate_thinking_plan(user_input)
            self.add_message("system", thinking_plan)
            final_response = self.generate_final_response(user_input, thinking_plan)
            self.add_message("assistant", final_response)
            return thinking_plan, final_response