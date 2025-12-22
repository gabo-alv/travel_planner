import asyncio
import signal
from typing import Dict, Optional, Set

import chainlit as cl
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

from common.temporal_client import get_temporal_client
from common import get_redis  # must return a redis-py client
from pois.poi_models import ClientLiEvent
from pois.workflow_poi_self_improving import SelfImprovingDestinationWorkflow
from pois.temporal_pois_worker import get_pois_worker

# ----------------------------
# Globals
# ----------------------------
client: Optional[Client] = None
worker: Optional[Worker] = None
worker_task: Optional[asyncio.Task] = None

# Per-session pubsub listener tasks
pubsub_tasks: Dict[str, asyncio.Task] = {}
# Track active session IDs to clean up on exit
active_sessions: Set[str] = set()


def _channel(session_id: str) -> str:
    return f"chainlit:poi:events:{session_id}"

# ----------------------------
async def consume_pubsub_events(session_id: str) -> None:
    """
    Subscribe to session channel and forward events to Chainlit UI.
    Uses blocking redis-py PubSub under cl.run_sync (thread) to avoid blocking the event loop.
    """
    redis = get_redis()
    channel = _channel(session_id)

    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    try:
        while True:
            try:
                # redis-py pubsub.get_message is non-blocking by default; we can poll with timeout
                msg =  pubsub.get_message()
                if not msg:
                    await asyncio.sleep(0.05)
                    continue

                # redis-py returns dict like: {"type": "message", "channel": b"...", "data": b"..."}
                raw = msg.get("data")
                print(f"got {raw}")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")

                event = ClientLiEvent.model_validate_json(raw)

                match event.type:
                    case "message":
                        await cl.Message(content=str(event.content), author="assistant").send()
                        if event.is_final:
                            break
                    case "update":
                        # Use dynamic title if available, otherwise fallback to default
                        step_title = event.title if event.title else "Workflow Update"
                        async with cl.Step(name=step_title) as step:
                            step.output = event.content
                            await step.update()
                            continue
                    case _:
                        # unknown / stop
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                # TODO log
                print(f"{e}")
                break
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass


def start_pubsub_listener(session_id: str) -> None:
    """
    Ensure one pubsub listener task per session, running in background.
    """
    global pubsub_tasks
    existing = pubsub_tasks.get(session_id)
    if existing:
        existing.cancel()

    task = asyncio.create_task(consume_pubsub_events(session_id))
    pubsub_tasks[session_id] = task


def stop_pubsub_listener(session_id: str) -> None:
    global pubsub_tasks
    task = pubsub_tasks.pop(session_id, None)
    if task:
        task.cancel()


# ----------------------------
# Temporal workflow start (replace if running)
# ----------------------------
async def start_or_replace_workflow(session_id: str) -> None:
   
    client = await get_temporal_client()
    active_sessions.add(session_id)

    try:
        await client.start_workflow(
            SelfImprovingDestinationWorkflow.run,
            session_id,
            id=session_id,
            task_queue="pois-self-improving-v2",
        )
    except WorkflowAlreadyStartedError:
        handle = client.get_workflow_handle(session_id)
        await handle.terminate(reason="Replace workflow run for same workflow id")
        await client.start_workflow(
            SelfImprovingDestinationWorkflow.run,
            session_id,
            id=session_id,
            task_queue="pois-self-improving-v2",
        )



async def on_init() -> None:
    global  worker
    if worker is not None:
        return
    client = await get_temporal_client()
    worker =  get_pois_worker(client)
    print("[startup] Temporal worker started")
    asyncio.create_task(worker.run())
    
    # Register signals during initial startup
    register_signals()
    


async def shutdown():
    """Logic to terminate workflows on server exit."""
    print("\n[shutdown] Interrupt received, cleaning up workflows...")
    client = await get_temporal_client()

    for session_id in list(active_sessions):
        try:
            handle = client.get_workflow_handle(session_id)
            await handle.terminate(reason="Server process exiting/terminating")
            print(f"[shutdown] Terminated workflow: {session_id}")
        except Exception as e:
            print(f"[shutdown] Failed to terminate {session_id}: {e}")

    global worker_task
    if worker_task:
        worker_task.cancel()
    print("[shutdown] Cleanup complete.")


def register_signals():
    """Register signal handlers for graceful shutdown."""
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    except (NotImplementedError, RuntimeError):
        pass



@cl.on_chat_start
async def on_chat_start() -> None:
    session_id = cl.user_session.get("id")
    await start_or_replace_workflow(session_id)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session_id = cl.user_session.get("id")
    # signal the workflow
    client = await get_temporal_client()
    handle = client.get_workflow_handle(session_id)
    await handle.signal(SelfImprovingDestinationWorkflow.user_reply, message.content)
    await consume_pubsub_events(session_id)

@cl.on_stop
async def on_stop():
    session_id = cl.user_session.get("id")
    await start_or_replace_workflow(session_id)

@cl.on_chat_end
async def on_chat_end() -> None:
    session_id = cl.user_session.get("id")
    active_sessions.discard(session_id)
    stop_pubsub_listener(session_id)
    
    # Terminate the workflow on chat end
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(session_id)
        await handle.terminate(reason="User ended Chainlit chat session")
        print(f"[session] Terminated workflow for session: {session_id}")
    except Exception as e:
        print(f"[session] Workflow already closed or failed to terminate: {e}")

asyncio.run(on_init())