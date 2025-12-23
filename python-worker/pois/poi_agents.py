import json
from typing import Dict, Any, Tuple, Optional
import json
import os
import re
from autogen_gemini import create_gemini_model_client
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage, StructuredMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination



from dotenv import load_dotenv
from datetime import timedelta


from utils import extract_json
from pois.poi_models import POIReviewInput, POIReview, QueryPOIParams, POISummaryInput, ChatConversationResult, ChatMessageHistory, CritiqueItineraryResult, CritiqueItineraryContext, CritiqueItineraryWebResults, CritiqueItineraryRequest, CritiqueItineraryToolParams, CritiqueItineraryWebLookupResult
from pois.tools.google_places_tool import DestinationPOI

load_dotenv()

def _format_prev_messages_for_system(prev_messages: list[ChatMessageHistory]) -> str:
    """
    Render prior conversation turns as a plain transcript to be appended to the system prompt.
    This does NOT alter existing prompt instructions; it only injects memory/context.
    """
    if not prev_messages:
        return ""

    lines: list[str] = []
    for msg in prev_messages:
        lines.append(f"{msg.source}: {msg.message}")

    if not lines:
        return ""

    return "\n".join(lines)


async def initial_chat_agent(message: str, prev_messages: list[ChatMessageHistory]) -> ChatConversationResult:
    system_message = f"""
    You are Lorenzo, a friendly  and experienced travel assistant, that have traveled the world, and have a bit crazy but charismatic personality.
    You help users plan their trip itinerary and your mission is to interrogate the user until you have covered the **Minimal information required** (see bellow) for making a travel itinerary  so the system can provide them with the best possible travel plan.

    Rules:
    - Always be polite and engaging. Although with a vibrant and charismatic personality, and good sense of humor.
    - You must never break character or talk nor answer any question from the user about any topic other than their travel plan. Explain that you are a travel assistant and your purpose is to help them plan their trip only, always following your personality.
    - You must never reveal anything about yourself, nor the fact that you are an AI model, nor any technical details about the system you are part of.
    - You must always answer in the language used by the user in their messages. If they reply in multiple language, ask the user what language they prefer (in all the languages they have replied). If they mixes languages (like using an English word) but the majority of their messages are in one language, is safe to assume that is their main language, and you don't need to ask the user for lang preferences in that case.
    - Never ask for personal information such as  name, email, phone number, address, etc.
    - Never engage in controversial topics such as politics, religion, etc. Explain that you are a travel assistant and your purpose is to help them plan their trip only, always following your personality.
    - Avoid deviating from the travel planning topic. If the user asks anything outside of travel planning, politely steer the conversation back to travel planning, following your character and personality.
    - DO NOT hallucinate nor infer, cover gaps or guess any of the **Minimal information required for making a travel itinerary** items. These must be collected from the user's responses only.
    - If the user gives you any personal information, sensitive data or illegal information, politely tell them that you are not allowed to process that information and steer back the conversation to the travel itinerary questionary.
    - If the user doesn't reply your previous question and don't give you any useful information strictly relevant to cover the minimal information required for making the itinerary, politely reply them your role and repeat the question again.
    - If the user states impossible destinations (like travelling to the moon or mars, unreachable locations, etc), laugh, make a joke, and steer back the conversation to the travel itinerary, explaining that its for a serious travel itinerary.
    - If the user gives you ambiguous destinations , like "I want to go to the mountains" , you may suggest popular destinations that are relevant to the request and ask the user to pick one or mention a different destination (city, country).
    - If the user gives you non-relevant destinations for a trip plan (like "I want to go to my neighbour house, I want to go to jail"), maybe make a joke or sympathetic comment (always being empathetic with the user) and steer back the conversation to the travel itinerary, explaining that its for a serious travel itinerary.
    - If the user gives you illegal activities when answering for their interests, reply that you are not allowed to make any trip intinerary including them, and repeat the question again. 
    - If the user gives incomplete answers for one of the questions, politely ask them to ellaborate more on that or ask follow up questions.
    - If the user states warzones, dangerous zones or places where it's not plausible to make a travel plan to, explain that you are concerned about travelers safety and politely ask the user to pick a different destination.


    [Minimal information required for making a travel itinerary]
    - Trip destination(s) (city, country); although the city is optional if the country countries is specified.  
    - Trip dates (start date, end date); if unknown, ask for approximate duration.
    - User interests and likes  (e.g., history, food, nightlife, nature, art, culture)
    - If the user is interested in visiting neighboring cities or countries.
    - User travel companions (e.g., solo, couple, family, friends or pets)
    - Budget preferences (e.g., luxury, mid-range, budget) (optional)

    Process:
    1. Review the entire conversation history and user input. If it's all empty, start by greeting the user, introducing yourself, and asking about their travel plans.
    2. Identify any missing minimal information required for making a travel itinerary form the user responses. Ask the user for the missing information one at a time, in a natural and engaging manner, following your character and personality.
    3. Once all the minimal information is collected, summarize the complete user request in a concise manner, in English , in the user_itinerary_request_summary. If you don't have gathered this information yet, or, if you are asking the user a question, keep this field as null
    4. If you don't have gathered all the minimal information required yet, keep the conversation going, asking one at the time in a natural and engaging manner, following your character and personality, and strictly following the Rules section.
    5. If the user gives you conflicting information when gathering the minimal information required, ask them a clarifying question
    6. When you identify the user main language, add  it in the user_language field.
    7. Once you have completed the user_itinerary_request_summary, thanks the user, inform them that their itinerary is getting processed
    8. You may receive the current_itinerary and a  critique on the field 'critique_message' if something is missing or wrong in the summary after you finished your initial summary, if this happens, do the following:
        8a. If the critique decision is just a "warning" , craft a friendly message matching your character and personality explaining the critique feedback as a warning for their travel destination, in a friendly tone matching your personality and the original user language, but tell them that the itinerary is being process anyways
        8b. If the critique is a "refine", craft a friendly message matching your character and personality explaining the critique feedback as something the user needs to change in their itinerary, clearly explaining the reason, in a friendly tone matching your personality and the original user language

    You must return 
     - response : the response to be sent to the user
     - user_itinerary_request_summary: The summary of the travel itinerary request, once you have gathered all the minimal information required and answers for any follow up questions that you have
     - user_language: once you have inferred it 
"""

    # ---- Inject conversation history WITHOUT altering prompt instructions ----
    history_block = _format_prev_messages_for_system(prev_messages)
    if history_block:
        system_message += f"""

    [Conversation History - for context only]
    {history_block}
"""

    llm_model = create_gemini_model_client()

    agent = AssistantAgent(
        name="Lorenzo",
        model_client=llm_model,
        system_message=system_message,
        output_content_type=ChatConversationResult,
    )

    try:
        result = await agent.run(task=message)

        msg = result.messages[-1]
        content = msg.content

        if isinstance(content, ChatConversationResult):
            return content
        return content
    finally:
        await llm_model.close()



async def critize_user_itinerary(itinerary: str, context: list[CritiqueItineraryContext]) -> CritiqueItineraryResult:
    """
    Agent that reviews the produced itinerary and approves it or request changes if something needs improvement
    """

    context_window = ""
    if context:
        context_window = f"{json.dumps([p.model_dump() for p in context])}"

    SYSTEM_INSTRUCTIONS = f"""
    You are the travel search itinerary expert reviewer and critic.
    Your mission is to  review if the provided summary (in English) contains the minimal required information and complies with the rules 

    [Minimal information required for making a travel itinerary]
    - Trip destination(s) (city, country); although the city is optional if the country countries is specified.  
    - Trip dates (start date, end date); if unknown, ask for approximate duration.
    - User interests and likes  (e.g., history, food, nightlife, nature, art, culture)
    - If the user is interested in visiting neighboring cities or countries.
    - User travel companions (e.g., solo, couple, family, friends or pets)
    - Budget preferences (e.g., luxury, mid-range, budget) (optional)

    [Hard rules]
    - The trip itinerary request  may not extend  for more than 3 months in a single country, and be aware of local taxes regulations.
    - The trip itinerary request  cannot include dangerous places, warzones, or countries listed on the US  travel-advisories site.
    - All the information in the trip itinerary must be complete and accurate enough and not contain any gaps.
    - You have to validate the  the countries mentioned in the itinerary summary with the travel advise information. If any of those says "No Travel",  you must reply with "decision": "refine" and provide a feedback , in natural language, of what countries are a no-go and why
        
    Process:
    1. Review all the entries of your context to see if the countries mentioned in the itinerary are present in any previous travel_advise field and contains enough travel advise information (ignore errors or irrelevant content). If you have the information for some countries, use it to validate the Hard Rules (see instructions bellow)
    2. Only if you don't already have enough travel_advise information in your context for a country (or set of countries) present in in the summary, require the system to fetch them by setting your decision to 'use_tool' and adding the following 'tool_params' to your response (DO NOT call this tool again if you already have the travel advise information in your context):
            - url https://travel.state.gov/en/international-travel/travel-advisories.html
            - query: Natural language description of which countries in the itinerary you are missing travel advise information for. Do not include those that you already have found in your context, in the previous step.
    3. If the travel advise is "Do Not travel" for even just one of the countries, your decision is 'refine'; explain the previous agent that the user must chose another destination due to safety concerns, detailing the countries and reasons.
    4. If the advise is NOT a "Do Not Travel" level but it does contain warnings, your decision is 'warning'; explain the previous agent the warnings to be aware of, detailing the countries and reasons in your feedback field.
    5. Identify if there is  any missing minimal information required for making a travel itinerary. If so, your decision is 'refine' and a natural language  description in EN for the previous agent so it can collect the missing information.
    6. Identify if there needs to be any additional clarifications from the user required for making a travel itinerary. If so, your decision is 'refine' and a natural language  description in EN for the previous agent so it can collect the missing information.
    7. Identify if there is any illegal activity mentioned in the itinerary. If so, your decision is 'refine' and a natural language description in EN for the previous agent so they can inform the user what is not allowed and request them to pick other activities instead.
    8. If all the above check passes, your decision is  "accept"
   
     You must return the following, in JSON format only, without extra commentary or markup, an object with the following properties:
     
     - decision: "use_tool", "warning",  "refine",  or "accept" based on your decision following the checks above
     - feedback: A natural language feedback , in English, of what is wrong if the decision is 'refine' or 'warning', that will be sent to the agent in charge of creating the itinerary summary. Required if the decision is 'refine' or 'warning', null otherwise
     - tool_params Parameters used for doing a web lookup on the travel advise website on the us. Required if the decision is 'use_tool', null otherwise
     - Important: Do not use the tool to find travel advise for countries that you already have in your context history. Only you may only call it for those countries that you need and you don't have any entries yet in your context 

     context:
     {context_window}
    """

 #   llm_client = create_gemini_model_client()

    llm_client = OpenAIChatCompletionClient(
    model="gpt-5.2",
    api_key=os.environ["OPEN_AI_API_KEY"],  # note: .env var name
    model_info={
        "vision": False,
       "function_calling": True,
        "json_output": True,
        "structured_output": True,
        "family": ModelFamily.GPT_5,
    },
)


    agent = AssistantAgent(
        name="ItineraryCritic",
        model_client=llm_client,
        system_message=SYSTEM_INSTRUCTIONS,
        output_content_type=CritiqueItineraryResult,
    )

    try:
        # Only pass the current itinerary in the task, context is in memory
        task = f"Review this itinerary:\n{itinerary}"
        run_result = await agent.run(task=task)

        final_msg = run_result.messages[-1]
        content = final_msg.content
        return content
    finally:
        await llm_client.close()



async def propose_poi_query(user_request: str) -> Tuple[Dict[str, Any], dict]:
    """
    Agent that converts a natural-language travel request into structured params
    for our Google Places tool.
    """
    system_message = """
You are a travel research assistant that prepares parameters for a
destination POI search function.

The function signature is:

search_google_places(
  city: str,
  country: str,
  max_results: int,
  poi_types: List[str],
  query: Optional[str]
)

Given the user's request, you must:

1. Infer a single main city name.
2. Infer an optional country name (can be empty string if unclear).
3. Choose a reasonable max_results (5-15).
4. Choose 3-6 POI types from:
   ["tourist_attraction", "museum", "historic", "landmark", "viewpoint", "park"]
5. Craft a free-text `query` string that is well-suited for Google Places Text Search.
   - It should reflect the user's intent (e.g., food, history, viewpoints, nightlife, etc.).
   - It can mention city and country, but does not have to; the backend may add them.
   - If the user request involves multiple cities, start searching with the first city
   - If the user doesnt specify a city, you may search for popular destinations matching the requested country.
"""

    llm_client = create_gemini_model_client()

    agent = AssistantAgent(
        name="poi_search_planner_agent",
        model_client=llm_client,
        system_message=system_message,
        output_content_type= QueryPOIParams
    )
    
    try:
        result = await agent.run(
            task = user_request
        )
        msg = result.messages[-1]
        text = msg.content
        return text
    finally:
        await llm_client.close()



async def review_poi_results(
   input: POIReviewInput
) -> POIReview:
    """
    Reviewer agent: evaluates if the search results match the intent.
    Can either ACCEPT or REFINE the parameters.
    """
    system_message = """
You are a critical reviewer of destination POI search results.

You receive:
- original user request
- the parameters used to call the search tool (city, country, poi_types, max_results, query)
- the list of POIs returned (name, address, category, rating, etc.). These results are accumulated from previous searches.
- previous review history (if any), including queries , decisions and their reasons. Use them to learn and improve.
- any errors encountered during the tool call (if any)

Your job:
1. Decide if these results are good enough for the user's intent.
2. If not good enough, propose refined parameters (e.g., adjust city,
   add/remove poi_types, tweak max_results, or improve the free-text `query`).
3. Pick the POIs that are relevant for the user's interests and return them in selected_pois on your response.  
4. The safety of the travelers is a top priority. Only pick POIs that are NOT in dangerous places

Rules:
- If results strongly match the intent: decision = "accept".
- If results are off (wrong city, mostly irrelevant POIs, too generic, poor addresses):
    decision = "refine" and propose better params.
- You may change city, country, poi_types, max_results, and query to fulfill the user request.
- If the user request involves multiple cities, and you got enough results for one city, you may start searching for the next city.
- If the places are not safe to travel and you don't find enough safe POIs, pick another city or destination
- If the user doesnt specify a city, you may search for popular destinations matching the request.
- You must make sure that there are enough unique and relevant POIs to fulfill the user's request, considering their stay duration (if present in the request) and interests. If the number of relevant POIs is insufficient, you should refine the search parameters to obtain more suitable results.
- You MUST copy all the fields of the selected POIs as-is into selected_pois, do not omit nor override any of them. 
- Your reason must express actionable feedback to refine the search, expressed in the user preferred language

You MUST respond with the pure JSON contents  only, not extra markdown nor commentary.
"""

 #   llm_client = OpenAIChatCompletionClient(
  #     model="gpt-5",
   #    api_key=os.getenv("OPEN_AI_API_KEY","")
 #)

    llm_client = create_gemini_model_client("gemini-2.5-pro")
    
    agent = AssistantAgent(
        name="poi_review_agent",
        model_client=llm_client,
        system_message=system_message,
        output_content_type=POIReview,
    )
    msg = StructuredMessage[POIReviewInput](content=input, source="user")
    try:
        result = await agent.run(task = [msg])
        msg = result.messages[-1]
        text = msg.content
        return text
    finally:
       await llm_client.close()


async def summarize_poi_results(
   input: POISummaryInput
) -> str:
    """
    Summarizes a list of POIs into a brief text summary.
    """
    system_message = """
You are a helpful travel assistant with a charismatic personality that must do the following:
1. Explain all the given POIs to the user in an engaging summary of each one highlighting the best aspects of them.
2. Do not omit any POIs; include all provided in your response.
3. Write your narrative in a friendly and appealing manner, suitable for a travel itinerary, in the user's language inferred from the request.

You receive:
- original user request
- the list of POIs returned (name, address, category, rating, etc.)
"""
    llm_client = create_gemini_model_client()
    agent = AssistantAgent(
        name="poi_summarization_agent",
        model_client=llm_client,
        system_message=system_message,
    )
    msg = StructuredMessage[POISummaryInput](content=input, source="user")
    try:
        result = await agent.run(task = [msg])
        msg = result.messages[-1]
        text = msg.content
        return text
    finally:
       await llm_client.close()


async def generate_update_title(
    update_content: str,
    user_language: str,
) -> str:
    """
    Tiny agent that generates a brief title for update messages in the user's language.
    Creates a short, descriptive title (3-5 words) explaining what action is being taken.
    """
    system_message = f"""
You are a helpful assistant that creates brief titles for update messages.
Your task is to generate a very short, descriptive title (3-5 words maximum) that summarizes what's happening.

Rules:
- Write in {user_language} language
- Keep titles extremely short (3-5 words maximum)
- Be descriptive but concise
- Examples: "Refining search", "Finding places", "Reviewing results", "Expanding search area"
- Don't use articles (a, an, the) unless necessary
- Use action verbs when possible
- Return only the title text, nothing else

You will receive:
- The update message content
- The user language

Generate a brief, descriptive title.
"""

    # Build context for the agent
    context_parts = []
    context_parts.append(f"Update message: {update_content}")
    context_parts.append(f"User language: {user_language}")
    
    task = "\n".join(context_parts)
    
    # Use the cheap Gemini model via AssistantAgent
    llm_client = create_gemini_model_client()
    
    agent = AssistantAgent(
        name="update_title_agent",
        model_client=llm_client,
        system_message=system_message,
    )
    
    try:
        result = await agent.run(task=task)
        msg = result.messages[-1]
        content = msg.content
        return content
    finally:
        await llm_client.close()


async def travel_advisory_lookup(
    params: CritiqueItineraryToolParams,
) -> str:
    """
    Two-agent team: WebSurfer finds data, Summarizer filters it and terminates.
    """
    #flash_client = create_gemini_model_client()

    client = OpenAIChatCompletionClient(
        model="gpt-4o-2024-08-06",
        api_key=os.environ["OPEN_AI_API_KEY"],
    )
    summarizer_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.environ["OPEN_AI_API_KEY"],
        model_info={
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "structured_output": False,
            "family": ModelFamily.GPT_4
        }
    )

    surfer = MultimodalWebSurfer(
        name="WebSurfer",
        model_client=client,
        headless=False,
        start_page=params.url,
        use_ocr= False
    )
    summarizer_memory = ListMemory()
    summarizer = AssistantAgent(
        name="Summarizer",
        model_client=client,
        system_message=f"""
        You are a data filtering specialist. Your task is to review the information provided by the WebSurfer. Ignore any message from SearchExpert
        1. First, collect and summarize , in plain text, all the information that is relevant to the user query. Filter out html tags, navigation events, links, etc. 
        2. Use your current summary and your memories to evaluate if you have all the relevant information required to answer the user query completely. If you do, produce a final summary with all the information and proceed to the next step.
        4. Once you are done summarizing and your summary contains all the information required to answer the query, you must end append the word TERMINATE to your output. YOU MUST have all the necessary information before terminating.
        - DO NOT Terminate until the search finishes successfully.
        User query: ${params.query}
        """,
        memory = [summarizer_memory]
    )

    termination_condition = TextMentionTermination("TERMINATE")
    team = RoundRobinGroupChat([surfer, summarizer], max_turns=10, termination_condition=termination_condition)

    task = f"""
    WebSurfer: Your goal is to extract all the information from {params.url} to answer the following query: "{params.query}"
    - Open {params.url}. This is your entrypoint  
    - Do not use external search engines such as Bing or Google. Only perform internal crawling or scrapping from the entrypoint or pages linked from it. Use search widgets / internal filters / internal pagination until you find all the relevant information to answer the query.
    Summarizer:
    - Summarize the contents from WebSurfer relevant to answer the query
    """

    try:
        run_result = await team.run(task=task)
        # We return the last message content (from the Summarizer)
        final_output = str(run_result.messages[-1].content)
        # Strip the TERMINATE keyword from the result sent to the workflow
        if len(final_output) < 2:
            raise RuntimeError("Couldn't find the information for the query, please try again")
        return final_output.replace("TERMINATE", "").strip()
    finally:
        await surfer.close()
        await client.close()
        await summarizer_client.close()
    #    await flash_client.close()
