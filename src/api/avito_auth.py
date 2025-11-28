"""
Avito Authentication Module

This module handles OAuth authentication with the Avito API. It manages
access token lifecycle including fetching, caching, and automatic refresh.
It also retrieves and caches the user ID associated with the authenticated account.

Tokens are cached to disk to avoid unnecessary authentication requests.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

from src.constants import (
    AVITO_SELF_ACCOUNT_URL,
    AVITO_TOKEN_URL,
    TOKEN_CACHE_FILE,
    TOKEN_EXPIRATION_BUFFER_MINUTES,
)

# Determine the correct path to the .env file
# Assumes .env is in the project root, and this script is in a subdirectory (e.g., src/)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")

# If .env is not found in the parent directory (e.g., if script is run from root),
# try loading from the current working directory.
if not os.path.exists(dotenv_path):
    dotenv_path = ".env"  # Fallback to CWD

# Load .env file variables into environment
load_dotenv(dotenv_path=dotenv_path)


class AvitoAuth:
    """
    Handles OAuth authentication with the Avito API.

    This class manages access tokens, including fetching, caching, and automatic
    refresh. It also retrieves and caches the user ID associated with the
    authenticated account.

    Attributes:
        client_id: Avito API client ID
        client_secret: Avito API client secret
        access_token: Current access token
        token_expires_at: Datetime when the current token expires
        user_id: Avito user ID associated with the authenticated account
    """

    def __init__(self, client_id: str = None, client_secret: str = None):
        """
        Initializes the AvitoAuth instance.

        Args:
            client_id: Avito API client ID. If None, reads from AVITO_CLIENT_ID env var
            client_secret: Avito API client secret. If None, reads from
                          AVITO_CLIENT_SECRET env var

        Raises:
            ValueError: If client_id or client_secret are not provided and not
                       found in environment variables
        """
        self.client_id = client_id if client_id is not None else os.getenv("AVITO_CLIENT_ID")
        self.client_secret = (
            client_secret if client_secret is not None else os.getenv("AVITO_CLIENT_SECRET")
        )

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Client ID and Client Secret must be provided either as arguments "
                "or set as AVITO_CLIENT_ID and AVITO_CLIENT_SECRET environment variables."
            )

        self.access_token = None
        self.token_expires_at = None
        self.user_id = None  # Initialize user_id
        self._load_token_from_cache()

    def _load_token_from_cache(self):
        """
        Loads cached token and user_id from disk if available.

        Attempts to load previously cached authentication data from TOKEN_CACHE_FILE.
        If the cache is malformed or missing, initializes with None values.
        """
        try:
            if os.path.exists(TOKEN_CACHE_FILE):
                with open(TOKEN_CACHE_FILE, "r") as f:
                    data = json.load(f)
                    # Validate data structure before assigning
                    token = data.get("access_token")
                    expires_at_str = data.get("token_expires_at")
                    user_id_from_cache = data.get("user_id")

                    if token and expires_at_str:
                        self.access_token = token
                        self.token_expires_at = datetime.fromisoformat(expires_at_str)
                        self.user_id = user_id_from_cache  # Can be None if old cache
                        # print(f"Token and user_id ({self.user_id}) loaded from cache. Expires at: {self.token_expires_at}")
                    else:  # Malformed cache entry
                        self.access_token = None
                        self.token_expires_at = None
                        self.user_id = None
                        # print("Malformed token data in cache. Ignoring.")
            # else:
            # print(f"Cache file {TOKEN_CACHE_FILE} not found. Will request new token if needed.")
        except Exception:
            # print(f"Could not load token/user_id from cache")
            self.access_token = None
            self.token_expires_at = None
            self.user_id = None

    def _save_token_to_cache(self):
        """
        Saves current token and user_id to disk cache.

        Persists authentication data to TOKEN_CACHE_FILE for reuse across sessions.
        Silently fails if there's an error writing to disk.
        """
        if self.access_token and self.token_expires_at:  # user_id can be None
            try:
                with open(TOKEN_CACHE_FILE, "w") as f:
                    json.dump(
                        {
                            "access_token": self.access_token,
                            "token_expires_at": self.token_expires_at.isoformat(),
                            "user_id": self.user_id,
                        },
                        f,
                    )
                # print("Token and user_id saved to cache.")
            except Exception:
                pass  # print(f"Could not save token/user_id to cache")
        # else:
        # print("Attempted to save token to cache, but access_token or token_expires_at is missing.")

    async def _fetch_user_id(self, token_for_request: str) -> bool:
        """
        Fetches the user ID from Avito API using the provided token.

        Args:
            token_for_request: Access token to use for the API request

        Returns:
            True if user_id was successfully fetched, False otherwise

        Note:
            Updates self.user_id with the fetched value or None on failure
        """
        if not token_for_request:
            # print("Cannot fetch user_id without an access token.")
            return False

        # print("Fetching user_id from /core/v1/accounts/self...")
        headers = {"Authorization": f"Bearer {token_for_request}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(AVITO_SELF_ACCOUNT_URL, headers=headers)
            response.raise_for_status()
            user_data = response.json()
            fetched_user_id = user_data.get("id")
            if fetched_user_id is not None:  # Check for None explicitly
                self.user_id = str(fetched_user_id)
                # print(f"User ID fetched successfully: {self.user_id}")
                return True
            else:
                # print("User ID 'id' field not found or is null in /self response.")
                self.user_id = None
                return False
        except httpx.HTTPStatusError:
            # print(f"HTTP error fetching user_id")
            self.user_id = None
            return False
        except httpx.RequestError:
            # print(f"Request error fetching user_id")
            self.user_id = None
            return False
        except json.JSONDecodeError:
            # print(f"Error decoding JSON from /self endpoint. Response: {response.text if 'response' in locals() else 'N/A'}")
            self.user_id = None
            return False

    async def _request_new_token(self) -> bool:
        """
        Requests a new access token from Avito API.

        Uses OAuth client credentials flow to obtain a new access token.
        Also fetches the user_id after obtaining the token.

        Returns:
            True if token was successfully obtained, False otherwise

        Note:
            Updates self.access_token, self.token_expires_at, and self.user_id
        """
        # print("Requesting new Avito access token...")
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(AVITO_TOKEN_URL, data=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            expires_in = data.get("expires_in")

            if not self.access_token or not isinstance(expires_in, int):
                # print("Error: access_token or expires_in not found/invalid in new token response.")
                self.access_token = None
                self.token_expires_at = None
                self.user_id = None
                return False

            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            # print(f"New token obtained. Expires at: {self.token_expires_at}")

            if not await self._fetch_user_id(self.access_token):
                # print("Failed to fetch user_id with new token. Token obtained but user_id is missing.")
                # self.user_id will be None as per _fetch_user_id failure
                pass  # Continue, user_id is None

            self._save_token_to_cache()  # Save token and whatever user_id state we have
            return True

        except httpx.HTTPStatusError:
            # print(f"HTTP error requesting new token")
            self.access_token = None
            self.token_expires_at = None
            self.user_id = None
            return False
        except httpx.RequestError:
            # print(f"Request error requesting new token")
            self.access_token = None
            self.token_expires_at = None
            self.user_id = None
            return False
        except json.JSONDecodeError:  # Corrected variable name in print
            # print(f"Error decoding JSON response from token endpoint. Response: {response.text if 'response' in locals() else 'N/A'}")
            self.access_token = None
            self.token_expires_at = None
            self.user_id = None
            return False

    async def get_access_token(self) -> str | None:
        """
        Gets a valid access token, refreshing if necessary.

        Checks if the current token is valid and not expiring soon (within 5 minutes).
        If not, requests a new token. Also ensures user_id is fetched.

        Returns:
            Valid access token string

        Raises:
            ConnectionError: If unable to obtain or refresh the access token
        """
        token_is_valid_and_not_expiring_soon = False
        if self.access_token and self.token_expires_at:
            if self.token_expires_at > (
                datetime.now() + timedelta(minutes=TOKEN_EXPIRATION_BUFFER_MINUTES)
            ):
                token_is_valid_and_not_expiring_soon = True

        if not token_is_valid_and_not_expiring_soon:
            # print("Token is missing, expired, or expiring soon. Requesting/refreshing.")
            if not await self._request_new_token():
                raise ConnectionError("Failed to obtain/refresh Avito access token.")

        if self.access_token and self.user_id is None:
            # print("Token is valid, but user_id is missing. Attempting to fetch user_id post-validation.")
            if await self._fetch_user_id(self.access_token):
                self._save_token_to_cache()
            # else:
            # print("Still failed to fetch user_id. Proceeding with user_id as None.")

        return self.access_token

    async def get_current_user_id(self) -> str | None:
        """
        Gets the current user ID, ensuring authentication is valid.

        Returns:
            User ID string if available, None if authentication fails or
            user_id cannot be fetched
        """
        try:
            await self.get_access_token()  # Ensures token and user_id fetch attempt
        except ConnectionError:  # If token fetching fails, user_id cannot be determined
            return None
        return self.user_id


# Example usage (for testing purposes, will be removed/modified later)
async def main_test():  # pragma: no cover
    print("Avito Authentication Module - __main__ execution for testing")
    print("==========================================================")
    # ... (rest of __main__ block should be updated to use new methods and test user_id)

    # Display loaded credentials from .env
    client_id_from_env = os.getenv("AVITO_CLIENT_ID")
    client_secret_from_env = os.getenv("AVITO_CLIENT_SECRET")

    print(f"Loaded AVITO_CLIENT_ID from .env: '{client_id_from_env}'")
    print(f"Loaded AVITO_CLIENT_SECRET from .env: '{client_secret_from_env}'")
    print("---")

    auth_instance = None
    print("Attempting to initialize AvitoAuth...")
    try:
        auth_instance = AvitoAuth()
        print("AvitoAuth initialized successfully.")
    except ValueError as e:
        print(f"AvitoAuth initialization failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during AvitoAuth initialization: {e}")

    if auth_instance:
        print("\nAttempting to get access token and user ID...")
        try:
            token = await auth_instance.get_access_token()
            if token:
                print(f"Access token retrieved: {token[:20]}...")
                user_id = (
                    await auth_instance.get_current_user_id()
                )  # This will use the already fetched token
                if user_id:
                    print(f"User ID retrieved: {user_id}")
                else:
                    print("User ID could not be fetched/retrieved.")

                if os.path.exists(TOKEN_CACHE_FILE):
                    print(
                        f"Token data (incl. user_id if fetched) stored/updated in '{os.path.abspath(TOKEN_CACHE_FILE)}'."
                    )
                else:
                    print(
                        f"WARNING: Token file {TOKEN_CACHE_FILE} not found after token operations."
                    )

            else:  # Token is None
                print("Failed to retrieve access token.")

        except ConnectionError as e:
            print(f"ConnectionError during token/user_id retrieval: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    print("\n--- End of __main__ test execution ---")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main_test())
