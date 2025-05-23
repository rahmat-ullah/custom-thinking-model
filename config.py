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