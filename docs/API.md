# Avito API Integration Documentation

This document provides comprehensive documentation for the Avito API integration in the Avito Rental Assistant project.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [API Client Architecture](#api-client-architecture)
- [Core API Methods](#core-api-methods)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The Avito Rental Assistant integrates with the Avito API to manage apartment rental listings, bookings, and guest communications. The integration is implemented through two main modules:

- **`avito_auth.py`**: Handles OAuth authentication and token management
- **`avito_api_client.py`**: Provides methods for all Avito API operations

### API Base URL

```
https://api.avito.ru
```

### API Documentation

Official Avito API documentation: https://www.avito.ru/professionals/api

## Authentication

### OAuth 2.0 Client Credentials Flow

The Avito API uses OAuth 2.0 with the client credentials grant type for authentication.

#### Authentication Flow

```
1. Application requests access token with client credentials
2. Avito returns access token with expiration time
3. Application caches token for reuse
4. Application includes token in all API requests
5. Application refreshes token before expiration
```

### AvitoAuth Class

The `AvitoAuth` class manages the complete authentication lifecycle.

#### Initialization

```python
from src.api.avito_auth import AvitoAuth

# Initialize with credentials from environment variables
auth = AvitoAuth()

# Or provide credentials explicitly
auth = AvitoAuth(
    client_id="your_client_id",
    client_secret="your_client_secret"
)
```

#### Getting an Access Token

```python
import asyncio

async def main():
    auth = AvitoAuth()
    token = await auth.get_access_token()
    print(f"Access token: {token}")

asyncio.run(main())
```

#### Token Caching

Tokens are automatically cached to disk in `.avito_token_cache.json` to avoid unnecessary authentication requests.

**Cache Structure**:
```json
{
  "access_token": "your_access_token",
  "token_expires_at": "2024-01-01T12:00:00",
  "user_id": "12345678"
}
```

#### User ID Retrieval

The user ID is automatically fetched and cached along with the access token:

```python
async def main():
    auth = AvitoAuth()
    user_id = await auth.get_current_user_id()
    print(f"User ID: {user_id}")

asyncio.run(main())
```

### Authentication Endpoints

#### Token Endpoint

**POST** `/token`

Request a new access token using client credentials.

**Request**:
```http
POST https://api.avito.ru/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET
```

**Response**:
```json
{
  "access_token": "your_access_token",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

#### Self Account Endpoint

**GET** `/core/v1/accounts/self`

Retrieve the authenticated user's account information.

**Request**:
```http
GET https://api.avito.ru/core/v1/accounts/self
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response**:
```json
{
  "id": 12345678,
  "name": "Your Name",
  "email": "your@email.com"
}
```

## API Client Architecture

### AvitoApiClient Class

The `AvitoApiClient` class provides a comprehensive interface to all Avito API operations.

#### Initialization

```python
from src.api.avito_auth import AvitoAuth
from src.api.avito_api_client import AvitoApiClient
import asyncio

async def main():
    # Initialize auth and fetch token/user_id
    auth = AvitoAuth()
    await auth.get_access_token()
    
    # Initialize API client
    client = AvitoApiClient(avito_auth_instance=auth)
    
    # Now you can use the client
    chats = await client.get_chats()

asyncio.run(main())
```

#### Internal Request Method

All API requests go through the `_make_request` method, which handles:
- Authentication header injection
- Retry logic for transient failures
- Rate limit handling with exponential backoff
- Response parsing and error handling

## Core API Methods

### Messenger API

#### Get Chats

Retrieve a list of chats for the authenticated user.

```python
chats = await client.get_chats(
    unread_only=False,
    item_ids=None,
    chat_types=["u2i"],  # User-to-item chats
    limit=50,
    offset=0
)
```

**Parameters**:
- `unread_only` (bool): Filter for unread chats only
- `item_ids` (list): Filter by specific item IDs
- `chat_types` (list): Chat types to include (default: ["u2i"])
- `limit` (int): Maximum number of chats to return (default: 50)
- `offset` (int): Pagination offset (default: 0)

**Returns**: List of chat dictionaries

**API Endpoint**: `GET /messenger/v2/accounts/{user_id}/chats`

#### Get Messages in Chat

Retrieve messages from a specific chat.

```python
messages = await client.get_messages_in_chat(
    chat_id="chat_12345",
    limit=20,
    offset=0
)
```

**Parameters**:
- `chat_id` (str): The chat ID
- `limit` (int): Maximum number of messages (default: 20)
- `offset` (int): Pagination offset (default: 0)

**Returns**: List of message dictionaries

**API Endpoint**: `GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/`

#### Send Message

Send a text message to a chat.

```python
response = await client.send_message(
    chat_id="chat_12345",
    text_content="Hello! Thank you for your inquiry."
)
```

**Parameters**:
- `chat_id` (str): The chat ID
- `text_content` (str): Message text to send

**Returns**: API response dictionary

**API Endpoint**: `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages`

#### Mark Chat as Read

Mark all messages in a chat as read.

```python
response = await client.mark_message_read(chat_id="chat_12345")
```

**Parameters**:
- `chat_id` (str): The chat ID

**Returns**: API response dictionary

**API Endpoint**: `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read`

#### Get New Messages

High-level method to retrieve new incoming messages from unread chats.

```python
new_messages = await client.get_new_messages(
    item_ids_filter=[123456, 789012]
)
```

**Parameters**:
- `item_ids_filter` (list, optional): Filter by specific item IDs

**Returns**: List of incoming message dictionaries with added metadata:
- `chat_id`: The chat ID
- `chat_user_id`: The other user's ID
- `item_id_avito`: The associated item ID

### Items (Ads) API

#### Get Item Details

Retrieve full details for a specific item (ad).

```python
item = await client.get_item_details(item_id=123456)
```

**Parameters**:
- `item_id` (int): The Avito item ID

**Returns**: Item details dictionary

**API Endpoint**: `GET /core/v1/accounts/{user_id}/items/{item_id}`

**Response Example**:
```json
{
  "id": 123456,
  "title": "Cozy 2-bedroom apartment",
  "address": "Moscow, Leninsky Prospekt, 123",
  "category": "Квартиры",
  "status": "active",
  "price": 5000
}
```

#### Get All User Items

Retrieve a paginated list of all items for the user.

```python
items = await client.get_all_user_items(
    status="active",
    per_page=50,
    page=1
)
```

**Parameters**:
- `status` (str): Filter by status (default: "active")
- `per_page` (int): Items per page (default: 50)
- `page` (int): Page number (default: 1)

**Returns**: List of item dictionaries

**API Endpoint**: `GET /core/v1/items`

### Bookings API

#### Get Item Bookings

Retrieve bookings for a specific item within a date range.

```python
bookings = await client.get_item_bookings(
    item_id=123456,
    date_start="2024-01-01",
    date_end="2024-01-31",
    with_unpaid=False
)
```

**Parameters**:
- `item_id` (int): The Avito item ID
- `date_start` (str): Start date in YYYY-MM-DD format
- `date_end` (str): End date in YYYY-MM-DD format
- `with_unpaid` (bool): Include unpaid bookings (default: False)

**Returns**: List of booking dictionaries

**API Endpoint**: `GET /realty/v1/accounts/{user_id}/items/{item_id}/bookings`

**Response Example**:
```json
{
  "bookings": [
    {
      "avito_booking_id": "booking_123",
      "check_in": "2024-01-15",
      "check_out": "2024-01-20",
      "status": "active",
      "base_price": 25000,
      "contact": {
        "name": "John Doe"
      }
    }
  ]
}
```

#### Update Item Bookings

Create or update bookings for an item (typically to block dates).

```python
payload = {
    "bookings": [
        {
            "date_start": "2024-01-15",
            "date_end": "2024-01-20",
            "type": "manual",
            "comment": "Blocked via Telegram bot"
        }
    ]
}

response = await client.update_item_bookings(
    item_id=123456,
    bookings_payload=payload,
    source="telegram_bot"
)
```

**Parameters**:
- `item_id` (int): The Avito item ID
- `bookings_payload` (dict): Booking data conforming to PostCalendarData schema
- `source` (str): Source identifier (default: "pms")

**API Endpoint**: `POST /core/v1/accounts/{user_id}/items/{item_id}/bookings`

#### Update Item Availability

Update availability intervals for an item.

```python
payload = {
    "intervals": [
        {
            "date_start": "2024-01-15",
            "date_end": "2024-01-20",
            "open": 1  # 1 for open, 0 for closed
        }
    ]
}

response = await client.update_item_availability(
    item_id=123456,
    availability_payload=payload,
    source="telegram_bot"
)
```

**Parameters**:
- `item_id` (int): The Avito item ID
- `availability_payload` (dict): Availability data conforming to PostCalendarDataV2 schema
- `source` (str): Source identifier (default: "pms")

**API Endpoint**: `POST /realty/v1/items/intervals`

## Error Handling

### Exception Types

The API client handles several types of errors:

1. **HTTP Status Errors** (`httpx.HTTPStatusError`):
   - 400: Bad Request (invalid parameters)
   - 401: Unauthorized (invalid or expired token)
   - 403: Forbidden (insufficient permissions)
   - 404: Not Found (resource doesn't exist)
   - 429: Too Many Requests (rate limit exceeded)
   - 500: Internal Server Error

2. **Request Errors** (`httpx.RequestError`):
   - Network connectivity issues
   - DNS resolution failures
   - Connection timeouts

3. **Authentication Errors** (`ConnectionError`):
   - Failed to obtain access token
   - Invalid credentials

### Error Handling Strategy

```python
try:
    chats = await client.get_chats()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        print("Authentication failed. Check your credentials.")
    elif e.response.status_code == 429:
        print("Rate limit exceeded. Retry after some time.")
    else:
        print(f"HTTP error: {e}")
except httpx.RequestError as e:
    print(f"Network error: {e}")
except ConnectionError as e:
    print(f"Authentication error: {e}")
```

### Automatic Retry Logic

The `_make_request` method automatically retries failed requests:

- **Retries**: Up to 3 attempts
- **Backoff**: Exponential backoff for rate limits (429)
- **Delay**: 2-second delay between retries for other errors

## Rate Limiting

### Avito API Rate Limits

Avito enforces rate limits on API requests. Exact limits are not publicly documented but typically:

- **Per-minute limits**: ~60 requests per minute
- **Per-hour limits**: ~1000 requests per hour
- **Per-day limits**: ~10,000 requests per day

### Rate Limit Handling

When a 429 (Too Many Requests) response is received:

1. The client waits using exponential backoff
2. Backoff time: 2^attempt seconds (2s, 4s, 8s)
3. After 3 attempts, the exception is raised

### Best Practices

1. **Cache responses** when possible
2. **Batch operations** to reduce request count
3. **Use pagination** efficiently
4. **Implement request queuing** for high-volume scenarios

## Usage Examples

### Complete Workflow Example

```python
import asyncio
from src.api.avito_auth import AvitoAuth
from src.api.avito_api_client import AvitoApiClient

async def main():
    # Initialize authentication
    auth = AvitoAuth()
    await auth.get_access_token()
    
    # Initialize API client
    client = AvitoApiClient(avito_auth_instance=auth)
    
    # Get all active items
    items = await client.get_all_user_items(status="active")
    print(f"Found {len(items)} active items")
    
    # Get details for first item
    if items:
        item_id = items[0]["id"]
        details = await client.get_item_details(item_id)
        print(f"Item: {details.get('title')}")
        
        # Get bookings for next 30 days
        from datetime import date, timedelta
        today = date.today()
        end_date = today + timedelta(days=30)
        
        bookings = await client.get_item_bookings(
            item_id=item_id,
            date_start=today.strftime("%Y-%m-%d"),
            date_end=end_date.strftime("%Y-%m-%d")
        )
        print(f"Found {len(bookings)} bookings")
    
    # Get unread chats
    unread_chats = await client.get_chats(unread_only=True)
    print(f"Found {len(unread_chats)} unread chats")
    
    # Process each unread chat
    for chat in unread_chats:
        chat_id = chat["id"]
        messages = await client.get_messages_in_chat(chat_id, limit=10)
        
        # Find incoming messages
        incoming = [m for m in messages if m.get("direction") == "in"]
        print(f"Chat {chat_id}: {len(incoming)} incoming messages")
        
        # Send a response
        if incoming:
            await client.send_message(
                chat_id=chat_id,
                text_content="Thank you for your message! We'll respond shortly."
            )
            
            # Mark as read
            await client.mark_message_read(chat_id=chat_id)

asyncio.run(main())
```

### Blocking Dates Example

```python
async def block_dates(client, item_id, start_date, end_date):
    """Block dates on an item's calendar."""
    payload = {
        "bookings": [
            {
                "date_start": start_date,
                "date_end": end_date,
                "type": "manual",
                "comment": "Blocked for maintenance"
            }
        ]
    }
    
    try:
        response = await client.update_item_bookings(
            item_id=item_id,
            bookings_payload=payload
        )
        print(f"Successfully blocked dates: {start_date} to {end_date}")
        return response
    except Exception as e:
        print(f"Error blocking dates: {e}")
        return None

# Usage
await block_dates(client, 123456, "2024-01-15", "2024-01-20")
```

### Opening Dates Example

```python
async def open_dates(client, item_id, start_date, end_date):
    """Open dates on an item's calendar."""
    payload = {
        "intervals": [
            {
                "date_start": start_date,
                "date_end": end_date,
                "open": 1
            }
        ]
    }
    
    try:
        response = await client.update_item_availability(
            item_id=item_id,
            availability_payload=payload
        )
        print(f"Successfully opened dates: {start_date} to {end_date}")
        return response
    except Exception as e:
        print(f"Error opening dates: {e}")
        return None

# Usage
await open_dates(client, 123456, "2024-01-15", "2024-01-20")
```

## Best Practices

### 1. Token Management

- Always use the `AvitoAuth` class for authentication
- Don't manually manage tokens
- Let the auth class handle caching and refresh

### 2. Error Handling

- Always wrap API calls in try-except blocks
- Handle specific exception types appropriately
- Log errors for debugging

### 3. Async Operations

- Use `async`/`await` for all API calls
- Don't block the event loop
- Use `asyncio.gather()` for parallel requests

### 4. Resource Management

- Reuse the same `AvitoApiClient` instance
- Don't create multiple clients unnecessarily
- Close HTTP clients when done (handled automatically)

### 5. Data Validation

- Validate date formats before API calls
- Check required fields in payloads
- Handle missing or null values in responses

### 6. Pagination

- Use pagination for large result sets
- Don't fetch all data at once
- Implement cursor-based pagination where available

## Troubleshooting

### Common Issues

#### "Failed to obtain Avito access token"

**Causes**:
- Invalid client ID or secret
- Network connectivity issues
- Avito API downtime

**Solutions**:
1. Verify credentials in `.env` file
2. Check network connectivity
3. Try manual authentication via curl
4. Check Avito API status

#### "User ID not found on AvitoAuth instance"

**Causes**:
- `get_access_token()` not called before client initialization
- API error when fetching user ID

**Solutions**:
1. Always call `await auth.get_access_token()` before creating client
2. Check API response for errors
3. Verify account has proper permissions

#### Rate Limit Errors (429)

**Causes**:
- Too many requests in short time
- Concurrent requests exceeding limits

**Solutions**:
1. Implement request throttling
2. Add delays between requests
3. Use caching to reduce API calls
4. Batch operations when possible

#### Empty or Malformed Responses

**Causes**:
- API endpoint changes
- Invalid request parameters
- Server-side errors

**Solutions**:
1. Check API documentation for changes
2. Validate request parameters
3. Log full response for debugging
4. Contact Avito support if persistent

### Debugging Tips

1. **Enable detailed logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Inspect raw responses**:
```python
response = await client._make_request("GET", endpoint)
print(json.dumps(response, indent=2))
```

3. **Test with curl**:
```bash
curl -X GET "https://api.avito.ru/core/v1/accounts/self" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

4. **Check token cache**:
```bash
cat .avito_token_cache.json
```

### Getting Help

If you encounter issues not covered here:

1. Check the [official Avito API documentation](https://www.avito.ru/professionals/api)
2. Review the source code in `src/api/`
3. Enable debug logging to see detailed request/response data
4. Open an issue on GitHub with:
   - Error message
   - Code snippet
   - API endpoint being called
   - Expected vs actual behavior

---

For more information, see:
- [Setup Guide](SETUP.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Main README](../README.md)
