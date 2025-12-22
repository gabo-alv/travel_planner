from typing import Optional, Tuple, Dict, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo, ModelFamily
import tiktoken
import os

load_dotenv()


def _ensure_gemini_key() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY env var is required for Gemini.")


async def run_single_agent(
    name: str,
    system_message: str,
    task: str,
    model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-8b"),
) -> Tuple[str, Dict[str, int]]:
    """
    Runs a single agent step, returns:
        (output_text, usage_dict)

    usage_dict = {
        "prompt_tokens": int,
        "completion_tokens": int,
        "total_tokens": int
    }
    """
    _ensure_gemini_key()

    base_url = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    # Use any tiktoken encoding as an approximation – Autogen just
    # needs *some* tokenizer to estimate usage.
    tokenizer = tiktoken.get_encoding("cl100k_base")

    model_info = ModelInfo(
        name=model,
        tokenizer=tokenizer,
        max_input_tokens=128_000,
        max_output_tokens=8192,
        input_cost_per_1k_tokens=0.15,      # update with real Gemini pricing later
        output_cost_per_1k_tokens=0.60,
        vision=False,                        # REQUIRED NOW
        supports_system_message=True,
        supports_json_schema=True,
        function_calling=False,
        json_output=True,
        structured_output=True,
        family=model,
    )

    client = OpenAIChatCompletionClient(
        model=model,
        api_key=os.environ["GEMINI_API_KEY"],
        base_url=base_url,
        model_info=model_info,
    )

    try:
        agent = AssistantAgent(
            name=name,
            model_client=client,
            system_message=system_message,
        )

        result = await agent.run(task=task)  # type: ignore

        final_msg: Optional[TextMessage] = None
        for msg in result.messages:  # type: ignore[attr-defined]
            if isinstance(msg, TextMessage):
                final_msg = msg

        if not final_msg:
            raise RuntimeError(f"{name} produced no TextMessage output.")

        text = final_msg.content
        if not isinstance(text, str):
            raise RuntimeError(f"{name} returned non-str content: {type(text)}")
        text = text.strip()

        usage_dict: Dict[str, int] = {}
        if final_msg.models_usage:
            pt = final_msg.models_usage.prompt_tokens or 0
            ct = final_msg.models_usage.completion_tokens or 0
            usage_dict = {
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": pt + ct,
            }

        return text, usage_dict

    finally:
        await client.close()



def create_gemini_model_client(
    model: Optional[str] = None,
) -> OpenAIChatCompletionClient:
    """
    Create an OpenAIChatCompletionClient configured to talk to Gemini via
    the OpenAI-compatible endpoint.

    You are responsible for closing the client with `await client.close()`
    when done.
    """
    _ensure_gemini_key()

    model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash-8b")

    base_url = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    # Any tiktoken encoding is fine as an approximation for usage tracking
    tokenizer = tiktoken.get_encoding("cl100k_base")

    model_info = ModelInfo(
        name=model,
        tokenizer=tokenizer,
        max_input_tokens=128_000,
        max_output_tokens=8192,
        input_cost_per_1k_tokens=0.15,   # TODO: tune with real Gemini pricing
        output_cost_per_1k_tokens=0.60,  # TODO: tune with real Gemini pricing
        vision=False,
        supports_system_message=True,
        supports_json_schema=True,
        function_calling=False,
        json_output=True,
        structured_output=True,
        family=model,  # or "gemini" if you prefer logical families
    )

    client = OpenAIChatCompletionClient(
        model=model,
        api_key=os.environ["GEMINI_API_KEY"],
        base_url=base_url,
        model_info=model_info,
    )
    return client

