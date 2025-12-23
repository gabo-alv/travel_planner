# Travel Planner - AI-Powered Travel Itinerary System

A proof-of-concept toy project that demonstrates an integration of AutoGen and Temporal io for conversational Agentic flows.


The biggest addition of integrating an agentic framework is that it enables three types of architectures: 

- **Single Agent per Activity**: Enforces the principle of LLM calls being triggered *once per activity* call on a Temporal Workflow. Often the most deterministic approach that could be achieved, as the flow is controlled in a pure deterministic flow control logic and each activity (and workflow as a whole) can be tested in isolation.
- **Single Team per Activity**: An Activity wraps an agentic team and returns its outcome. Often used in a producer + critic pattern or to encapsulate more complex and undeterministic tasks. Even if a team consists of a single "agent" (or LLM wrapper), it is still abstracted as a "team" for consistency.
- **Hybrid**: Complex, undeterministic tasks are handled by agent teams, while simple calls can be just plain LLM client calls or single agents. This is the pattern chosen for this project (See `travel_advisory_lookup` usage for an example).

There is a lot to be explored in this kind of systems, see **Agents Lifecycle and memory** below for an example.


## 🏗️ Architecture

### Overview

This system uses a three-layer architecture:

1. **Temporal Workflows** - Orchestrate long-running, fault-tolerant processes
2. **AutoGen Agents** - Handle AI-powered conversations and decision-making
3. **Gemini/OpenAI LLMs** - Provide language understanding and generation

### Architecture Components

#### 1. Temporal Layer

**Temporal** serves as the workflow orchestration engine, providing:
- **Fault tolerance**: Automatic retries and recovery from failures
- **Durability**: Workflow state persists across restarts
- **Observability**: Full visibility into workflow execution via Temporal UI
- **Scalability**: Activities can be distributed across multiple workers. (For simplicity, and because this is a toy project, we just have one worker initialized in the same file as the Chainlit server. Worker's lifecycle should be handled separately)

**Key Concepts:**
- **Workflows**: Define the business logic and orchestration flow
- **Activities**: Wrap external operations (LLM calls, Tool calls) as executable units
- **Signals**: Allow workflows to receive external events (e.g., user messages)
- **Task Queues**: Route work to specific workers. For our conversational loop, we just have one queue

#### 2. AutoGen Layer

**AutoGen** provides the multi-agent framework for building conversational AI agents:

- **AssistantAgent**: Each agent is an `AssistantAgent` with:
  - System prompts defining its role and behavior
  - Model client (Gemini or OpenAI)
  - Structured output support via Pydantic models

#### 3. UI Layer (Chainlit + Custom Elements)

**Chainlit** provides the chat interface with support for custom React components:
- **Custom Elements**: React components (JSX) for rich UI interactions
- **POIMap Element**: Google Maps JavaScript API integration for interactive map display
- **Real-time Updates**: Redis pub/sub for workflow status updates
- **Custom Event Handling**: Specialized handlers for different UI element types

#### 4. Tools Calls:

Tools are modeled as just regular code wrapped in Temporal Activities. They will be re-run (depending on Temporal's workflow setup) gracefully if they fail, and the number of retries or timeouts can be controlled at runtime

#### 5. Agents Lifecycle

In this project, each agent (or team of agents) is created and destroyed per Activity call. This gives an important benefit as they don't have to be programmatically controlled based on sessions or on each API call.

**Agent Types:**
- **Chat Agents**: Handle user conversations (e.g., "Lorenzo" travel assistant)
- **Planning Agents**: Generate travel plans and itineraries
- **Review Agents**: Critique and validate itineraries
- **Search Agents**: Convert natural language to structured search parameters
- **Web Surfing Agents**: Scrape and extract information from arbitrary websites using MultimodalWebSurfer

There is a lot to explore on AutoGen [Memory solutions](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/memory.html) to address this issue and offload memory from the Workflow, with the caveat that stale memory cleaning, etc,  must be implemented separatelly.

##### Todo: Actual RAG memory solution for our "Itinerary Critic" example

The intention of the "Itinerary Critic" agent was to explore realtime web retrieval. A more robust solution would be to have these source of knowledge already downloaded (e.g on a simple S3 bucket) and use something like the [RAG example](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/memory.html#building-a-simple-rag-agent) from AutoGen docs.
This should be feasible and both could play together (the documents could be retrieved at runtime via deterministic crawlers or WebModalSurfer) and stored to the knowledge base as needed, however, predownloading would be a better solution for this example with limited data to crawl

#### 6. LLM Integration

**Gemini Integration:**
- Uses Google Gemini models via OpenAI-compatible API endpoint
- Primary model: `gemini-2.5-flash` (cost-effective for most operations)
- Configured through `OpenAIChatCompletionClient` with custom `ModelInfo`
- Supports structured output (Pydantic models) and JSON schema validation

**OpenAI Integration:**
- Used for specialized tasks requiring advanced capabilities
- Web surfing capabilities via `autogen-ext[web-surfer]`
- Structured output for complex data extraction

The system uses a **two-agent team architecture** for real-time arbitrary website scraping:

1. **WebSurfer Agent** (`MultimodalWebSurfer`):
   - Navigates and scrapes websites using headless browser automation
   - Performs internal crawling, following links and using search widgets
   - Extracts content from dynamic web pages
   - Uses OpenAI GPT-4o model for navigation decisions

2. **Summarizer Agent** (`AssistantAgent`):
   - Filters and summarizes scraped content
   - Focuses only on information relevant to the query
   - Ignores irrelevant content (ads, navigation, unrelated information)
   - Provides clean, structured summaries

**How It Works:**
- The two agents work together in a `RoundRobinGroupChat` team
- WebSurfer navigates the website and extracts data
- Summarizer reviews the extracted content and filters it
- Termination condition: Summarizer appends "TERMINATE" when sufficient information is gathered
- Used for travel advisory lookups from government websites (e.g., U.S. State Department travel advisories)

**Use Case:**
This architecture is used in the `travel_advisory_lookup` function to fetch real-time travel safety information from official government websites, enabling the itinerary critique agent to validate destinations against current travel advisories.

### Integration Flow

```
User Message (Chainlit UI)
    ↓
Temporal Workflow (SelfImprovingDestinationWorkflow)
    ↓
Temporal Activity (initial_chat_activity)
    ↓
AutoGen Agent (initial_chat_agent)
    ↓
Gemini LLM (via OpenAI-compatible endpoint)
    ↓
Structured Response (Pydantic model)
    ↓
Back to Workflow → Redis → Chainlit UI
```

### Workflow Patterns

#### Self-Improving POI Workflow

The main workflow (`SelfImprovingDestinationWorkflow`) implements a self-improving loop:

1. **Initial Chat** - "Lorenzo" agent collects user requirements
2. **Itinerary Critique** - Validates itinerary against business rules and travel advisories. It may pass back the flow to Initial Chat if something needs to be changed or informed to the user.
3. **POI Query Proposal** - Converts user request to structured search parameters
4. **Google Places Search** - Executes POI search with proposed parameters
5. **POI Review** - Agent reviews results and decides:
   - **Accept**: Results are good enough → proceed to summary
   - **Refine**: Results need improvement → adjust parameters and loop back
6. **POI Summary** - Generates final itinerary summary
7. **Interactive Map Display** - Custom Chainlit element renders POIs on Google Maps with markers, info windows, and auto-zoom
8. **Circular Conversation** - Workflow continues, allowing users to modify or make new requests

**Key Features:**
- **Self-improving**: Review agent learns from previous iterations
- **Iterative refinement**: Automatically adjusts search parameters based on results
- **Circular flow**: Workflow doesn't terminate, enabling continuous conversation
- **Real-time updates**: Uses Redis pub/sub for live UI updates

### Data Models

The system uses **Pydantic** models for type safety and validation:

- `ChatConversationResult`: Agent responses with structured fields
- `POIReview`: Review decisions (accept/refine) with reasoning
- `QueryPOIParams`: Structured search parameters
- `ClientLiEvent`: Events for Chainlit UI updates
- `SelfImprovingDestinationWorkflowContext`: Workflow state management

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **uv** (Python package manager) - [Installation guide](https://github.com/astral-sh/uv)
- **API Keys**:
  - Google Gemini API key
  - OpenAI API key (for web surfing)
  - Google Places API key

### Installation

#### 1. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv

# Verify installation
uv --version
```

#### 2. Clone and Navigate

```bash
git clone <repository-url>
cd travel_planner
```

#### 3. Set Up Python Environment

```bash
cd python-worker

# Create virtual environment using uv
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install dependencies
uv sync
```

#### 4. Configure Environment Variables

Create a `.env` file in the project root (`travel_planner/.env`) or just copy and rename .env-example with your values for:

```bash
# Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# OpenAI Configuration (for web surfing and structured output)
OPEN_AI_API_KEY=your_openai_api_key_here

# Google Places API
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here

# Temporal Configuration
TEMPORAL_ADDRESS=localhost:7233

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
```

**Getting API Keys:**
- **Gemini**: Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI**: Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Google Places**: Enable Places API in [Google Cloud Console](https://console.cloud.google.com/)

#### 5. Start Infrastructure with Docker Compose

From the project root:

```bash
# Start all services (PostgreSQL, Temporal, Temporal UI, Redis)
docker-compose -f docker-compose.dev.yml up -d

# Verify services are running
docker-compose -f docker-compose.dev.yml ps

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

**Services:**
- **PostgreSQL**: `localhost:5432` (Temporal database)
- **Temporal Server**: `localhost:7233` (gRPC endpoint)
- **Temporal UI**: `http://localhost:5050` (Web UI for monitoring workflows)
- **Redis**: `localhost:6379` (Pub/Sub for real-time updates)

#### 6. Start the Application

From the `python-worker` directory:

```bash
# Make sure you're in the python-worker directory
cd python-worker

# Ensure virtual environment is activated
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Run the start script
./start.sh
```

The `start.sh` script will:
1. Set `PYTHONPATH=.` to ensure imports work correctly
2. Use `uv run` to execute Chainlit with the correct environment
3. Start the Chainlit web UI (typically at `http://localhost:8000`)

### Accessing the Application

- **Chainlit UI**: Open `http://localhost:8000` in your browser
- **Temporal UI**: Open `http://localhost:5050` to monitor workflow execution

## 

```
travel_planner/
├── docker-compose.dev.yml    # Docker Compose configuration
├── start_local.sh             # Local worker startup script
├── python-worker/
│   ├── pyproject.toml         # Python dependencies (uv)
│   ├── start.sh               # Chainlit server startup
│   ├── autogen_gemini.py     # Gemini client configuration
│   ├── app/
│   │   └── server.py         # Chainlit web server
│   ├── public/
│   │   └── elements/
│   │       └── POIMap.jsx    # Custom Google Maps element
│   ├── pois/                 # POI workflow module
│   │   ├── workflow_poi_self_improving.py  # Main POI workflow
│   │   ├── poi_agents.py                  # POI-related agents
│   │   ├── poi_models.py                  # Pydantic models
│   │   ├── pois_self_improving_activities.py  # Activity wrappers
│   │   ├── temporal_pois_worker.py       # POI worker registration
│   │   └── tools/
│   │       └── google_places_tool.py     # Google Places API integration
│   └── common/
│       ├── temporal_client.py  # Temporal client factory
│       └── get_redis.py       # Redis client factory
```

##  Development

### Running Workers Locally

For local development, you can run docker for AutoGen support and redis, then manually start the server with the following command:

```bash
docker-compose -f docker-compose.dev.yml up -d

cd python-worker
source .venv/bin/activate
./start.sh
```

The service is prepared to be run in a container, but for now this is out of scope, as is just a PoC  

- **Temporal UI**: Visit `http://localhost:5050` to see:
  - Workflow execution history
  - Activity logs and retries
  - Workflow state and signals
  - Performance metrics

Note: In temporal, you could see multiple "zombie" workflows when you restart the server. This is expected if you have multiple tabs opened as Chainlit would restablish sessions for each of them. Is recommended that you close all the tabs and cancel any leftover Workflows during development for ease of monitoring.

Is also worth mentioning that, if this was in prod, "sleeping" workflows doesn't consume resources, however, it would be highly recommended in real systems to have the wait condition (` await workflow.wait_condition(lambda: self._pending_user_reply is not None)` timeboxed and raise and handle an exception to close idle sessions (to avoid incurr in costs if using Temporal Cloud in prod)

- **Chainlit UI**: Visit `http://localhost:8000` to:
  - Chat with the travel assistant
  - See real-time workflow updates
  - View conversation history

## Key Features

### 1. Self-Improving POI Search

The POI workflow automatically refines search parameters based on review feedback:

- **Initial Search**: Agent proposes search parameters from user request
- **Review Loop**: Review agent evaluates results and decides to accept or refine
- **Learning**: Previous reviews inform future parameter adjustments
- **Convergence**: Continues until satisfactory results are found

### 2. Circular Conversation Flow

Unlike traditional workflows that terminate, this system maintains an active conversation:

- Workflow persists after itinerary creation
- Users can request modifications or new searches
- Conversation history is maintained in workflow context
- Real-time updates via Redis pub/sub
- Workflow is terminated once the chat session is disconnected. (for now the state history is also lost, but could be made persistent as well easily)

### 3. Multi-Agent Collaboration

Different agents handle specialized tasks:

- **Lorenzo**: Friendly travel assistant for user interaction
- **Itinerary Critic**: Validates itineraries against business rules
- **POI Proposer**: Converts natural language to structured search params
- **POI Reviewer**: Critically evaluates search results
- **POI Summarizer**: Creates user-friendly itinerary summaries

### 4. Structured Output

All agents return structured Pydantic models:

- Type-safe responses
- Automatic validation
- Clear data contracts
- Easy integration with workflows

### 5. Real-Time Web Scraping

The MultimodalWebSurfer - Summary Assistant architecture enables dynamic website scraping:

- **Arbitrary Websites**: Can scrape any website without pre-configuration
- **Intelligent Filtering**: Summarizer agent filters out irrelevant content
- **Real-Time Data**: Fetches current information (e.g., travel advisories) at runtime
- **Internal Navigation**: Follows internal links and uses site search features
- **Termination Control**: Automatically stops when sufficient information is gathered
- **Guardrails to prevent search engine crawling:** It's against the ToS of Bing and Google, and often results in captchas / IP banning if not in place (MultimodalWebSurfer *by default* uses Bing heavily without it)

### 6. Interactive POI Map Display

Custom Chainlit element for visualizing POIs:

- **Google Maps Integration**: Interactive map with all discovered POIs
- **Custom Markers**: Numbered markers corresponding to each POI location
- **Info Windows**: Tap markers to see detailed information (name, photo, rating, address, description)
- **Auto-Zoom**: Map automatically fits all POIs with appropriate margins for optimal viewing

### 7. Next steps:
 
- We already successfully built a "search profile" or "itinerary summary" during the initial `chat_flow()`. The intention for asking dates and budget was to have an online search for hotels scrapping either known sites (like booking) or WebModalSurfer + Google CSE  
- Likewise, the POIs search could be enhanced with online searches on TripAdvisor or similar websites, but then we would require to find the GPS location for any new activity or POI found online
- Consolidated tokens budget tracking and storage in a database, implementing token limits, throttling, etc
- Offloading the Context from the Workflow using [agent state](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tutorial/state.html). Check trade-offs of complexity vs having the state in Temporals Workflow, which is persistent by design.
- If we keep the state on the Workflow, then state persisting and restoring (using regular databases or even S3 buckets) on session start / termination, if we add an auth layer.

### 8. Testing

Testing is largely missing in this toy-project currently. Here are some possible testing strategies (feel free to suggest more):

- Activities to implement a protocol and be injected to the Workflow during instantiation
- Workflow be unit tested following Temporal's guideline and with mocked Activities. This should cover the deterministic flow control.
- Agents to be tested with known data and expected to make knonw decisions on a scheduled build run as part of CI/CD

### Common Issues

**1. Import Errors**
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=.
# Or use: PYTHONPATH=. uv run chainlit run app/server.py
```

**2. Temporal Connection Errors**
```bash
# Verify Temporal is running
docker-compose -f docker-compose.dev.yml ps temporal

# Check Temporal logs
docker-compose -f docker-compose.dev.yml logs temporal
```

**3. Redis Connection Errors**
```bash
# Verify Redis is running
docker-compose -f docker-compose.dev.yml ps redis

# Test Redis connection
redis-cli ping
```

**4. API Key Errors**
- Ensure `.env` file exists in project root
- Verify all API keys are set correctly
- Check API key permissions and quotas

**5. Port Conflicts**
- Temporal UI: Change port in `docker-compose.dev.yml` (default: 5050)
- Chainlit: Change port in `start.sh` or via `--port` flag
- PostgreSQL: Change port mapping if 5432 is in use

## 📚 Additional Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Chainlit Documentation](https://docs.chainlit.io/)


See `FILES_TO_MODIFY.md` for detailed guidance on common changes.


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with:
- [Temporal](https://temporal.io/) - Workflow orchestration
- [AutoGen](https://github.com/microsoft/autogen) - Multi-agent framework
- [Google Gemini](https://ai.google.dev/) - Language models
- [Chainlit](https://chainlit.io/) - Chat UI framework

