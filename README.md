# 🛡️ Vault Guardian

An advanced, agentic AI Telegram bot designed for Instagram influencers to track earnings and expenses with high precision and natural language processing.

## 🚀 Key Features

-   **Natural Language Processing**: Powered by NVIDIA NIM, the bot understands complex financial sentences (e.g., *"Received 50k from Nike for 2 reels yesterday"*).
-   **Fully Asynchronous Architecture**: Built with `python-telegram-bot` and `SQLAlchemy (Async)` with `aiosqlite` for non-blocking operations.
-   **Persistent Multi-Turn Confirmations**: Operations requiring user approval (like deletions or fuzzy brand matches) are stored in the database, remaining valid even if the bot restarts.
-   **Intelligent Brand Matching**: Fuzzy logic handles variations in brand names and asks *"Did you mean?"* to prevent data fragmentation.
-   **Automated Reporting**: Generates comprehensive PDF and Excel reports of your financial health.
-   **Safety First**: Built-in audit logging, chat ID validation, and Pydantic-powered tool validation.

## 🛠️ Tech Stack

-   **Language**: Python 3.14+
-   **Bot Framework**: `python-telegram-bot` (Async)
-   **AI Orchestration**: OpenAI-compatible API (NVIDIA NIM)
-   **Database**: SQLite with `SQLAlchemy 2.0` (Async/aiosqlite)
-   **Data Validation**: `Pydantic v2`
-   **Utilities**: `fuzzywuzzy` for matching, `reportlab` & `openpyxl` for reporting.

## 📦 Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/vineetkishore01/Vault-Guardian.git
    cd Vault-Guardian
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure environment:**
    Create a `.env` file based on `.env.example`:
    ```env
    TELEGRAM_BOT_TOKEN=your_token
    ALLOWED_CHAT_ID=your_id
    LLM_API_KEY=your_nvidia_nim_key
    LLM_BASE_URL=https://integrate.api.nvidia.com/v1
    LLM_MODEL=z-ai/glm4.7
    ```

4.  **Run the bot:**
    ```bash
    python -m src.main
    ```

## 📖 Usage Examples

-   **Adding Data**: *"Add 1.2 lakh from Amazon for 1 reel and 3 stories"*
-   **Tracking Expenses**: *"Spent rs 1500 on taxi for shoot"*
-   **Querying**: *"How much did I earn this month?"*
-   **Reporting**: *"Send me a PDF report for last 3 months"*
-   **Management**: *"Delete my last entry for Lakme"*

## 🛡️ Engineering Standards

Vault Guardian follows strict engineering principles:
-   **Strict Input Validation**: Every tool call is validated against Pydantic schemas.
-   **Audit Trails**: Every database mutation is logged in the `audit_log` table.
-   **Transactional Safety**: Uses context managers for database sessions to ensure atomic operations.
-   **Scalability**: Async event loop ensures the bot handles multiple concurrent events without lag.

## 📄 License

MIT License. See `LICENSE` for details.
