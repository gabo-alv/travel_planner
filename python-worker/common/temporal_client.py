from temporalio.client import Client
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()



async def get_temporal_client() -> Client:
    temporal = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    return temporal

