# System Architecture

This document provides a comprehensive overview of the Avito Rental Assistant system architecture, including component design, data flow, and integration patterns.

## Table of Contents

- [Overview](#overview)
- [System Components](#system-components)
- [Architecture Diagram](#architecture-diagram)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [API Integration](#api-integration)
- [Communication Patterns](#communication-patterns)
- [Security Considerations](#security-considerations)
- [Scalability and Performance](#scalability-and-performance)

## Overview

The Avito Rental Assistant is a multi-component system designed to automate apartment rental management on the Avito platform. It combines:

- **Telegram Bot**: Landlord interface for managing bookings and receiving notifications
- **AI-Powered Chat**: Guest interface using Ollama LLM with RAG capabilities
- **MCP Server**: Communication bridge between chat and bot
- **Avito API Client**: Integration with Avito's rental platform
- **Database**: Persistent storage for ads, bookings, and chat history

### Design Principles

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Loose Coupling**: Components communicate through well-defined interfaces
3. **Async-First**: All I/O operations use async/await for better performance
4. **Fail-Safe**: Graceful error handling and recovery mechanisms
5. **Extensibility**: Easy to add new features or replace components

## System Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Avito Rental Assistant                        │
└─────────────────────────────────────────────────────────────────┘

External Services:
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Telegram    │         │   Avito API  │         │    Ollama    │
│   Platform   │         │   Platform   │         │     LLM      │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │                        │                        │
Internal Components:
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Telegram Bot │◄───────►│  Avito API   │         │  Guest Chat  │
│   Module     │         │    Client    │         │   Interface  │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │                        │                        │
       └────────────┬───────────┴────────────┬───────────┘
                    │                        │
                    ▼                        ▼
             ┌──────────────┐         ┌──────────────┐
             │  MCP Server  │         │   Database   │
             │   (FastMCP)  │         │ (SQLAlchemy) │
             └──────────────┘         └──────────────┘
```

## Component Details

### 1. Telegram Bot Module (`src/bot/`)

**Purpose**: Provides a mobile interface for landlords to manage their Avito listings.

**Key Responsibilities**:
- Handle landlord commands (`/close_dates`, `/open_dates`, `/calendar`)
- Display booking information and calendars
- Send notifications about new bookings and guest check-ins
- Manage conversation state for multi-step interactions

**Technology Stack**:
- `python-telegram-bot`: Telegram Bot API wrapper
- Conversation handlers for stateful interactions
- Inline keyboards for user-friendly selection

**Key Files**:
- `telegram_bot.py`: Main bot logic, command handlers, conversation flows

**Communication**:
- **Inbound**: Commands from Telegram users
- **Outbound**: 
  - API calls to Avito API Client
  - Database queries for ad information
  - Notifications triggered by MCP Server

### 2. Guest Chat Interface (`src/chat/`)

**Purpose**: Provides an AI-powered conversational interface for apartment rental guests.

**Key Responsibilities**:
- Process guest inquiries using natural language
- Provide context-aware responses using RAG
- Extract check-in times from conversations
- Trigger landlord notifications via MCP Server

**Technology Stack**:
- `ollama`: Python client for Ollama LLM
- RAG (Retrieval-Augmented Generation) with local apartment data
- Two-stage LLM processing:
  1. Conversational response generation
  2. Information extraction for notifications

**Key Files**:
- `guest_chat.py`: Main chat loop, Ollama integration, MCP client
- `rag_loader.py`: Loads apartment information and prompts from files

**Communication**:
- **Inbound**: User text input from console
- **Outbound**:
  - Ollama API for LLM inference
  - MCP Server for notification triggers
  - File system for RAG data

### 3. MCP Server (`src/mcp/`)

**Purpose**: Bridges the guest chat interface with the Telegram bot using the Model Context Protocol.

**Key Responsibilities**:
- Expose notification tools via MCP protocol
- Receive check-in requests from guest chat
- Forward notifications to Telegram bot

**Technology Stack**:
- `fastmcp`: FastMCP server implementation
- HTTP-based streamable transport
- RESTful endpoints

**Key Files**:
- `mcp_server.py`: FastMCP server with notification tools

**Communication**:
- **Inbound**: MCP tool calls from guest chat
- **Outbound**: Telegram bot notifications (currently simulated)

**Endpoints**:
- `/mcp`: Main MCP protocol endpoint
- `/health`: Health check endpoint

### 4. Avito API Client (`src/api/`)

**Purpose**: Handles all interactions with the Avito API.

**Key Responsibilities**:
- OAuth authentication and token management
- Fetch and manage chat messages
- Retrieve and update item (ad) details
- Manage bookings and availability
- Handle rate limiting and retries

**Technology Stack**:
- `httpx`: Async HTTP client
- OAuth 2.0 client credentials flow
- Exponential backoff for rate limiting

**Key Files**:
- `avito_auth.py`: OAuth authentication, token caching
- `avito_api_client.py`: API methods for all Avito operations

**Communication**:
- **Inbound**: Requests from Telegram bot
- **Outbound**: HTTPS requests to Avito API

**Key Features**:
- Automatic token refresh
- Token caching to disk
- Retry logic with exponential backoff
- User ID fetching and caching

### 5. Database Module (`src/database/`)

**Purpose**: Provides persistent storage for application data.

**Key Responsibilities**:
- Store ad descriptions and metadata
- Track bookings and their status
- Maintain chat history
- Provide ORM for data access

**Technology Stack**:
- `sqlalchemy`: ORM and database toolkit
- SQLite: Default database engine (configurable)

**Key Files**:
- `models.py`: SQLAlchemy model definitions
- `database.py`: Database session management, helper functions

**Communication**:
- **Inbound**: Queries from all components
- **Outbound**: None (data layer)

## Data Flow

### Scenario 1: Landlord Closes Booking Dates

```
1. Landlord sends /close_dates command to Telegram Bot
2. Bot fetches ad list from Database
3. Bot displays inline keyboard with ads
4. Landlord selects ad and enters date range
5. Bot calls Avito API Client to close dates
6. API Client authenticates with Avito API
7. API Client sends booking update to Avito
8. Bot confirms success to landlord
9. Bot sends notification to configured user IDs
```

### Scenario 2: Guest Requests Check-in Time

```
1. Guest types message in Chat Interface
2. Chat sends message to Ollama for conversational response
3. Ollama generates response using RAG context
4. Chat displays response to guest
5. Chat sends message to Ollama for information extraction
6. Ollama extracts check-in time and intent
7. If check-in detected, Chat calls MCP Server tool
8. MCP Server forwards notification to Telegram Bot
9. Bot sends notification to landlord
10. Chat confirms to guest that landlord was notified
```

### Scenario 3: Viewing Booking Calendar

```
1. Landlord sends /calendar command to Telegram Bot
2. Bot fetches ad list from Database
3. Landlord selects ad and specifies time period
4. Bot calls Avito API Client to fetch bookings
5. API Client retrieves bookings from Avito API
6. Bot formats booking data into readable calendar
7. Bot sends calendar to landlord
8. Bot logs calendar request
```

## Database Schema

### AdDescriptionsModel

Stores information about Avito ads (listings).

```python
class AdDescriptionsModel:
    id: Integer (Primary Key)
    ad_id_avito: String (Unique, Avito's ad ID)
    title: String (Ad title)
    address: String (Property address)
    description: Text (Full ad description)
    category: String (Ad category)
    created_at: DateTime (Record creation time)
    updated_at: DateTime (Last update time)
```

**Usage**:
- Telegram bot uses this to display ad selection keyboards
- Stores metadata for quick lookups without API calls
- Cached from Avito API responses

### Future Schema Extensions

Potential additions for enhanced functionality:

```python
class BookingModel:
    id: Integer (Primary Key)
    avito_booking_id: String (Unique)
    ad_id: Integer (Foreign Key to AdDescriptionsModel)
    guest_name: String
    check_in: Date
    check_out: Date
    status: String (active, pending, canceled)
    price: Decimal
    created_at: DateTime

class ChatHistoryModel:
    id: Integer (Primary Key)
    chat_id: String
    user_id: String
    message: Text
    direction: String (in/out)
    timestamp: DateTime
```

## API Integration

### Avito API Endpoints Used

#### Authentication
- `POST /token`: OAuth token endpoint
- `GET /core/v1/accounts/self`: Fetch user ID

#### Messenger
- `GET /messenger/v2/accounts/{user_id}/chats`: List chats
- `GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/`: Get messages
- `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/messages`: Send message
- `POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read`: Mark as read

#### Items (Ads)
- `GET /core/v1/accounts/{user_id}/items/{item_id}`: Get item details
- `GET /core/v1/items`: List all user items

#### Bookings
- `GET /realty/v1/accounts/{user_id}/items/{item_id}/bookings`: Get bookings
- `POST /core/v1/accounts/{user_id}/items/{item_id}/bookings`: Create/update bookings
- `POST /realty/v1/items/intervals`: Update availability intervals

### Rate Limiting Strategy

The Avito API Client implements several strategies to handle rate limits:

1. **Exponential Backoff**: When a 429 (Too Many Requests) response is received
2. **Retry Logic**: Up to 3 retries for transient failures
3. **Token Caching**: Reduces authentication requests
4. **Request Batching**: (Future enhancement) Batch multiple operations

## Communication Patterns

### Synchronous Communication

- **Telegram Bot ↔ Database**: Direct SQLAlchemy queries
- **Telegram Bot ↔ Avito API Client**: Async function calls

### Asynchronous Communication

- **Guest Chat → MCP Server**: HTTP-based MCP protocol
- **MCP Server → Telegram Bot**: Event-driven notifications (simulated)

### Event-Driven Patterns

Future enhancements could include:
- Message queue for decoupling components
- Webhook-based notifications from Avito
- Real-time updates using WebSockets

## Security Considerations

### Authentication and Authorization

1. **Avito API**:
   - OAuth 2.0 client credentials flow
   - Tokens cached securely on disk
   - Automatic token refresh

2. **Telegram Bot**:
   - Bot token stored in environment variables
   - User ID whitelist for notifications
   - No public endpoints

3. **MCP Server**:
   - Currently localhost-only
   - No authentication (internal service)
   - Future: Add API key authentication

### Data Protection

1. **Environment Variables**:
   - All secrets in `.env` file
   - `.env` excluded from version control
   - No hardcoded credentials

2. **Database**:
   - Local SQLite file
   - No sensitive guest data stored
   - Regular backups recommended

3. **Logging**:
   - No credentials logged
   - Sanitized error messages
   - Configurable log levels

### Network Security

1. **HTTPS Only**: All external API calls use HTTPS
2. **Local Services**: MCP server binds to localhost only
3. **No Public Exposure**: No components exposed to internet

## Scalability and Performance

### Current Limitations

1. **Single Instance**: All components run as single processes
2. **SQLite**: Not suitable for high concurrency
3. **Synchronous Processing**: Sequential message handling

### Scaling Strategies

#### Horizontal Scaling

1. **Multiple Bot Instances**:
   - Use webhook mode instead of polling
   - Load balance across instances
   - Shared database (migrate to PostgreSQL)

2. **Distributed MCP Servers**:
   - Deploy multiple MCP server instances
   - Use service discovery
   - Load balancer for distribution

#### Vertical Scaling

1. **Database Optimization**:
   - Migrate to PostgreSQL for better concurrency
   - Add indexes for frequent queries
   - Implement connection pooling

2. **Caching Layer**:
   - Redis for session data
   - Cache Avito API responses
   - Reduce database queries

#### Performance Optimizations

1. **Async Operations**:
   - All I/O operations already async
   - Parallel API requests where possible
   - Non-blocking database queries

2. **Request Batching**:
   - Batch multiple Avito API calls
   - Bulk database operations
   - Reduce round-trip time

3. **Resource Management**:
   - Connection pooling for HTTP clients
   - Database connection limits
   - Memory-efficient data structures

### Monitoring and Observability

Future enhancements:

1. **Metrics**:
   - Request latency tracking
   - Error rate monitoring
   - Resource utilization

2. **Logging**:
   - Structured logging (JSON)
   - Centralized log aggregation
   - Log levels per component

3. **Tracing**:
   - Distributed tracing for requests
   - Performance profiling
   - Bottleneck identification

## Technology Choices

### Why Python?

- Rich ecosystem for AI/ML (Ollama, LangChain)
- Excellent async support
- Strong Telegram bot libraries
- Rapid development

### Why SQLAlchemy?

- Database-agnostic ORM
- Easy migration path
- Type-safe queries
- Good documentation

### Why FastMCP?

- Simple MCP server implementation
- HTTP-based transport
- Easy integration with existing tools
- Minimal dependencies

### Why Ollama?

- Local LLM execution (privacy)
- No API costs
- Multiple model support
- Simple Python client

## Future Architecture Enhancements

### Short-term (1-3 months)

1. **Real MCP Integration**: Connect MCP server to actual Telegram bot
2. **Webhook Mode**: Switch bot from polling to webhooks
3. **Enhanced Logging**: Structured logging with rotation
4. **Error Tracking**: Integrate Sentry or similar

### Medium-term (3-6 months)

1. **PostgreSQL Migration**: Replace SQLite for production
2. **Message Queue**: Add Redis/RabbitMQ for async tasks
3. **Admin Dashboard**: Web interface for monitoring
4. **Multi-tenant Support**: Support multiple landlords

### Long-term (6-12 months)

1. **Microservices**: Split into independent services
2. **Kubernetes Deployment**: Container orchestration
3. **API Gateway**: Unified entry point
4. **Advanced Analytics**: Booking trends, revenue tracking

---

For more information, see:
- [Setup Guide](SETUP.md)
- [API Documentation](API.md)
- [Main README](../README.md)
