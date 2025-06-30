# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv antenv
source antenv/bin/activate  # On Windows: antenv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install browser for playwright (required for web scraping)
playwright install chromium
```

### Running the Application
```bash
# Development server with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Using the startup script
./startup.sh

# Production server with gunicorn
gunicorn -c gunicorn.conf.py main:app
```

### Build and Deploy
```bash
# Build script (installs dependencies)
./build.sh
```

### Testing
```bash
# Run tests
pytest
```

## Architecture Overview

This is a FastAPI-based conversational AI system called "Ublix Enterprise" that supports multi-channel communication (WhatsApp, Instagram, Facebook) with intelligent chat capabilities.

### Core Architecture Components

**LangGraph-Based Conversation Engine:**
- Uses LangGraph for state management and conversation flow
- Graph-based execution with nodes: `agent`, `tools`, `summarize_conversation`
- Memory persistence using MemorySaver with state cleanup (MAX_KEYS = 1)
- Supports both regular and streaming responses

**Multi-Channel Webhook System:**
- Instagram: `/api/instagram/webhook`
- Facebook: `/api/facebook/webhook` 
- WhatsApp: `/api/whatsapp/webhook`
- Chat API: `/api/chat/message` and `/api/chat/stream`

**Tool System Architecture:**
- Tools are dynamically loaded based on `project.enabled_tools` configuration
- API tools loaded asynchronously with fallback to synchronous loading
- Always-available tools: datetime, holidays, contact management
- Optional tools: retriever, FAQ, products, calendar, email, image processing, MongoDB

**State Management:**
- `CustomState` for LangGraph execution state
- `ChatState` for project/user context
- `MemoryStatePersistence` for conversation memory
- Background task execution for state saving and summary generation

### Key Files Structure

**Core Chat Engine:**
- `app/controler/chat/core/graph.py` - Main Graph class with execute() and execute_stream()
- `app/controler/chat/core/nodes.py` - Agent creation and node definitions
- `app/controler/chat/core/tools/__init__.py` - Tool loading and management
- `app/controler/chat/core/state.py` - State definitions
- `app/controler/chat/services/streaming_service.py` - Streaming response handling

**API Layer:**
- `app/__init__.py` - FastAPI app creation and middleware
- `app/routes.py` - Route definitions for chat and webhooks
- `app/chatbot.py` - Chat request handlers

**Data Persistence:**
- `app/controler/chat/store/` - Database adapters and state persistence
- `app/models/` - Pydantic models for data structures

**Integration Adapters:**
- `app/controler/chat/adapters/` - External service integrations (API, MongoDB, SQL)
- `app/controler/webhook/` - Platform-specific webhook handlers

### Project Configuration

Projects are loaded from database with configuration for:
- `enabled_tools` - Controls which tools are available
- `personality` - AI personality settings
- `instructions` - Custom instructions
- `prompt` - Base prompt template with placeholders: `{name}`, `{personality}`, `{instructions}`, `{utc_now}`

### Environment Variables

The application uses `.env` files for configuration. Key environment variables are loaded in `main.py` and throughout the system for database connections, API keys, and service configurations.

### Memory Management

- Conversation state is persisted between interactions
- State cleanup maintains only the most recent conversation (MAX_KEYS = 1)
- Summary generation runs in background to reduce memory usage
- Chile timezone (America/Santiago) used for datetime operations

### Error Handling

- Comprehensive logging throughout the system
- Graceful degradation for tool loading failures
- Background task error handling for non-critical operations