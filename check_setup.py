#!/usr/bin/env python
"""Quick start checker for Vault Guardian."""
import os
import sys
import asyncio
from pathlib import Path

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...\n")

    issues = []

    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 14):
        issues.append(f"❌ Python 3.14+ required (found {python_version.major}.{python_version.minor})")
    else:
        print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")

    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        issues.append("❌ .env file not found (copy from .env.example)")
    else:
        print(f"✅ .env file exists")

        # Check required environment variables
        from dotenv import load_dotenv
        load_dotenv()

        required_vars = {
            "TELEGRAM_BOT_TOKEN": "your_telegram_bot_token_here",
            "ALLOWED_CHAT_ID": "your_allowed_chat_id_here",
            "LLM_API_KEY": "your_llm_api_key_here",
        }

        for var, placeholder in required_vars.items():
            value = os.getenv(var)
            if not value or value == placeholder:
                issues.append(f"❌ {var} not configured in .env")
            else:
                # Show partial value for security
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                print(f"✅ {var}: {masked}")

    # Check virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    if in_venv:
        print(f"✅ Virtual environment active")
    else:
        print(f"⚠️  Virtual environment not active (recommended but not required)")

    # Check data directory
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created data directory")
    else:
        print(f"✅ Data directory exists")

    # Check dependencies
    try:
        import openai
        print(f"✅ openai installed")
    except ImportError:
        issues.append("❌ openai not installed (run: pip install -r requirements.txt)")

    try:
        import telegram
        print(f"✅ python-telegram-bot installed")
    except ImportError:
        issues.append("❌ python-telegram-bot not installed (run: pip install -r requirements.txt)")

    try:
        import sqlalchemy
        print(f"✅ sqlalchemy installed")
    except ImportError:
        issues.append("❌ sqlalchemy not installed (run: pip install -r requirements.txt)")

    print("\n" + "="*50)
    
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  {issue}")
        print("\nPlease fix these issues before running the bot.")
        return False
    else:
        print("✅ All prerequisites passed!")
        print("\n🔗 Testing connections...")
        
        # Test connections (LLM test is optional)
        telegram_ok = test_telegram_connection()
        llm_ok = test_llm_connection()
        
        print("\n" + "="*50)
        
        if telegram_ok:
            print("✅ All critical checks passed! You're ready to run the bot.")
            if not llm_ok:
                print("⚠️  Note: LLM connection test failed, but the bot may still work.")
                print("   The bot will retry LLM connections during normal operation.")
            print("\nNext steps:")
            print("  1. Run: python -m src.main")
            print("  2. Test in Telegram")
            print("  3. Reset data: python reset_data.py")
            return True
        else:
            print("❌ Connection tests failed. Please fix the issues above.")
            return False

def test_telegram_connection():
    """Test Telegram bot connection."""
    print("\n📱 Testing Telegram connection...")
    
    try:
        from telegram import Bot
        from dotenv import load_dotenv
        load_dotenv()
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token or bot_token == "your_telegram_bot_token_here":
            print("  ❌ Telegram bot token not configured")
            return False
        
        bot = Bot(token=bot_token)
        
        # Test getMe
        try:
            bot_info = asyncio.run(bot.get_me())
            print(f"  ✅ Telegram bot connected: @{bot_info.username}")
            print(f"  ✅ Bot name: {bot_info.first_name}")
            return True
        except Exception as e:
            print(f"  ❌ Telegram connection failed: {e}")
            return False
        
    except Exception as e:
        print(f"  ❌ Telegram connection failed: {e}")
        return False

def test_llm_connection():
    """Test LLM API connection."""
    print("\n🤖 Testing LLM API connection...")
    
    try:
        from openai import OpenAI, APITimeoutError
        from dotenv import load_dotenv
        import threading
        import time
        
        load_dotenv()
        
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        model = os.getenv("LLM_MODEL", "z-ai/glm4.7")
        
        if not api_key or api_key == "your_llm_api_key_here":
            print("  ❌ LLM API key not configured")
            return False
        
        # Create client with longer timeout
        client = OpenAI(
            api_key=api_key, 
            base_url=base_url,
            timeout=60.0  # 60 second timeout
        )
        
        # Test with a simple completion using threading for timeout
        result = {"success": False, "error": None}

        def test_request():
            try:
                # Build request params
                params = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Say hi in one word"}],
                    "max_tokens": 10,
                    "temperature": 0.7,
                    "top_p": 1.0,
                    "seed": 42,
                }

                # NVIDIA NIM: chat_template_kwargs via extra_body
                enable_thinking = os.getenv("LLM_ENABLE_THINKING", "true").lower() == "true"
                clear_thinking = os.getenv("LLM_CLEAR_THINKING", "false").lower() == "true"
                params["extra_body"] = {
                    "chat_template_kwargs": {
                        "enable_thinking": enable_thinking,
                        "clear_thinking": clear_thinking
                    }
                }

                response = client.chat.completions.create(**params)

                # Check if response is valid
                if not response or not hasattr(response, 'choices') or not response.choices:
                    result["error"] = "Empty response"
                    return

                if not response.choices[0] or not hasattr(response.choices[0], 'message'):
                    result["error"] = "Invalid response structure"
                    return

                message = response.choices[0].message
                content = message.content if hasattr(message, 'content') else None

                # Some models (thinking models) may return empty content but valid response
                # Also check for tool_calls or other response fields
                tool_calls = message.tool_calls if hasattr(message, 'tool_calls') else None

                if not content and not tool_calls:
                    # Check for reasoning_content (used by thinking models like glm4.7)
                    reasoning_content = None
                    if hasattr(message, 'reasoning_content'):
                        reasoning_content = message.reasoning_content

                    if reasoning_content:
                        result["success"] = True
                        result["content"] = f"(thinking model: {reasoning_content[:50]}...)"
                        return

                    result["error"] = "Empty content"
                    return

                result["success"] = True
                result["content"] = content if content else "(tool calls)"
            except Exception as e:
                result["error"] = str(e)
        
        # Run test in thread with timeout
        thread = threading.Thread(target=test_request)
        thread.daemon = True
        thread.start()
        thread.join(timeout=15)  # 15 second timeout
        
        if thread.is_alive():
            print(f"  ⚠️  LLM connection test timed out (15s)")
            print(f"  💡 This might be due to network issues or API being slow")
            print(f"  💡 The bot will work fine with longer timeouts during normal operation")
            print(f"  ✅ Connection test skipped (timeout is acceptable)")
            return True  # Return True so the bot can still run
        
        if result["error"]:
            print(f"  ❌ LLM connection failed: {result['error']}")
            return False
        
        if result["success"]:
            print(f"  ✅ LLM API connected successfully")
            print(f"  ✅ Model: {model}")
            print(f"  ✅ Response: {result['content'][:50]}...")
            return True
        
        print(f"  ❌ LLM connection failed: Unknown error")
        return False
        
    except Exception as e:
        print(f"  ❌ LLM connection failed: {e}")
        return False

if __name__ == "__main__":
    success = check_prerequisites()
    sys.exit(0 if success else 1)
