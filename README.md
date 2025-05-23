# LLM Dual Brain - Thinking Chat vs. Direct Chat

A Streamlit application that demonstrates two different approaches to LLM interactions:
- **Thinking Chat**: The LLM first plans its approach before responding
- **Direct Chat**: The LLM responds directly without explicit planning

## 📋 Requirements

- Python 3.7+
- OpenAI API key

## 🚀 Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd llm-dual-brain
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## 🏃‍♂️ Running the Application

Start the Streamlit application:
```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501` in your web browser.

## 🧠 How It Works

### Thinking Chat
1. The user input is sent to the LLM with a "thinking planner" system prompt.
2. The LLM generates a plan outlining how to approach answering the query.
3. This plan is used as guidance for a second LLM call that generates the final response.

### Direct Chat
1. The user input is sent directly to the LLM.
2. The LLM responds without any intermediate planning step.

## 📊 Project Structure

```
llm_dual_chat/
│
├── app.py                  # Main Streamlit app
├── thinking_chat.py        # Logic for planning + response
├── direct_chat.py          # Logic for direct chat
├── utils.py                # Helper functions
├── config.py               # OpenAI keys, settings
├── prompts/
│   └── planner_prompt.txt  # Base prompt for planning
├── logs/
│   └── chat_history.json   # Chat history storage
└── requirements.txt        # Dependencies
```

## 🔍 Features

- Side-by-side comparison of thinking-based and direct responses
- Expandable thinking process display
- Chat history logging and export
- Clear chat functionality

## ⚙️ Configuration

You can adjust the following settings in `config.py`:
- LLM models used for each chat type
- Logging configuration
- Log file path 

## 📧 Gmail Integration

This application supports integration with your Gmail account to allow the `ThinkingChat` to list and read your emails.

### Setup for Gmail Integration

1.  **Enable the Gmail API & Download Credentials**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the "Gmail API" for your project. You can find this in the "APIs & Services" > "Library" section.
    *   Go to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" and choose "OAuth 2.0 Client ID".
    *   Select "Desktop app" as the application type.
    *   After creation, download the JSON file. Rename this file to `credentials.json`.
    *   For more detailed steps, refer to the official Google documentation for [setting up OAuth 2.0](https://developers.google.com/workspace/guides/create-credentials) and [using API keys](https://support.google.com/googleapi/answer/6158862) (though for this app, OAuth 2.0 is used).

2.  **Place `credentials.json`**:
    *   Place the downloaded `credentials.json` file in the root directory of the project, or in the path you specify in your `.env` file (see next step).

3.  **Configure Environment Variables**:
    *   Add the following variables to your `.env` file:
        ```env
        # For Gmail API
        GMAIL_CREDENTIALS_PATH=credentials.json  # Path to your credentials file
        GMAIL_TOKEN_PATH=token.json              # Path where the auth token will be saved
        GMAIL_CLIENT_ID=your_google_client_id    # From your credentials.json
        GMAIL_CLIENT_SECRET=your_google_client_secret # From your credentials.json
        GMAIL_ADDRESS=your_email@gmail.com       # The Gmail address you want to access
        ```
    *   You can find `your_google_client_id` and `your_google_client_secret` inside the `credentials.json` file (usually under the `installed` key).

4.  **Install Required Libraries**:
    *   The necessary Google client libraries are listed in `requirements.txt` (`google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`).
    *   If you haven't already, install them by running:
        ```bash
        pip install -r requirements.txt
        ```

5.  **Token Generation (`token.json`)**:
    *   The `token.json` file (its path is specified by `GMAIL_TOKEN_PATH` in your `.env` file) stores your OAuth 2.0 access and refresh tokens.
    *   This file will be created automatically in the specified path after you successfully authenticate with Gmail through the application's UI for the first time. You will be prompted to go through Google's authentication flow in your browser.

### Using Gmail Integration

Once set up, you can interact with your Gmail account in two ways:

1.  **Through the User Interface (UI)**:
    *   A new "Gmail Integration" section will appear in the application.
    *   Click the "🔗 Connect to Gmail" button. This will open a new tab in your browser for Google authentication.
    *   After successful authentication, the UI will show "✅ Connected to Gmail".
    *   You can then use the input field to search your emails (e.g., `is:unread from:someone@example.com`) and click "🔍 Search Emails".
    *   The search results will be displayed, and you can click "Read Email" for any specific email to view its content.

2.  **Through the `ThinkingChat`**:
    *   If you are connected to Gmail, you can ask the `ThinkingChat` to perform email actions. Examples:
        *   `"list my 5 latest unread emails"`
        *   `"search emails from news@example.com"`
        *   `"read email with id <actual_email_id_here>"` (you can get email IDs from the list command)
    *   The `ThinkingChat` will use your authenticated Gmail connection to fetch and display the information.