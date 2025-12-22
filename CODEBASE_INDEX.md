# Travel Planner Codebase Index

## Overview

This is a **Temporal-based travel planning system** that uses AI agents (AutoGen with Gemini/OpenAI) to create personalized travel itineraries. The system has one main workflow:

1. **SelfImprovingDestinationWorkflow** - An interactive POI (Point of Interest) search workflow with self-improving search refinement

## Architecture

### Core Technologies
- **Temporal**: Workflow orchestration engine
- **AutoGen**: Multi-agent AI framework
- **Gemini API**: Primary LLM (via OpenAI-compatible endpoint)
- **OpenAI API**: Used for structured output and web surfing
- **Google Places API**: POI search and discovery
- **Redis**: Pub/Sub for real-time UI updates
- **Chainlit**: Web-based chat UI
- **FastAPI**: (Present but not heavily used in current implementation)

### Infrastructure
- **Docker Compose**: Local development environment with:
  - PostgreSQL (Temporal database)
  - Temporal server
  - Temporal UI (port 5050)
  - Redis
  - Python worker container

## System Components

### 1. Self-Improving POI Workflow (`pois/workflow_poi_self_improving.py`)

An interactive, iterative workflow for finding Points of Interest:

**Flow:**
1. **Initial Chat** (`initial_chat_activity`) - "Lorenzo" agent collects user requirements
2. **Itinerary Critique** (`critize_user_itinerary_activity`) - Validates itinerary, checks travel advisories
3. **POI Query Proposal** (`propose_poi_query_activity`) - Converts user request to search parameters
4. **Google Places Search** (`google_places_activity_with_params`) - Executes POI search
5. **POI Review** (`review_poi_results_activity`) - Evaluates results, decides to accept or refine
6. **Loop** - If refinement needed, adjusts parameters and searches again (up to max_attempts)
7. **POI Summary** (`summarize_pois_activity`) - Final summary of selected POIs

**Features:**
- Interactive chat interface via Chainlit
- Real-time updates via Redis Pub/Sub
- Self-improving search refinement
- Travel advisory safety checks
- Multi-language support

**Entry Point**: `app/server.py` (Chainlit web UI) or `run_poi_workflow.py` (CLI)

## File Structure & Responsibilities

### POI Workflow Files
- `pois/workflow_poi_self_improving.py` - SelfImprovingDestinationWorkflow definition
- `pois/pois_self_improving_activities.py` - Activity wrappers for POI workflow
- `pois/poi_agents.py` - Agent implementations (chat, critique, propose, review, summarize, web lookup)
- `pois/poi_models.py` - Pydantic models for POI workflow data structures
- `pois/tools/google_places_tool.py` - Google Places API integration
- `pois/temporal_pois_worker.py` - POI-specific worker factory

### Infrastructure & Utilities
- `common/temporal_client.py` - Temporal client connection helper
- `common/get_redis.py` - Redis connection singleton
- `utils.py` - JSON extraction utility
- `app/server.py` - Chainlit web server with workflow integration

### Entry Points
- `run_poi_workflow.py` - CLI runner for SelfImprovingDestinationWorkflow
- `start.sh` - Chainlit server startup script
- `start_local.sh` - Local development worker startup

### Configuration
- `pyproject.toml` - Python dependencies (using uv)
- `docker-compose.dev.yml` - Local development infrastructure
- `Dockerfile` - Container image for worker

## Data Flow

### POI Workflow
```
User Chat → Lorenzo Agent → Itinerary Critique → POI Query → Google Places → Review Agent
                                                                                ↓
                                                                    [Accept] → Summary
                                                                    [Refine] → Loop back to Query
```

## Key Design Patterns

1. **Activity Pattern**: All external operations (LLM calls, API calls) are wrapped as Temporal Activities
2. **Agent Pattern**: Each agent is an AutoGen AssistantAgent with specific system prompts
3. **Self-Improving Loop**: POI workflow iteratively refines search parameters based on review feedback
4. **Pub/Sub Pattern**: Real-time UI updates via Redis channels
5. **Signal Pattern**: Workflow receives user messages via Temporal signals

## Environment Variables Required

- `GEMINI_API_KEY` - Google Gemini API key
- `GEMINI_MODEL` - Model name (default: "gemini-1.5-flash-8b")
- `GEMINI_BASE_URL` - API endpoint (default: OpenAI-compatible endpoint)
- `OPEN_AI_API_KEY` - OpenAI API key (for structured output and web surfing)
- `GOOGLE_PLACES_API_KEY` - Google Places API key
- `TEMPORAL_ADDRESS` - Temporal server address (default: "localhost:7233")
- `REDIS_HOST` - Redis host (default: "localhost")
- `REDIS_PORT` - Redis port (default: 6379)

## Task Queues

- `pois-self-improving-v2` - For SelfImprovingDestinationWorkflow

## Common Modification Scenarios

See `FILES_TO_MODIFY.md` for detailed file lists for common changes.

