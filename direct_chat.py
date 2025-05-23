import openai
from typing import List, Dict, Any
import config

class DirectChat:
    def __init__(self):
        """Initialize the DirectChat class."""
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.DIRECT_MODEL
        self.messages = []
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat history."""
        self.messages.append({"role": role, "content": content})
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get all messages in the chat history."""
        return self.messages
    
    def clear_messages(self) -> None:
        """Clear all messages in the chat history."""
        self.messages = []
    
    def process_message(self, user_input: str) -> str:
        """Process user input and generate a direct response."""
        # Add user message to history
        self.add_message("user", user_input)
        
        try:
            # Send the conversation to OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Extract the assistant's response
            assistant_response = response.choices[0].message.content
            
            # Add assistant's response to history
            self.add_message("assistant", assistant_response)
            
            return assistant_response
        
        except Exception as e:
            error_message = f"Error generating response: {str(e)}"
            print(error_message)
            self.add_message("system", error_message)
            return error_message 