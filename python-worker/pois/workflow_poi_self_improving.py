# workflow_poi_self_improving.py
from datetime import timedelta
from typing import Dict, Any, List, Optional
import json
from dotenv import load_dotenv
import os
from temporalio import workflow
from temporalio.exceptions import ActivityError
from pydantic import BaseModel

load_dotenv()


with workflow.unsafe.imports_passed_through():
    from pois.pois_self_improving_activities import (
        initial_chat_activity,
        propose_poi_query_activity,
        google_places_activity_with_params,
        review_poi_results_activity,
        summarize_pois_activity,
        publish_clientli_message_activity,
        critize_user_itinerary_activity,
        travel_advisory_lookup_activity,
        generate_update_title_activity,
    )
    from pois.poi_models import (
        QueryPOIParams, DestinationPOI, POIReview, POISummaryInput, POIReviewInput, ChatConversationResult, ClientLiEvent,
        ChatMessageHistory, ChatConversationRequest,
          CritiqueFeedbackMessage, 
          CritiqueItineraryContext, 
          CritiqueItineraryRequest,
          CritiqueItineraryResult,
          CritiqueItineraryWebLookupResult,
          CritiqueItineraryToolParams,
          GenerateUpdateTitleRequest
    )
    from pois.tools.google_places_tool import DestinationPOI


class SelfImprovingDestinationWorkflowContext(BaseModel):
    user_session_id: str = ""
    user_language: Optional[str] = None
    main_chat_history: list[ChatMessageHistory] = []
    itinerary_critique_history: list[CritiqueItineraryContext] = []

@workflow.defn
class SelfImprovingDestinationWorkflow:
    """
    Self-improving POI search:

    1) LLM agent proposes params.
    2) Tool (Google Places) is called.
    3) Reviewer agent evaluates output.
    4) If "refine" and attempts < max_attempts, loop with new params.
    5) Return final params + POIs + review (and optionally usage).
    """

    def __init__(self) -> None:
        # for future interactive mode
        self._pending_user_reply: str | None = None
        self.context = SelfImprovingDestinationWorkflowContext()


    @workflow.signal
    async def user_reply(self, message: str) -> None:
        self._pending_user_reply = message
        

    @workflow.run
    async def run(
        self,
        session_id: str,
        max_attempts: int = 20,
    ) -> None:
        while(True):
            self.context.user_session_id = session_id
            user_request = await self._chat_flow()
            await  self._execute_poi_search_flow(user_request)

    async def _chat_flow(self) -> Optional[str]:
        """
        Handles chat flow with the user, collecting itinerary requirements.
        
        Args:
            post_itinerary_mode: If True, when an itinerary is accepted, execute POI search
                                and continue looping instead of returning. If False, returns
                                the itinerary when accepted (for initial flow).
        
        Returns:
            Optional[str]: The itinerary summary if accepted in initial mode, None if in
                         post-itinerary mode (continues looping).
        """
        while(True):
            await workflow.wait_condition(lambda: self._pending_user_reply is not None)
            self.context.main_chat_history.append(ChatMessageHistory(source="user", message=self._pending_user_reply))
            print("waiting for user reply")
            result: ChatConversationResult = await workflow.execute_activity(
                initial_chat_activity,
                ChatConversationRequest(
                    message= self._pending_user_reply if self._pending_user_reply is not None else "",
                    history = self.context.main_chat_history
                ), start_to_close_timeout = timedelta(minutes=2)
            )
            self.context.main_chat_history.append(ChatMessageHistory(source="Lorenzo", message= result.response))
            await self._send_user_message("message", result.response, is_final=result.user_itinerary_request_summary is None)
            if result.user_language is not None:
                self.context.user_language = result.user_language
            if result.user_itinerary_request_summary is not None and result.user_itinerary_request_summary != "null" and len(result.user_itinerary_request_summary) > 2:
                self.context.main_chat_history.append(ChatMessageHistory(source="Initial itinerary", message= result.user_itinerary_request_summary))
                
                critique_result = await self._critique_initial_itinerary(result.user_itinerary_request_summary)
                
                match critique_result.decision.lower().strip():

                    case "accept":
                        return result.user_itinerary_request_summary
                    case "warning":
                        self.context.main_chat_history.append(
                            ChatMessageHistory(
                                message = f"{critique_result.model_dump_json()}",
                                source="critique"
                            )
                        )
                        warning_message = await workflow.execute_activity(
                             initial_chat_activity,
                             ChatConversationRequest(
                                    message="" ,
                                    critique_message= CritiqueFeedbackMessage(
                                        current_itinerary = result.user_itinerary_request_summary,
                                        critique_feedback = critique_result.feedback  
                                    ),
                                    history = self.context.main_chat_history
                            ), start_to_close_timeout = timedelta(minutes=2)
                        )
                        self._pending_user_reply = None
                        # Warnings might still require additional information, in which case the summary will be null
                        await self._send_user_message("message",warning_message.response, is_final=warning_message.user_itinerary_request_summary is None)
                        self.context.main_chat_history.append(
                            ChatMessageHistory(
                                message=warning_message.response,
                                source="Lorenzo"
                            )
                        )
                        if warning_message.user_itinerary_request_summary is not None:
                            return warning_message.user_itinerary_request_summary

                    case "refine":
                        current_itinerary = result.user_itinerary_request_summary
                        self.context.main_chat_history.append(
                            ChatMessageHistory(
                                message = f"{json.dumps(critique_result.model_dump())}",
                                source="critique"
                            )
                        )
                        refine_message = await workflow.execute_activity(
                             initial_chat_activity,
                             ChatConversationRequest(
                                    message= "",
                                    critique_message= CritiqueFeedbackMessage(
                                        current_itinerary = current_itinerary,
                                        critique_feedback = critique_result.feedback  
                                    ),
                                    history = self.context.main_chat_history
                            ), start_to_close_timeout = timedelta(minutes=2)
                        )
                        self.context.main_chat_history.append(
                            ChatMessageHistory(source="Lorenzo", message=refine_message.response)
                        )
                        self._pending_user_reply = None
                        await self._send_user_message("message", refine_message.response, is_final= True)
            else:
                self._pending_user_reply = None



    async def _critique_initial_itinerary(self, itinerary_summary: str) -> CritiqueItineraryResult:
        print(f"Calling critique for summary: \n{itinerary_summary}")
        while(True):
            critique_result = await workflow.execute_activity(
                critize_user_itinerary_activity,
                CritiqueItineraryRequest(
                    itinerary = itinerary_summary,
                    context = self.context.itinerary_critique_history
                ),  start_to_close_timeout = timedelta(minutes=2)                
            )
            self.context.itinerary_critique_history.append(
                CritiqueItineraryContext(
                    itinerary = itinerary_summary,
                    decision= critique_result.decision,
                    feedback = critique_result.feedback,
                    travel_advise = None
                )
            )
            if critique_result.decision.lower().strip() == "use_tool" and critique_result.tool_params is not None:
                print(f"Executing web search, params {json.dumps(critique_result.model_dump())}")
                try:
                    web_lookup_results: str = await workflow.execute_activity(
                        travel_advisory_lookup_activity,
                        critique_result.tool_params,
                         start_to_close_timeout = timedelta(minutes=2)
                    )
                    self.context.itinerary_critique_history.append(
                        CritiqueItineraryContext(
                            itinerary =  itinerary_summary,
                            decision = "",
                            feedback = None,
                            travel_advise=web_lookup_results
                        )
                    )
                except Exception as e:
                    raise ActivityError(f"{e}")
            else:
                if critique_result.decision is None or critique_result.decision.lower().strip() not in ["accept", "refine", "warning"]:
                    # Guard for the rest of valid values , temporal will retry the activity
                    raise ActivityError(f"Got invalid critique response {critique_result.model_dump_json()}")
                return critique_result
    
    
    async def _execute_poi_search_flow(self, user_request: str) -> None:
        """
        Executes the POI search flow for a given user request.
        This is extracted from the main run() method to be reusable.
        """
        log = workflow.logger
        
        # Propose initial params
        params = await workflow.execute_activity(
            propose_poi_query_activity,
            user_request,
            start_to_close_timeout=timedelta(minutes=2),
        )
        
        log.info("[POI] Initial params: %s", params)
        attempt = 0
        total_selected_pois: List[DestinationPOI] = []
        last_pois: List[DestinationPOI] = []
        last_reviews: List[POIReview] = []
        last_error: str | None = None
        
        while True:
            attempt += 1
            log.info("[POI] Attempt #%s using params=%s", attempt, params)
            
            # Call the tool
            try:
                await self._send_user_message(
                    type="update",
                    message="Searching",
                    is_final=False
                )
                pois = await workflow.execute_activity(
                    google_places_activity_with_params,
                    params,
                    start_to_close_timeout=timedelta(minutes=2),
                )
                
                last_pois = list({p.id: p for p in last_pois + pois}.values())
                
            except ActivityError as e:
                last_error = f"[POI] Error calling Google Places: {e}"
                pois = []
            
            log.info("[POI] Retrieved %s POIs", len(pois))
            
            # Reviewer agent
            review = await workflow.execute_activity(
                review_poi_results_activity,
                POIReviewInput(
                    user_language=self.context.user_language or "",
                    user_request=user_request,
                    params=params,
                    last_search_pois=last_pois,
                    pois_selected_so_far=total_selected_pois,
                    previous_reviews=last_reviews,
                    last_error=last_error,
                ),
                start_to_close_timeout=timedelta(minutes=3),
            )
            
            decision = review.decision
            
            if decision != "refine" or attempt >= 20:  # max_attempts
                # Done
                if review.selected_pois is not None:
                    last_pois = review.selected_pois
                total_selected_pois = list({p.id: p for p in total_selected_pois + last_pois}.values())
                break
            
            # Generate dynamic title for the update message
            update_title = await workflow.execute_activity(
                generate_update_title_activity,
                GenerateUpdateTitleRequest(
                    content = review.reason,
                    user_language = self.context.user_language
                ),
                start_to_close_timeout=timedelta(minutes=2),
            )
            
            await self._send_user_message(
                type="update",
                message=review.reason,
                is_final=False,
                title=update_title
            )
            
            # Refine and loop again
            new_params = review.new_params
            selected_pois = review.selected_pois
            last_reviews.append(review)
            
            log.info("[POI] Refining params to: %s", new_params)
            params = new_params
            if selected_pois is not None:
                last_pois = selected_pois
            total_selected_pois = list({p.id: p for p in total_selected_pois + last_pois}.values())
        
        # Summarization
        summary_input = POISummaryInput(
            user_language=self.context.user_language or "",
            user_request=user_request,
            pois=total_selected_pois,
        )
        
        summary = await workflow.execute_activity(
            summarize_pois_activity,
            summary_input,
            start_to_close_timeout=timedelta(minutes=2),
        )
        
        # Send the full summary to the user
        await self._send_user_message(
            type="message",
            message=summary,
            is_final=False
        )
        self.context.main_chat_history.append(
            ChatMessageHistory(source="Lorenzo", message=summary)
        )
        
        # Send POI data for map display
        poi_data = [poi.model_dump() for poi in total_selected_pois]
        await self._send_pois(
            is_final=True,
            poi_data=poi_data
        )
        self._pending_user_reply = None

    async def _send_user_message(
        self, 
        type: str, 
        message: str, 
        is_final: bool, 
        title: Optional[str] = None,
    ) -> None:
         await workflow.execute_activity(
                publish_clientli_message_activity,
                ClientLiEvent(
                    session_id= self.context.user_session_id,
                    type=type,
                    content=message,
                    is_final=is_final,
                    title=title,
                ),
                start_to_close_timeout=timedelta(minutes=2),
            )


    async def _send_pois(self, poi_data: List[Dict[str, Any]], is_final: bool) -> None:
            event = ClientLiEvent(
                session_id=self.context.user_session_id,
                type="poi_map",
                content="",
                is_final=is_final,
                title=None,
                poi_data=poi_data
            )
            
            await workflow.execute_activity(
                publish_clientli_message_activity,
                event,
                start_to_close_timeout=timedelta(minutes=2),
            )





