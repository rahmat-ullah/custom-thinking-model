import openai
import os
from typing import List, Dict, Any, Tuple
import config

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
        # Add user message to history
        self.add_message("user", user_input)
        
        # Generate thinking plan
        thinking_plan = self.generate_thinking_plan(user_input)
        
        # Add system message with thinking plan
        self.add_message("system", thinking_plan)
        
        # Generate final response
        final_response = self.generate_final_response(user_input, thinking_plan)
        
        # Add assistant's response to history
        self.add_message("assistant", final_response)
        
        return thinking_plan, final_response 