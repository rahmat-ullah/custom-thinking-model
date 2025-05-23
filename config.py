import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Model configuration
THINKING_MODEL = "gpt-4o-mini"
DIRECT_MODEL = "gpt-3.5-turbo"

# Logging configuration
ENABLE_LOGGING = True
LOG_FILE_PATH = "logs/chat_history.json" 

# Gmail API credentials and settings
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "YOUR_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.json")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "wealthwaveofficialbiz@gmail.com")

# Outlook (Microsoft Graph) API configuration
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "YOUR_OUTLOOK_CLIENT_ID")
OUTLOOK_CLIENT_SECRET = os.getenv("OUTLOOK_CLIENT_SECRET", "YOUR_OUTLOOK_CLIENT_SECRET") # Needed for some flows like ConfidentialClientApplication
OUTLOOK_TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "YOUR_OUTLOOK_TENANT_ID") # Often 'common' or your specific tenant ID