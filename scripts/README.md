# Entry Point Scripts

This directory contains entry point scripts for running different components of the Avito Rental Assistant system.

## Available Scripts

### 1. run_bot.py - Telegram Bot

Starts the Telegram bot for landlord interactions.

**Usage:**
```bash
python scripts/run_bot.py [options]
```

**Options:**
- `--env-file PATH`: Path to the .env file (default: .env)
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Example:**
```bash
python scripts/run_bot.py --log-level DEBUG
```

**Required Environment Variables:**
- `AVITO_TG_BOT_TOKEN`: Your Telegram bot token
- `AVITO_CLIENT_ID`: Avito API client ID
- `AVITO_CLIENT_SECRET`: Avito API client secret

### 2. run_chat.py - Guest Chat Interface

Starts the interactive chat interface for guests using Ollama LLM.

**Usage:**
```bash
python scripts/run_chat.py [options]
```

**Options:**
- `--env-file PATH`: Path to the .env file (default: .env)
- `--apartment-info-dir PATH`: Directory with apartment info files (default: data/apartment_info)
- `--prompts-dir PATH`: Directory with prompt files (default: data/prompts)
- `--mcp-server-url URL`: MCP server URL (default: http://127.0.0.1:8314/mcp)
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Example:**
```bash
python scripts/run_chat.py --apartment-info-dir custom/apartment_info
```

**Prerequisites:**
- Ollama must be installed and running
- At least one Ollama model must be pulled (e.g., `ollama pull llama2`)
- MCP server must be running (see run_mcp_server.py)

### 3. run_mcp_server.py - MCP Server

Starts the FastMCP server for bridging chat and Telegram notifications.

**Usage:**
```bash
python scripts/run_mcp_server.py [options]
```

**Options:**
- `--env-file PATH`: Path to the .env file (default: .env)
- `--host HOST`: Host to bind to (default: 127.0.0.1)
- `--port PORT`: Port to bind to (default: 8314)
- `--path PATH`: URL path for MCP endpoint (default: /mcp)
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

**Example:**
```bash
python scripts/run_mcp_server.py --port 8315 --log-level DEBUG
```

## Typical Workflow

1. **Start the MCP server first:**
   ```bash
   python scripts/run_mcp_server.py
   ```

2. **Start the Telegram bot (in a separate terminal):**
   ```bash
   python scripts/run_bot.py
   ```

3. **Start the guest chat interface (in another terminal):**
   ```bash
   python scripts/run_chat.py
   ```

## Configuration

All scripts support loading configuration from a `.env` file. Create a `.env` file in the project root with the following variables:

```env
# Telegram Bot
AVITO_TG_BOT_TOKEN=your_telegram_bot_token
USER_TELEGRAM_IDS=123456789,987654321

# Avito API
AVITO_CLIENT_ID=your_avito_client_id
AVITO_CLIENT_SECRET=your_avito_client_secret

# Database
DATABASE_URL=sqlite:///./avito_rental.db

# MCP Server
MCP_SERVER_URL=http://127.0.0.1:8314/mcp

# Ollama
OLLAMA_MODEL=llama2
```

See `.env.example` in the project root for a complete template.

## Troubleshooting

### Bot won't start
- Verify `AVITO_TG_BOT_TOKEN` is set correctly
- Check that Avito API credentials are valid
- Ensure database is accessible

### Chat interface errors
- Verify Ollama is running: `ollama list`
- Check that MCP server is running and accessible
- Ensure prompt files exist in the prompts directory

### MCP server connection issues
- Verify the port is not already in use
- Check firewall settings if accessing remotely
- Ensure the URL matches what's configured in the chat interface

## Development

To run scripts in development mode with verbose logging:

```bash
python scripts/run_bot.py --log-level DEBUG
python scripts/run_chat.py --log-level DEBUG
python scripts/run_mcp_server.py --log-level DEBUG
```
