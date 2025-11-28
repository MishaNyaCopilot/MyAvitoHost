#!/usr/bin/env python3
"""
Entry point script for running the MCP (Model Context Protocol) server.

This script starts the FastMCP server that bridges the guest chat interface
with the Telegram bot for sending notifications.
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mcp.mcp_server import mcp

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Avito Rental Assistant MCP Server")
    parser.add_argument(
        "--env-file", type=str, default=".env", help="Path to the .env file (default: .env)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8314, help="Port to bind the server to (default: 8314)"
    )
    parser.add_argument(
        "--path", type=str, default="/mcp", help="URL path for the MCP endpoint (default: /mcp)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    return parser.parse_args()


def main():
    """Main entry point for the MCP server."""
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

    # Log server configuration
    logger.info("Starting MCP server...")
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Path: {args.path}")
    logger.info(f"Full URL: http://{args.host}:{args.port}{args.path}")

    try:
        # Run the MCP server
        mcp.run(transport="streamable-http", host=args.host, port=args.port, path=args.path)
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server encountered an error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
