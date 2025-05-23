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