from typing import List, Optional, Dict, Any

from temporalio import activity

from pois.tools.google_places_tool import DestinationPOI, search_google_places
from common.get_redis import get_redis
from pois.poi_models import ClientLiEvent
import json

from pois.poi_models import (
    POISummaryInput,
    POIReviewInput,
    QueryPOIParams,
    POIReview,
    ChatConversationResult, 
    ChatMessageHistory,
    ChatConversationRequest,
    CritiqueItineraryRequest,
    CritiqueItineraryResult,
    CritiqueItineraryToolParams,
    CritiqueItineraryWebLookupResult,
    GenerateUpdateTitleRequest
)
from pois.poi_agents import (
    propose_poi_query,
    review_poi_results,
    summarize_poi_results,
    initial_chat_agent,
    critize_user_itinerary,
    travel_advisory_lookup,
    generate_update_title
)

@activity.defn
async def initial_chat_activity(params: ChatConversationRequest) -> ChatConversationResult:
    """
    Initiates / continues a conversation and emits a ChatConversationResult, which contains either
    the user summary for search , or a follow up message to the user 
    """
    conversation_result = await initial_chat_agent(params.message, params.history)
    return conversation_result

@activity.defn
async def critize_user_itinerary_activity(params: CritiqueItineraryRequest) -> CritiqueItineraryResult:
    """
    Critizies the initial itinerary draft looking for missing information, and compliance with business policy
    """
    critize_result = await critize_user_itinerary(
        itinerary=params.itinerary,
        context=params.context
    )
    return critize_result 

@activity.defn
async def travel_advisory_lookup_activity(params: CritiqueItineraryToolParams) -> str:
    """
    Runs a web lookup into the travels itinerary website and return the information for the requested countries
    """
    travel_advisory_lookup_result = await travel_advisory_lookup(
        params=params
    )
    return travel_advisory_lookup_result

@activity.defn
async def propose_poi_query_activity(user_request: str) -> QueryPOIParams:
    """
    Activity that wraps the parameter-proposing agent.
    Returns (params, usage).
    """
    params = await propose_poi_query(user_request)
    return params


@activity.defn
async def google_places_activity_with_params(params: QueryPOIParams) -> List[DestinationPOI]:
    """
    Activity that calls the Google Places tool using the given params dict.
    """
    pois = await search_google_places(
        city= params.city,
        query= params.query,
        country=params.country,
        max_results=params.max_results,
        poi_types=params.poi_types,
    )
    return pois


@activity.defn
async def review_poi_results_activity(
    payload: POIReviewInput,
) -> POIReview:
    """
    Activity that wraps the reviewer agent.
    Returns (review_dict, usage_dict).
    """
    return await review_poi_results(
        payload
    )

@activity.defn
async def summarize_pois_activity(
   payload: POISummaryInput,
) -> str:
    """
    Activity that wraps the POI summarization agent.
    Returns (summary_dict, usage_dict).
    """

    summary = await summarize_poi_results(
       payload
    )
    return summary


@activity.defn
async def generate_update_title_activity(
    payload: GenerateUpdateTitleRequest
) -> str:
    """
    Activity that wraps the update title agent.
    Generates a brief title for update messages in the user's language.
    """
    return await generate_update_title(
        update_content=payload.content,
        user_language=payload.user_language,
    )


@activity.defn
async def publish_clientli_message_activity(event: ClientLiEvent) -> None:
    redis = get_redis()
    channel = f"chainlit:poi:events:{event.session_id}"
    redis.publish(channel, event.model_dump_json())