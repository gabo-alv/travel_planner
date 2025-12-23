from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from dataclasses import dataclass, asdict
from pois.tools.google_places_tool import DestinationPOI


class ChatConversationResult(BaseModel):
    response: str = Field(..., description="The agent's response message")
    user_itinerary_request_summary: Optional[str] = Field(..., description="A summary of the complete user request, when the agent deems it complete")
    user_language: Optional[str] = Field(..., description="The user's language")




class QueryPOIParams(BaseModel):
    city: str = Field(..., description="City name where to search for POIs")
    country: Optional[str] = Field(..., description="Country name (optional)")
    max_results: int = Field(..., description="Maximum number of POI results to return")
    poi_types: Optional[List[str]] = Field(
        None, description="List of POI types/categories to filter the search"
    )
    query: Optional[str] = Field(
        None,
        description=(
            "Custom free-text query for searching POIs. "
        ),
    )


class POIReview(BaseModel):
    decision: str = Field(..., description="Either 'refine' or 'approve' according to your decision")
    reason: str = Field(..., description="Natural language reason for your decision")
    new_params: Optional[QueryPOIParams] = Field(
        None, description="New parameters for POI search if refining"
    )
    selected_pois: Optional[List[DestinationPOI]] = Field(
        None, description="List of selected POIs that match the user's intent"
    )


class POIReviewInput(BaseModel):
    user_request: str = Field(..., description="Original user request for POIs")
    user_language: str = Field(..., description= "The language of the user, use it for redacting the reason summary.")
    params: QueryPOIParams = Field(..., description="Parameters used for the POI search")
    last_search_pois: List[DestinationPOI] = Field(..., description="List of POIs retrieved from the latest search")
    pois_selected_so_far: Optional[List[DestinationPOI]] = Field(
        None, description="POIs selected in previous iterations, if any"
    )
    previous_reviews: Optional[List[POIReview]] = Field(
        None, description="Context history of previous reviews to consider"
    )
    last_error: Optional[str] = Field(None, description="Last error message from the POI search tool, if any")


class POISummaryInput(BaseModel):
    user_language: str = Field(..., description = "The language in which the summary must be written")
    user_request: str = Field(..., description="Original user request for POIs")
    pois: List[DestinationPOI] = Field(..., description="Final list of selected POIs to summarize")



class ClientLiEvent(BaseModel):
    session_id: str            
    type:  str
    content: str
    is_final: bool
    title: Optional[str] = Field(default=None, description="Optional title for update messages")
    poi_data: Optional[List[Dict[str, Any]]] = Field(default=None, description="POI data for map display")

class ChatMessageHistory(BaseModel):
    source: str
    message: str

class CritiqueFeedbackMessage(BaseModel):
    current_itinerary: str
    critique_feedback: str    


class CritiqueItineraryToolParams(BaseModel):
    url: str
    query: str = Field(..., description="Natural language description of which countries are in the list that you are looking information about.") 

class CritiqueItineraryResult(BaseModel):
    decision: str = Field(..., decription = "The decision of the initial itinerary critique. Should be 'approve' if everything is complete and follows the rules, 'refine' if something must be refined or 'use_tool' if you need to fetch external information"),
    feedback: str = Field (..., description = "A natural language feedback , in English, of what is wrong if the decision is 'refine' or 'warning' , that will be sent to the agent in charge of creating the itinerary summary, explaining any concerns with the current itinerary")
    tool_params: Optional[CritiqueItineraryToolParams]



class CritiqueItineraryWebResults(BaseModel):
    url: Optional[str] = Field(..., description="URL where the advisory was found")
    country: str = Field(..., description="Country name as shown on the site")
    advises: str = Field(..., description="Natural language advisory summary for this country")
    level: Optional[str] = Field(None, description="If available (e.g., Level 4 - Do Not Travel)")

class CritiqueItineraryWebLookupResult(BaseModel):
    results: list[CritiqueItineraryWebResults]
    err: Optional[str]
    termination_state: Optional[str]


class CritiqueItineraryContext(BaseModel):
    itinerary: str
    decision: Optional[str]
    feedback: Optional[str] 
    travel_advise: Optional[str]

class CritiqueItineraryRequest(BaseModel):
    itinerary: str 
    context: list[CritiqueItineraryContext] = []

class ChatConversationRequest(BaseModel):
    message: Optional[str]
    history: list[ChatMessageHistory]
    critique_feedback: Optional[CritiqueFeedbackMessage] = None

class GenerateUpdateTitleRequest(BaseModel):
    content: str
    user_language: str
