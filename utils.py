import json
import os
from datetime import datetime
from typing import List, Dict, Any

def ensure_directory_exists(directory_path: str) -> None:
    """Ensure that the specified directory exists."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def save_chat_history(chat_history: List[Dict[str, Any]], file_path: str) -> None:
    """Save the chat history to a JSON file."""
    ensure_directory_exists(os.path.dirname(file_path))
    
    # Add timestamp to each entry if not already present
    for entry in chat_history:
        if "timestamp" not in entry:
            entry["timestamp"] = datetime.now().isoformat()
    
    try:
        with open(file_path, 'w') as f:
            json.dump(chat_history, f, indent=2)
    except Exception as e:
        print(f"Error saving chat history: {e}")

def load_chat_history(file_path: str) -> List[Dict[str, Any]]:
    """Load chat history from a JSON file."""
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

def format_message_for_display(message: Dict[str, str]) -> str:
    """Format a message for display in the UI."""
    role = message.get("role", "")
    content = message.get("content", "")
    
    if role == "user":
        return f"You: {content}"
    elif role == "assistant":
        return f"Assistant: {content}"
    elif role == "system":
        return f"System: {content}"
    else:
        return content 