#!/usr/bin/env python3
"""
Entry point script for running the guest chat interface.

This script starts the interactive chat interface for guests to inquire
about apartment rentals using Ollama LLM with RAG capabilities.
"""
import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.guest_chat import main as chat_main

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the Avito Rental Assistant Guest Chat Interface"
    )
    parser.add_argument(
        "--env-file", type=str, default=".env", help="Path to the .env file (default: .env)"
    )
    parser.add_argument(
        "--apartment-info-dir",
        type=str,
        default="data/apartment_info",
        help="Directory containing apartment information files (default: data/apartment_info)",
    )
    parser.add_argument(
        "--prompts-dir",
        type=str,
        default="data/prompts",
        help="Directory containing prompt files (default: data/prompts)",
    )
    parser.add_argument(
        "--mcp-server-url",
        type=str,
        default="http://127.0.0.1:8314/mcp",
        help="MCP server URL (default: http://127.0.0.1:8314/mcp)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    return parser.parse_args()


def validate_directories(apartment_info_dir, prompts_dir):
    """Validate that required directories exist."""
    if not os.path.exists(apartment_info_dir):
        logger.warning(f"Apartment info directory not found: {apartment_info_dir}")
        logger.info(f"Creating directory: {apartment_info_dir}")
        os.makedirs(apartment_info_dir, exist_ok=True)

    if not os.path.exists(prompts_dir):
        logger.warning(f"Prompts directory not found: {prompts_dir}")
        logger.info(f"Creating directory: {prompts_dir}")
        os.makedirs(prompts_dir, exist_ok=True)

    # Check for required prompt files
    system_prompt_file = os.path.join(prompts_dir, "system_prompt_employee.txt")
    few_shot_file = os.path.join(prompts_dir, "few_shot_examples.json")

    if not os.path.exists(system_prompt_file):
        logger.warning(f"System prompt file not found: {system_prompt_file}")
        logger.info("The chat will not work properly without a system prompt file.")

    if not os.path.exists(few_shot_file):
        logger.warning(f"Few-shot examples file not found: {few_shot_file}")
        logger.info("The chat may be less predictable without few-shot examples.")


async def run_chat():
    """Run the guest chat interface."""
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

    # Set environment variables for the chat module
    os.environ["APARTMENT_INFO_DIR"] = args.apartment_info_dir
    os.environ["PROMPTS_DIR"] = args.prompts_dir
    os.environ["MCP_SERVER_URL"] = args.mcp_server_url

    # Validate directories
    validate_directories(args.apartment_info_dir, args.prompts_dir)

    logger.info("Starting guest chat interface...")
    logger.info(f"Apartment info directory: {args.apartment_info_dir}")
    logger.info(f"Prompts directory: {args.prompts_dir}")
    logger.info(f"MCP server URL: {args.mcp_server_url}")

    try:
        # Run the chat main function
        await chat_main()
    except KeyboardInterrupt:
        logger.info("Chat interface stopped by user")
    except Exception as e:
        logger.error(f"Chat interface encountered an error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(run_chat())
    except KeyboardInterrupt:
        logger.info("Chat stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
