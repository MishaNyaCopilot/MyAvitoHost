"""
Avito API Client Module

This module provides a comprehensive client for interacting with the Avito API.
It handles all API requests including chat management, item (ad) operations,
booking management, and availability updates.

The client uses async/await for all operations and includes automatic retry
logic for transient failures and rate limiting.
"""

import asyncio
import json
import os

import httpx

from src.api.avito_auth import AvitoAuth
from src.constants import (
    API_RATE_LIMIT_BACKOFF_BASE,
    API_REQUEST_RETRIES,
    API_RETRY_BASE_DELAY,
    AVITO_API_BASE_URL,
    DEFAULT_CHATS_LIMIT,
    DEFAULT_CHAT_TYPES,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_MESSAGES_LIMIT,
)


class AvitoApiClient:
    """
    Comprehensive client for interacting with the Avito API.

    Provides methods for all major Avito API operations including chat management,
    item (ad) operations, booking management, and availability updates. All methods
    are async and include automatic retry logic for transient failures.

    Attributes:
        auth: AvitoAuth instance for authentication
        user_id: Avito user ID from the auth instance
        httpx_client: Async HTTP client for making requests
    """

    def __init__(self, avito_auth_instance: AvitoAuth):  # user_id parameter removed
        """
        Initializes the Avito API client.

        Args:
            avito_auth_instance: Authenticated AvitoAuth instance with user_id populated

        Raises:
            ValueError: If avito_auth_instance is None
            ConnectionError: If user_id is not available on the auth instance
        """
        if not avito_auth_instance:
            raise ValueError("AvitoAuth instance is required.")
        self.auth = avito_auth_instance
        # user_id is now expected to be populated on AvitoAuth instance
        # after get_access_token() has been called (which also fetches user_id).
        self.user_id = self.auth.user_id

        if not self.user_id:
            # This is a critical issue if user_id could not be fetched by AvitoAuth
            # or was not pre-loaded by an explicit call to auth.get_access_token().
            raise ConnectionError(
                "AvitoApiClient: User ID not found on AvitoAuth instance. Ensure get_access_token() was awaited on auth instance before client initialization."
            )
        # print(f"AvitoApiClient initialized for user_id: {self.user_id}")
        self.httpx_client = httpx.AsyncClient(base_url=AVITO_API_BASE_URL)

    async def _make_request(
        self, method, endpoint, params=None, json_data=None, expected_status=200
    ):
        """
        Makes an authenticated HTTP request to the Avito API with retry logic.

        Args:
            method: HTTP method ('GET' or 'POST')
            endpoint: API endpoint path
            params: Optional query parameters
            json_data: Optional JSON body for POST requests
            expected_status: Expected HTTP status code (default: 200)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            httpx.HTTPStatusError: If the request fails after all retries
            httpx.RequestError: If there's a network error after all retries

        Note:
            Implements exponential backoff for rate limiting (429 status)
            and retries up to 3 times for transient failures
        """
        # self.user_id should be set by __init__.
        access_token = await self.auth.get_access_token()  # Now awaits the async method
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",  # Default, can be overridden if needed
        }

        url = f"{AVITO_API_BASE_URL}{endpoint}"

        # Basic retry mechanism (e.g., for rate limits or transient errors)
        # In a real app, this would be more sophisticated (e.g., exponential backoff)
        retries = API_REQUEST_RETRIES
        last_exception = None
        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    response = await self.httpx_client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await self.httpx_client.post(
                        url, headers=headers, params=params, json=json_data
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == expected_status:
                    try:
                        # Read the response content as bytes
                        response_bytes = response.content
                        # Decode bytes to text (assuming utf-8 encoding for JSON)
                        response_text = response_bytes.decode("utf-8")

                        if (
                            not response_text
                        ):  # Handle cases where 200 OK might have a truly empty body
                            print(
                                f"Call to {endpoint} successful with status {response.status_code}, but received an empty body."
                            )
                            return {}  # Return empty dict for empty body

                        return json.loads(response_text)
                    except UnicodeDecodeError:
                        # Handle cases where content is not valid UTF-8
                        print(
                            f"Call to {endpoint} successful with status {response.status_code}, but body is not valid UTF-8. Response bytes snippet: '{response_bytes[:200]}'"
                        )
                        return {
                            "status": "success_not_utf8",
                            "status_code": response.status_code,
                            "response_bytes": response_bytes,
                        }
                    except json.JSONDecodeError:
                        # This will catch if json.loads(response_text) fails
                        print(
                            f"Call to {endpoint} successful with status {response.status_code}, but body is not valid JSON. Response text snippet: '{response_text[:200]}'"
                        )
                        return {
                            "status": "success_not_json",
                            "status_code": response.status_code,
                            "response_text": response_text,
                        }

                elif response.status_code == 429:  # Too Many Requests
                    backoff_time = API_RATE_LIMIT_BACKOFF_BASE**attempt
                    print(
                        f"Rate limit hit for {url}. Attempt {attempt + 1}/{retries}. Retrying in {backoff_time}s..."
                    )
                    await asyncio.sleep(backoff_time)  # Exponential backoff
                    last_exception = httpx.HTTPStatusError(
                        f"Rate limited after retries for {url}",
                        request=response.request,
                        response=response,
                    )
                    continue
                else:
                    response.raise_for_status()  # Raise an exception for other bad status codes

            except httpx.RequestError as e:
                print(f"Request failed for {url} (attempt {attempt + 1}/{retries}): {e}")
                last_exception = e
                if attempt < retries - 1:
                    await asyncio.sleep(API_RETRY_BASE_DELAY)  # Simple delay before retry
                else:
                    # Re-raise the last exception if all retries fail
                    # Or raise a custom error: raise ConnectionError(f"API request to {url} failed after {retries} retries: {last_exception}")
                    print(f"API request to {url} failed after {retries} retries.")
                    raise last_exception

        # This part should ideally not be reached if retries are handled correctly
        # but as a fallback:
        if last_exception:
            raise last_exception
        return None  # Should not happen

    async def get_chats(
        self,
        unread_only=False,
        item_ids=None,
        chat_types=None,
        limit=DEFAULT_CHATS_LIMIT,
        offset=0,
    ):
        """
        Gets a list of chats for the user.
        Ref: GET /messenger/v2/accounts/{user_id}/chats
        """
        if chat_types is None:
            chat_types = DEFAULT_CHAT_TYPES

        endpoint = f"/messenger/v2/accounts/{self.user_id}/chats"
        params = {
            "unread_only": str(unread_only).lower(),  # Convert boolean to string "true" or "false"
            "limit": limit,
            "offset": offset,
            "chat_types": ",".join(chat_types),  # API expects comma-separated string for array
        }
        if item_ids:
            params["item_ids"] = ",".join(map(str, item_ids))

        print(f"Getting chats with params: {params}")
        response_data = await self._make_request("GET", endpoint, params=params)
        return response_data.get("chats", []) if response_data else []

    async def get_messages_in_chat(self, chat_id, limit=DEFAULT_MESSAGES_LIMIT, offset=0):
        """
        Gets messages from a specific chat.
        Ref: GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/
        """
        endpoint = f"/messenger/v3/accounts/{self.user_id}/chats/{chat_id}/messages/"
        params = {"limit": limit, "offset": offset}
        print(f"Getting messages for chat_id: {chat_id} with params: {params}")
        response_data = await self._make_request("GET", endpoint, params=params)
        # The response for this endpoint is directly an array of messages
        return response_data if isinstance(response_data, list) else []

    async def get_item_details(self, item_id: int) -> dict | None:
        """
        Gets full details for a specific item (ad).
        Ref: GET /core/v1/accounts/{user_id}/items/{item_id}
        """
        endpoint = f"/core/v1/accounts/{self.user_id}/items/{item_id}"
        print(f"Getting details for item_id: {item_id}")
        response_data = await self._make_request("GET", endpoint)
        print(f"Raw response from get_item_details for {item_id}: {response_data}")  # Added logging
        return response_data

    async def get_all_user_items(
        self, status: str = "active", per_page: int = DEFAULT_ITEMS_PER_PAGE, page: int = 1
    ) -> list:
        """
        Gets a list of all items (ads) for the user, with pagination.
        Ref: GET /core/v1/items
        """
        endpoint = "/core/v1/items"
        params = {"status": status, "per_page": per_page, "page": page}
        print(f"Getting all user items with params: {params}")
        response_data = await self._make_request("GET", endpoint, params=params)
        print(f"Raw response from get_all_user_items: {response_data}")  # Added logging
        return response_data.get("resources", []) if response_data else []

    async def get_new_messages(self, item_ids_filter=None):
        """
        Retrieves new incoming messages from unread chats.

        This is a high-level function that first fetches unread chats, then
        retrieves messages from those chats, filtering for incoming messages.

        Args:
            item_ids_filter: Optional list of item IDs to filter chats by

        Returns:
            List of incoming message dictionaries with added chat_id, chat_user_id,
            and item_id_avito fields
        """
        print("Fetching new messages (unread chats first)...")
        unread_chats = await self.get_chats(
            unread_only=True, item_ids=item_ids_filter, limit=10
        )  # Limit chats for now

        all_new_messages = []
        if not unread_chats:
            print("No unread chats found.")
            return all_new_messages

        for chat in unread_chats:
            chat_id = chat.get("id")
            if not chat_id:
                print(f"Skipping chat with no ID: {chat}")
                continue

            item_id_avito = None
            chat_context = chat.get("context", {})
            if chat_context.get("type") == "item":
                item_id_avito = chat_context.get("value", {}).get("id")

            print(
                f"Fetching messages for unread chat_id: {chat_id}, item_id_avito: {item_id_avito}"
            )
            # Fetch a limited number of recent messages, assuming new messages are recent
            # The API for messages doesn't have an 'unread_only' flag, so we might get read ones too.
            # Business logic in ChatProcessor will need to handle already processed messages if any.
            messages = await self.get_messages_in_chat(chat_id, limit=20)  # Get recent 20 messages
            if messages:
                # Add chat_id to each message for context, and user_id of the other party
                chat_user_id = None
                # Correctly parse users from the chat object
                users_in_chat = chat.get("users", [])
                if isinstance(users_in_chat, list):
                    for user in users_in_chat:
                        if isinstance(user, dict) and str(user.get("id")) != str(
                            self.user_id
                        ):  # Find the other user
                            chat_user_id = user.get("id")
                            break

                for msg in messages:
                    msg["chat_id"] = chat_id
                    msg["chat_user_id"] = chat_user_id  # ID of the person we are chatting with
                    if item_id_avito:
                        msg["item_id_avito"] = item_id_avito
                    # We are interested in incoming messages
                    if msg.get("direction") == "in":
                        all_new_messages.append(msg)
            else:
                print(f"No messages found in chat {chat_id}, or error fetching them.")

        print(f"Found {len(all_new_messages)} new incoming messages in total.")
        return all_new_messages

    async def send_message(self, chat_id, text_content):
        """
        Sends a text message to a chat.
        Ref: POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages
        """
        endpoint = f"/messenger/v1/accounts/{self.user_id}/chats/{chat_id}/messages"
        payload = {"message": {"text": text_content}, "type": "text"}
        print(f"Sending message to chat_id: {chat_id}, content: '{text_content}'")
        return await self._make_request("POST", endpoint, json_data=payload)

    async def mark_message_read(self, chat_id):
        """
        Marks all messages in a chat as read.
        Ref: POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read
        The API marks the entire chat as read, not specific messages.
        """
        endpoint = f"/messenger/v1/accounts/{self.user_id}/chats/{chat_id}/read"
        print(f"Marking chat_id: {chat_id} as read.")
        # This endpoint returns 200 OK with an empty JSON object {} or sometimes 204 No Content
        # _make_request handles empty JSON, let's expect 200.
        return await self._make_request("POST", endpoint, expected_status=200)  # Can also be 204

    async def get_item_bookings(
        self, item_id: int, date_start: str, date_end: str, with_unpaid: bool = False
    ):
        """
        Gets bookings for a specific item within a date range.
        Ref: GET /realty/v1/accounts/{user_id}/items/{item_id}/bookings
        """
        endpoint = f"/realty/v1/accounts/{self.user_id}/items/{item_id}/bookings"
        params = {
            "date_start": date_start,
            "date_end": date_end,
            "with_unpaid": str(with_unpaid).lower(),
        }
        print(f"Getting bookings for item_id: {item_id} with params: {params}")
        response_data = await self._make_request("GET", endpoint, params=params)
        return response_data.get("bookings", []) if response_data else []

    async def update_item_bookings(self, item_id: int, bookings_payload: dict, source: str = "pms"):
        """
        Updates bookings for a specific item (typically to block dates).

        Args:
            item_id: Avito item (ad) ID
            bookings_payload: Dictionary conforming to PostCalendarData schema
                             with 'bookings' list containing date ranges and details
            source: Source identifier (default: "pms")

        Returns:
            API response dictionary

        Example:
            payload = {
                "bookings": [{
                    "date_start": "2024-01-01",
                    "date_end": "2024-01-05",
                    "type": "manual",
                    "comment": "Blocked via bot"
                }]
            }

        Ref:
            POST /core/v1/accounts/{user_id}/items/{item_id}/bookings
        """
        endpoint = f"/core/v1/accounts/{self.user_id}/items/{item_id}/bookings"
        # Ensure the source is part of the payload if not already there
        if "source" not in bookings_payload:
            bookings_payload["source"] = source
        print(f"Updating bookings for item_id: {item_id} with payload: {bookings_payload}")
        return await self._make_request("POST", endpoint, json_data=bookings_payload)

    async def update_item_availability(
        self, item_id: int, availability_payload: dict, source: str = "pms"
    ):
        """
        Updates availability intervals for a specific item.

        Args:
            item_id: Avito item (ad) ID
            availability_payload: Dictionary conforming to PostCalendarDataV2 schema
                                 with 'intervals' list containing date ranges and
                                 open/closed status
            source: Source identifier (default: "pms")

        Returns:
            API response dictionary

        Example:
            payload = {
                "intervals": [{
                    "date_start": "2024-01-01",
                    "date_end": "2024-01-05",
                    "open": 1
                }]
            }

        Ref:
            POST /realty/v1/items/intervals
        """
        endpoint = "/realty/v1/items/intervals"
        # Ensure item_id and source are part of the payload as per schema
        if "item_id" not in availability_payload:
            availability_payload["item_id"] = item_id
        if "source" not in availability_payload:
            availability_payload["source"] = source
        print(f"Updating availability for item_id: {item_id} with payload: {availability_payload}")
        return await self._make_request("POST", endpoint, json_data=availability_payload)


if __name__ == "__main__":
    print("Avito API Client - Example Usage (requires valid credentials and user_id)")

    # print("Avito API Client - Example Usage (User ID now from Auth)") # Main print statement commented

    # Ensure src/config.py exists with placeholders if not present for CLIENT_ID, CLIENT_SECRET
    # This is primarily for AvitoAuth initialization if it relies on src.config directly.
    if not os.path.exists("src"):  # pragma: no cover
        os.makedirs("src")
    if not os.path.exists("src/config.py"):  # pragma: no cover
        os.makedirs("src", exist_ok=True)  # Ensure src directory exists
        with open("src/config.py", "w") as f:
            f.write('CLIENT_ID = "your_test_client_id"\n')
            f.write('CLIENT_SECRET = "your_test_client_secret"\n')
        # print("Created dummy src/config.py for CLIENT_ID/SECRET for AvitoAuth if needed.")

    async def run_api_client_tests():
        try:
            # 1. Initialize Auth
            auth_instance = AvitoAuth()
            # Crucially, ensure token and user_id are populated before API client uses them
            await auth_instance.get_access_token()
            # print("AvitoAuth initialized and token/user_id fetched.")

            # 2. Initialize API Client
            api_client = AvitoApiClient(avito_auth_instance=auth_instance)
            # print(f"AvitoApiClient initialized. It will use User ID: {api_client.user_id}")

            # 3. Get New Messages (demonstration)
            print("\n--- Attempting to get new messages ---")
            try:
                new_messages = await api_client.get_new_messages()
                if new_messages:
                    print(f"Fetched {len(new_messages)} new incoming messages:")
                    for msg in new_messages[:2]:  # Print first 2 messages
                        print(
                            f"  Chat ID: {msg.get('chat_id')}, Author: {msg.get('author_id')}, Content: {msg.get('content')}"
                        )
                else:
                    print("No new incoming messages found or an error occurred.")
            except Exception as e:
                print(f"Error getting new messages: {e}")

            # Other test calls (send_message, mark_message_read, etc.) would also need 'await'
            # and are commented out for this refactoring task to keep it focused.
            # Example:
            # test_chat_id_to_send = "some_chat_id"
            # if test_chat_id_to_send != "some_chat_id":
            #     print(f"\n--- Attempting to send a message to chat_id: {test_chat_id_to_send} ---")
            #     try:
            #         send_response = await api_client.send_message(test_chat_id_to_send, "Hello from async API Client test!")
            #         print(f"Send message response: {send_response}")
            #     except Exception as e:
            #         print(f"Error sending message: {e}")

            print("\nExample usage finished.")

        except ConnectionError as e:
            print(f"ConnectionError during API client example: {e}")
        except ValueError as e:
            print(f"ValueError during API client example: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during API client example: {e}")
        finally:
            # Clean up dummy config if it was created
            if os.path.exists("src/config.py"):
                with open("src/config.py", "r") as f:
                    content = f.read()
                if "your_test_client_id" in content:
                    try:
                        os.remove("src/config.py")
                        # print("Removed dummy src/config.py.")
                    except OSError:
                        pass

    asyncio.run(run_api_client_tests())
    # Old synchronous test code removed or commented out

    # # try:
    #     # ... (old synchronous test code) ...
    # # except ConnectionError as e:
    #     # print(f"ConnectionError during API client example: {e}")
    # except ValueError as e:
    #     print(f"ValueError during API client example: {e}")
    # except Exception as e:
    #     print(f"An unexpected error occurred during API client example: {e}")

    # finally:
    #     # Clean up dummy config if it was created by this script's main
    #     # This cleanup should be more specific if it's created, e.g. check content
    #     if os.path.exists("src/config.py"): # pragma: no cover
    #         with open("src/config.py", "r") as f:
    #             content = f.read()
    #         if 'your_test_client_id' in content and 'your_test_client_secret' in content and \
    #            'USER_ID' not in content.upper(): # Check it's the minimal dummy
    #              try:
    #                  os.remove("src/config.py")
    #                  # print("Removed dummy src/config.py created by api_client main.")
    #              except OSError: # pragma: no cover
    #                  pass # print("Could not remove dummy src/config.py.")
    #     # Token cache file is managed by avito_auth.py, not removed here.
