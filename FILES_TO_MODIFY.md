# Files to Modify for Common Changes

This document lists which files you'll need to modify for various types of changes to the travel planner system.

## 1. Modifying Agent Prompts/Behavior

**Files to modify:**
- `python-worker/pois/poi_agents.py` - Update `system_message` for POI agents

**Specific agents:**
- **Lorenzo (Chat)**: `initial_chat_agent()` in `pois/poi_agents.py`
- **POI Proposer**: `propose_poi_query()` in `pois/poi_agents.py`
- **POI Reviewer**: `review_poi_results()` in `pois/poi_agents.py`
- **POI Summarizer**: `summarize_poi_results()` in `pois/poi_agents.py`
- **Itinerary Critic**: `critize_user_itinerary()` in `pois/poi_agents.py`
- **Update Title Generator**: `generate_update_title()` in `pois/poi_agents.py`

---

## 2. Changing LLM Model or Provider

**Files to modify:**
- `python-worker/autogen_gemini.py` - Update model configuration, base URL, API key handling
- `python-worker/pois/poi_agents.py` - Update model client creation (for agents using different models)

**Key locations:**
- `create_gemini_model_client()` - Default Gemini client factory
- `run_single_agent()` - Single agent runner with Gemini
- `critize_user_itinerary()` - Uses OpenAI GPT-5
- `travel_advisory_lookup()` - Uses OpenAI GPT-4o

---

## 3. Adding a New POI Search Tool or Data Source

**Files to modify:**
- `python-worker/pois/tools/google_places_tool.py` - Add new tool function or modify existing
- `python-worker/pois/poi_models.py` - Add/update data models if needed
- `python-worker/pois/pois_self_improving_activities.py` - Add activity wrapper if new tool
- `python-worker/pois/workflow_poi_self_improving.py` - Integrate new tool in workflow if needed
- `python-worker/pois/temporal_pois_worker.py` - Register new activity if added

---

## 4. Modifying Workflow Logic (Order, Conditions, Loops)

**Files to modify:**
- `python-worker/pois/workflow_poi_self_improving.py` - SelfImprovingDestinationWorkflow logic

**Common changes:**
- Reordering agent execution
- Adding conditional logic
- Changing retry/refinement logic
- Adding new workflow steps

---

## 5. Changing Data Models/Schemas

**Files to modify:**
- `python-worker/pois/poi_models.py` - POI workflow models
- `python-worker/pois/tools/google_places_tool.py` - `DestinationPOI` model
- Any workflow/activity files that use these models

**Models defined:**
- `QueryPOIParams` - POI search parameters
- `POIReview` - Review decision and feedback
- `POIReviewInput` - Input to review agent
- `POISummaryInput` - Input to summary agent
- `ChatConversationResult` - Chat agent response
- `CritiqueItineraryResult` - Critique decision
- `DestinationPOI` - POI data structure
- Various context/history models

---

## 6. Modifying UI/Real-time Updates

**Files to modify:**
- `python-worker/app/server.py` - Chainlit UI handlers, pub/sub consumption
- `python-worker/pois/pois_self_improving_activities.py` - `publish_clientli_message_activity()` - Message publishing
- `python-worker/pois/workflow_poi_self_improving.py` - `_send_user_message()` - When messages are sent

**Key functions:**
- `consume_pubsub_events()` - Receives Redis messages
- `publish_clientli_message_activity()` - Publishes to Redis
- `on_message()`, `on_chat_start()`, `on_chat_end()` - Chainlit hooks

---

## 7. Adding New Activities

**Files to modify:**
- Create activity function in `pois/pois_self_improving_activities.py`
- `python-worker/pois/temporal_pois_worker.py` - Register in worker
- Update workflow file to call the activity

---

## 8. Changing Infrastructure/Deployment

**Files to modify:**
- `docker-compose.dev.yml` - Service configuration, ports, environment
- `python-worker/Dockerfile` - Container image build
- `python-worker/pyproject.toml` - Dependencies
- `python-worker/common/get_redis.py` - Redis connection settings
- `python-worker/common/temporal_client.py` - Temporal connection settings

---

## 9. Adding Error Handling/Retries

**Files to modify:**
- Activity files - Add try/except blocks
- Workflow files - Add error handling in workflow logic
- `python-worker/pois/workflow_poi_self_improving.py` - Already has some error handling for Google Places

---

## 10. Modifying Travel Advisory/Safety Checks

**Files to modify:**
- `python-worker/pois/poi_agents.py` - `critize_user_itinerary()` - Critique logic and rules
- `python-worker/pois/poi_agents.py` - `travel_advisory_lookup()` - Web lookup implementation
- `python-worker/pois/workflow_poi_self_improving.py` - `_critique_initial_itinerary()` - Critique workflow integration

---

## 11. Changing Task Queues

**Files to modify:**
- `python-worker/pois/temporal_pois_worker.py` - POI worker task queue
- `python-worker/run_poi_workflow.py` - Client task queue
- `python-worker/app/server.py` - Client task queue
- `python-worker/pois/workflow_poi_self_improving.py` - Workflow task queue (in `start_or_replace_workflow()`)

---

## 12. Adding New Workflow Signals

**Files to modify:**
- Workflow file (e.g., `pois/workflow_poi_self_improving.py`) - Add `@workflow.signal` method
- `python-worker/app/server.py` - Add signal sending logic in `on_message()` or other handlers

---

## 13. Modifying Chat Agent Behavior (Lorenzo)

**Files to modify:**
- `python-worker/pois/poi_agents.py` - `initial_chat_agent()` - System message and logic
- `python-worker/pois/poi_models.py` - `ChatConversationResult`, `ChatConversationRequest` if schema changes needed

---

## 14. Changing POI Selection/Filtering Logic

**Files to modify:**
- `python-worker/pois/poi_agents.py` - `review_poi_results()` - Selection criteria in system message
- `python-worker/pois/tools/google_places_tool.py` - `search_google_places()` - Filtering logic

---

## Quick Reference: Most Frequently Modified Files

1. **Agent Prompts**: `pois/poi_agents.py`
2. **Workflow Logic**: `pois/workflow_poi_self_improving.py`
3. **Data Models**: `pois/poi_models.py`, `pois/tools/google_places_tool.py`
4. **UI/Real-time**: `app/server.py`, `pois/pois_self_improving_activities.py`
5. **Infrastructure**: `docker-compose.dev.yml`, `pyproject.toml`

