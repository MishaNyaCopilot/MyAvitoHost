# Avito Rental Assistant

A sophisticated automated system for managing apartment rentals on Avito, combining a Telegram bot for landlords and an AI-powered natural language chat interface for guests. This project demonstrates practical integration of modern technologies including large language models, APIs, and real-time communication to create a comprehensive solution for short-term rental management.

> **Portfolio Project** | Full-stack Python application showcasing AI integration, API development, and real-time communication systems.

## Features

### Telegram Bot for Landlords

The Telegram bot provides a convenient mobile interface for landlords to manage their Avito listings:

- **Booking Management**
  - Close/open dates on the Avito calendar
  - View upcoming bookings for specific apartments
  - Manage multiple properties from one interface

- **Real-time Notifications**
  - New booking alerts
  - Upcoming check-in reminders
  - Ad status change notifications
  - Low balance warnings
  - Guest check-in time notifications from chat

### AI-Powered Guest Chat Interface

An interactive chat interface powered by Ollama LLM with Retrieval-Augmented Generation (RAG):

- **Natural Language Understanding**: Guests can ask questions conversationally and receive helpful, context-aware responses
- **RAG-Enhanced Responses**: AI knowledge is augmented with specific apartment details loaded from local files:
  - Apartment amenities and rules
  - Check-in/check-out procedures
  - Location and nearby points of interest
  - House information and policies
- **Automated Check-in Notifications**: Two-step AI process extracts check-in times from guest messages and automatically notifies landlords via Telegram
- **MCP Integration**: Uses FastMCP server to bridge chat interface with Telegram bot for seamless communication

### Avito API Integration

- OAuth authentication with Avito API
- Manage listings and bookings programmatically
- Retrieve account information and balance
- Update calendar availability

## Technology Stack

- **Python 3.8+** - Core programming language with async/await patterns
- **Telegram Bot API** - Real-time landlord interface via python-telegram-bot
- **Ollama LLM** - Local large language model for natural language processing
- **FastMCP** - Model Context Protocol server for inter-component communication
- **SQLAlchemy** - Database ORM for data persistence and relationship management
- **HTTPX** - Modern async HTTP client for external API integration
- **Retrieval-Augmented Generation (RAG)** - Context-aware AI responses using local knowledge base

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Avito Rental Assistant                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  Telegram Bot    │         │   Guest Chat     │
│   (Landlord)     │         │   (AI-Powered)   │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │                            │
         ├────────────┐      ┌────────┤
         │            │      │        │
         ▼            ▼      ▼        ▼
┌─────────────┐  ┌──────────────┐  ┌──────────┐
│  Avito API  │  │  MCP Server  │  │  Ollama  │
│             │  │   (FastMCP)  │  │   LLM    │
└─────────────┘  └──────────────┘  └──────────┘
         │            │                  │
         │            │                  │
         └────────────┴──────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │   Database   │
              │  (SQLAlchemy)│
              └──────────────┘
```

### Component Responsibilities

- **Telegram Bot** (`src/bot/`): Handles landlord interactions, manages bookings, sends notifications
- **Guest Chat** (`src/chat/`): Provides AI-powered chat interface with RAG capabilities
- **MCP Server** (`src/mcp/`): Bridges chat and bot, enables cross-component communication
- **API Client** (`src/api/`): Manages Avito API authentication and requests
- **Database** (`src/database/`): Persists listings, bookings, and chat history

### Data Flow

1. Guest asks question in chat interface
2. Ollama LLM generates response using RAG-enhanced context
3. If check-in time detected, MCP server notifies Telegram bot
4. Landlord receives notification and can manage booking
5. All interactions logged to database

## Project Structure

```
avito-rental-assistant/
├── src/                    # Source code
│   ├── bot/               # Telegram bot module
│   ├── chat/              # Guest chat interface
│   ├── mcp/               # MCP server
│   ├── api/               # Avito API client
│   └── database/          # Database models and ORM
├── data/                   # Data files
│   ├── apartment_info/    # Apartment details for RAG
│   └── prompts/           # AI prompt templates
├── docs/                   # Additional documentation
├── scripts/               # Entry point scripts
│   ├── run_bot.py        # Start Telegram bot
│   ├── run_chat.py       # Start guest chat
│   └── run_mcp_server.py # Start MCP server
├── .env.example           # Environment variable template
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Key Technical Highlights

- **Microservices Architecture**: Three independent components communicating via MCP protocol
- **Async/Await Patterns**: Efficient handling of concurrent operations and API calls
- **RAG Implementation**: Custom knowledge base integration for context-aware AI responses
- **OAuth 2.0 Integration**: Secure authentication with Avito API
- **Conversation State Management**: Complex multi-step user interactions with Telegram bot
- **Two-Stage AI Processing**: Separate conversational and information extraction pipelines
- **Modular Design**: Clean separation of concerns across bot, chat, API, and database layers

## Documentation

Technical documentation is available in the `docs/` directory:

- **[Architecture](docs/ARCHITECTURE.md)** - System design and component interactions
- **[API Documentation](docs/API.md)** - Avito API integration details

## About

This project was developed as a portfolio piece to demonstrate:
- Integration of modern AI technologies (LLMs, RAG) into practical applications
- Building scalable microservices architectures
- Working with external APIs and real-time communication systems
- Clean code practices and comprehensive documentation

For questions or collaboration opportunities, please open an issue on GitHub.

---

**Note**: This is an educational and portfolio project. Ensure compliance with Avito's API terms of service and Telegram's bot policies if deploying for production use.
