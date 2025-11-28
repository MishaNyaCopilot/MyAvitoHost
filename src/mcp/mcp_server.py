"""
MCP (Model Context Protocol) Server Module

This module implements a FastMCP server that bridges the guest chat interface
with the Telegram bot. It provides tools for sending rental request notifications
when guests express check-in intentions during chat conversations.

The server exposes a notification tool that can be called by the chat interface
to alert landlords about guest check-in requests.
"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("Apartment Rental Notifier")


@mcp.tool()
async def notify_rental_request(
    apartment_address: str, check_in_time: str
) -> dict:  # Changed return type to dict
    """
    Receives apartment rental request details and simulates sending a notification.
    In a real scenario, this would send a message to a Telegram bot.
    """
    notification_message = (
        f"Guest wants to check in to apartment at: {apartment_address} " f"at {check_in_time}."
    )
    print(f"Simulating Telegram Notification: {notification_message}")
    # Placeholder for actual Telegram bot integration
    # import telegram
    # bot = telegram.Bot(token="YOUR_TELEGRAM_BOT_TOKEN")
    # await bot.send_message(chat_id="YOUR_CHAT_ID", text=notification_message)
    return {
        "status": "success",
        "message": f"Notification simulated for: {apartment_address} at {check_in_time}",
    }  # Return a dictionary


# Add a health check endpoint for debugging
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    print("Health check endpoint hit!")
    return PlainTextResponse("OK")


if __name__ == "__main__":
    print("Starting FastMCP server...")
    mcp.run(
        transport="streamable-http", host="127.0.0.1", port=8314, path="/mcp"
    )  # Updated port to 8314
