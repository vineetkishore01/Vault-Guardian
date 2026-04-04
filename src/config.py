"""Configuration management module."""
import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class TelegramConfig(BaseSettings):
    """Telegram bot configuration."""
    bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    allowed_chat_id: str = Field(..., env="ALLOWED_CHAT_ID")


class LLMConfig(BaseSettings):
    """LLM configuration."""
    provider: str = "openai_compatible"
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 16384
    temperature: float = 1.0
    top_p: float = 1.0
    seed: int = 42
    stream: bool = False
    timeout: Optional[int] = None
    max_retries: int = 3
    retry_delay: int = 1
    enable_thinking: bool = True
    clear_thinking: bool = False

    class Config:
        env_prefix = "LLM_"
        extra = "ignore"


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    path: str = Field(default="./data/vault_guardian.db", env="DATABASE_PATH")
    timezone: str = "Asia/Kolkata"


class AnalyticsConfig(BaseSettings):
    """Analytics configuration."""
    default_currency: str = "INR"
    chart_style: str = "professional"
    max_report_entries: int = 10000


class RemindersConfig(BaseSettings):
    """Reminders configuration."""
    enabled: bool = True
    default_reminder_days: int = 7
    check_interval: str = "0 9 * * *"


class SecurityConfig(BaseSettings):
    """Security configuration."""
    rate_limit_per_minute: int = 30
    max_message_length: int = 4000
    log_level: str = "INFO"
    audit_log_enabled: bool = True


class BotConfig(BaseSettings):
    """Bot configuration."""
    notify_on_restart: bool = True
    typing_indicator_enabled: bool = True
    confirmation_required: bool = True
    error_notification: str = "immediate"


class DataRetentionConfig(BaseSettings):
    """Data retention configuration."""
    keep_all_data: bool = True
    backup_strategy: str = "manual"


class Config:
    """Main configuration class."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        
        self.config_path = config_path
        self._load_yaml_config()
        self._load_env_configs()
    
    def _load_yaml_config(self):
        """Load YAML configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            content = f.read()
            # Expand environment variables like ${VAR}
            content = self._expand_env_vars(content)
            yaml_config = yaml.safe_load(content)

        self.telegram = TelegramConfig(**yaml_config.get('telegram', {}))
        self.llm = LLMConfig(**yaml_config.get('llm', {}))
        self.database = DatabaseConfig(**yaml_config.get('database', {}))
        self.analytics = AnalyticsConfig(**yaml_config.get('analytics', {}))
        self.reminders = RemindersConfig(**yaml_config.get('reminders', {}))
        self.security = SecurityConfig(**yaml_config.get('security', {}))
        self.bot = BotConfig(**yaml_config.get('bot', {}))
        self.data_retention = DataRetentionConfig(**yaml_config.get('data_retention', {}))

    def _expand_env_vars(self, content: str) -> str:
        """Expand environment variables in string."""
        import re
        
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))
        
        # Matches ${VAR} or $VAR
        pattern = re.compile(r'\$\{(\w+)\}|\$(\w+)')
        return pattern.sub(replace_var, content)

    def _load_env_configs(self):
        """Load environment variable overrides."""
        env_vars = {
            'telegram': {'bot_token': 'TELEGRAM_BOT_TOKEN', 'allowed_chat_id': 'ALLOWED_CHAT_ID'},
            'database': {'path': 'DATABASE_PATH'}
        }

        for section, var_mapping in env_vars.items():
            section_config = getattr(self, section)
            for attr, env_var in var_mapping.items():
                env_value = os.getenv(env_var)
                if env_value:
                    setattr(section_config, attr, env_value)


# Global configuration instance
config = Config()