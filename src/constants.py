"""
Constants Module

This module contains all hardcoded constants used throughout the application.
Centralizing constants here makes them easier to maintain and modify.
"""

# API URLs
AVITO_TOKEN_URL = "https://api.avito.ru/token"
AVITO_SELF_ACCOUNT_URL = "https://api.avito.ru/core/v1/accounts/self"
AVITO_API_BASE_URL = "https://api.avito.ru"

# File paths
TOKEN_CACHE_FILE = "avito_token_cache.json"

# Timing constants
TOKEN_EXPIRATION_BUFFER_MINUTES = 5

# Default values
DEFAULT_MCP_SERVER_URL = "http://127.0.0.1:8314/mcp"
DEFAULT_MCP_SERVER_HOST = "127.0.0.1"
DEFAULT_MCP_SERVER_PORT = 8314
DEFAULT_MCP_SERVER_PATH = "/mcp"

DEFAULT_APARTMENT_INFO_DIR = "data/apartment_info"
DEFAULT_PROMPTS_DIR = "data/prompts"

# Telegram bot constants
DEFAULT_USER_TELEGRAM_IDS = [1308241542]

# Retry configuration
API_REQUEST_RETRIES = 3
API_RETRY_BASE_DELAY = 1  # seconds
API_RATE_LIMIT_BACKOFF_BASE = 2  # seconds for exponential backoff

# Pagination defaults
DEFAULT_CHATS_LIMIT = 50
DEFAULT_MESSAGES_LIMIT = 50
DEFAULT_ITEMS_PER_PAGE = 100

# Chat types
DEFAULT_CHAT_TYPES = ["u2i", "u2u"]

# Booking sources
BOOKING_SOURCE_AVITO = "avito"
BOOKING_SOURCE_MANUAL = "manual"
BOOKING_SOURCE_PMS = "pms"
BOOKING_SOURCE_TELEGRAM_BOT = "telegram_bot_conversation"

# Property-based testing
PBT_MIN_ITERATIONS = 100
