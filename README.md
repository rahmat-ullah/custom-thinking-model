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

You can adjust the following settings in `config.py` or your `.env` file:
- LLM models used for each chat type
- Logging configuration
- Log file path
- Email service credentials (see below)

## 📧 Email Integration

This application supports integration with your Gmail and Outlook (Microsoft 365) accounts to allow reading, listing, and replying to emails via voice and text commands.

### Setup for Gmail Integration

1.  **Enable the Gmail API & Download Credentials**:
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the "Gmail API" for your project (APIs & Services > Library).
    *   Go to "APIs & Services" > "Credentials".
    *   Click "Create Credentials" > "OAuth 2.0 Client ID".
    *   Select "Desktop app" as the application type.
    *   Download the JSON credentials file and rename it to `credentials.json`.
    *   Detailed Google guide: [Setting up OAuth 2.0](https://developers.google.com/workspace/guides/create-credentials).

2.  **Place `credentials.json`**:
    *   Place `credentials.json` in the project root, or the path specified in `GMAIL_CREDENTIALS_PATH`.

3.  **Configure Environment Variables for Gmail**:
    *   Add to your `.env` file:
        ```env
        # For Gmail API
        GMAIL_CREDENTIALS_PATH=credentials.json
        GMAIL_TOKEN_PATH=token.json
        GMAIL_CLIENT_ID=your_google_client_id        # Inside credentials.json
        GMAIL_CLIENT_SECRET=your_google_client_secret  # Inside credentials.json
        # GMAIL_ADDRESS=your_email@gmail.com         # Optional: Can be set if needed by specific utilities
        ```

4.  **Token Generation (`token.json`) for Gmail**:
    *   `token.json` stores your OAuth 2.0 tokens and is created automatically after you first authenticate with Gmail via the app's UI.

### Setup for Outlook (Microsoft Graph) Integration

1.  **Register an Application in Azure Active Directory**:
    *   Go to the [Azure portal](https://portal.azure.com/).
    *   Navigate to "Azure Active Directory" > "App registrations".
    *   Click "+ New registration".
    *   Give it a name (e.g., "VoiceEmailClient").
    *   Choose "Accounts in any organizational directory (Any Azure AD directory - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)" for broadest compatibility, or select a more restrictive option if appropriate.
    *   You do not need to configure a Redirect URI for the device code flow initially.
    *   After registration, note down the **Application (client) ID** and **Directory (tenant) ID**.
    *   Microsoft guide for app registration: [Quickstart: Register an application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

2.  **Enable Public Client Flow (for Device Authentication)**:
    *   In your app registration in Azure portal, go to "Authentication".
    *   Scroll down to "Advanced settings".
    *   Set "Allow public client flows" to **Yes**. This is necessary for device code flow.
    *   Save the changes.
    *   Reference: [Device code flow for native apps](https://learn.microsoft.com/en-us/entra/identity-platform/native-app-device-code-flow).

3.  **Client Secret (Optional but Recommended for Completeness)**:
    *   While the device code flow (a public client flow) does not strictly require a client secret to be embedded in the client application, some Microsoft Graph operations or future flow changes might. It's good practice to generate one if you plan to use `ConfidentialClientApplication` flows later or for other tools.
    *   In your app registration, go to "Certificates & secrets".
    *   Click "+ New client secret", give it a description, choose an expiry, and click "Add".
    *   **Important**: Copy the **Value** of the secret immediately. It will not be shown again.

4.  **Configure Environment Variables for Outlook**:
    *   Add to your `.env` file:
        ```env
        # For Outlook (Microsoft Graph) API
        OUTLOOK_CLIENT_ID=your_outlook_application_client_id
        OUTLOOK_TENANT_ID=your_outlook_directory_tenant_id  # or 'common' for multi-tenant/personal
        OUTLOOK_CLIENT_SECRET=your_outlook_client_secret_value # Optional for device flow, but good to have
        ```

5.  **API Permissions (Microsoft Graph)**:
    *   In your app registration in Azure portal, go to "API permissions".
    *   Click "+ Add a permission" > "Microsoft Graph".
    *   Choose "Delegated permissions".
    *   Add the following permissions (at a minimum for current functionality):
        *   `Mail.ReadWrite` (to read, list, and mark emails as read/unread)
        *   `Mail.Send` (to send replies)
        *   `offline_access` (implicitly added or required for refresh tokens)
        *   `User.Read` (often default, good for basic user info)
    *   Click "Add permissions".
    *   Admin consent might be required for some permissions depending on your organization's settings.

### Connecting to Email Services in the App

1.  **Gmail**:
    *   In the application's sidebar, under "Email Services", click "🔗 Connect to Gmail".
    *   This will open a new browser tab for Google authentication. Follow the prompts.
    *   On success, the UI will show "✅ Gmail Connected".

2.  **Outlook**:
    *   In the sidebar, click "🔗 Connect to Outlook".
    *   The application will display a **device code** and a **verification URL** (usually `https://microsoft.com/devicelogin`).
    *   Open the URL in a browser, enter the provided code, and complete the Microsoft authentication and consent flow.
    *   The application will detect when authentication is complete (this step is blocking in the app).
    *   On success, the UI will show "✅ Outlook Connected".

### Switching Between Email Services

*   Once one or both services are connected, you can switch the *active* service for email commands.
*   Use voice commands:
    *   `"Switch to Outlook"` or `"Use Outlook"`
    *   `"Switch to Gmail"` or `"Use Gmail"`
*   The application will confirm the switch. The currently active service is also displayed in the sidebar.

### Using Email Commands

Once an email service is connected and active, you can use voice commands (if "Talking Mode" is enabled) or text commands to manage your emails. The application uses the `VoiceEmailHandler` to process these commands for the currently active service.

Examples of commands:
*   `"Fetch my unread emails"` (or `"check my email"`, `"get my 5 latest unread emails"`)
*   `"Read email number one"` (or `"read email from Jane Doe"`, `"open email with subject Meeting update"`)
*   `"Reply to this email"` (the app will then ask for your reply message)
*   `"Mark email two as read"`
*   `"Mark email from John as unread"`

The commands are designed to be consistent across both Gmail and Outlook. The application will indicate which service (Gmail or Outlook) is being used for the action.
The previous UI for searching and listing emails directly in the Streamlit interface has been deprecated in favor of voice/text commands.