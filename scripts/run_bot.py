#!/usr/bin/env python3
"""
Entry point script for running the Telegram bot.

This script initializes the Avito API authentication, creates the API client,
and starts the Telegram bot with all necessary handlers.
"""
import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telegram.ext import Application

from src.api.avito_api_client import AvitoApiClient
from src.api.avito_auth import AvitoAuth
from src.bot.telegram_bot import register_handlers

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Avito Rental Assistant Telegram Bot")
    parser.add_argument(
        "--env-file", type=str, default=".env", help="Path to the .env file (default: .env)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    return parser.parse_args()


async def initialize_services():
    """Initialize Avito authentication and API client."""
    logger.info("Initializing Avito authentication...")
    try:
        avito_auth = AvitoAuth()
        # Fetch token and user_id
        await avito_auth.get_access_token()
        logger.info("Avito authentication initialized successfully")

        logger.info("Initializing Avito API client...")
        avito_api_client = AvitoApiClient(avito_auth_instance=avito_auth)
        logger.info(f"Avito API client initialized for user_id: {avito_api_client.user_id}")

        return avito_auth, avito_api_client
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise


async def main():
    """Main entry point for the Telegram bot."""
    args = parse_arguments()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Load environment variables
    env_path = os.path.abspath(args.env_file)
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        logger.warning(f"Environment file not found: {env_path}")

    # Get bot token
    bot_token = os.getenv("AVITO_TG_BOT_TOKEN")
    if not bot_token:
        logger.error("AVITO_TG_BOT_TOKEN not found in environment variables")
        sys.exit(1)

    # Initialize services
    try:
        avito_auth, avito_api_client = await initialize_services()
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        sys.exit(1)

    # Create Telegram application
    logger.info("Creating Telegram application...")
    application = Application.builder().token(bot_token).build()

    # Register handlers
    logger.info("Registering bot handlers...")
    register_handlers(application, avito_auth, avito_api_client)

    # Start the bot
    logger.info("Starting Telegram bot...")
    logger.info("Bot is now running. Press Ctrl+C to stop.")

    try:
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    # Import Update here to avoid circular imports
    from telegram import Update

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
