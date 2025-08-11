import re
import time

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
import os
import asyncio
import json
import requests

from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from llm_loader import get_llm

from utils import ChatTokenUtils
from schema import ChatRequest

# ---- FastAPI App
app = FastAPI()
TIMEOUT_SECONDS = int(os.getenv("MAX_PROMPT_GENERATION_TIMEOUT_IN_MIN", 20)) * 60

# ---- Streaming Response Function
async def token_stream(agent, model_name, prompt, callback, request: Request):
    task = asyncio.create_task(agent.ainvoke(prompt))
    try:
        start_time = time.time()
        async for token in callback.aiter():
            if await request.is_disconnected():
                print("User disconnected, cancelling task...")
                task.cancel()
                break
            if token:
                data = {
                    "id": str(uuid.uuid4()),
                    "object": "chat.completion.chunk",
                    "choices": [
                        {"delta": {"content": token}, "index": 0, "finish_reason": None}
                    ],
                }
                if time.time() - start_time > TIMEOUT_SECONDS:
                    print("Stream Chat Timeout: Stopping stream...")
                    task.cancel()
                    agent.stop(model_name)
                    break
                yield f"data: {json.dumps(data)}\n\n"
        if not task.done():
            await task
        yield "data: [DONE]\n\n"
    except asyncio.CancelledError:
        print("Agent task cancelled cleanly due to user stop.")
        task.cancel()
    except Exception as e:
        print(f"Error during streaming: {e}")
        yield "data: [DONE]\n\n"


# ---- Chat Completion Endpoint
@app.post("/chat/completions")
async def chat_completion(request: Request, chat_request: ChatRequest):
    prompt = chat_request.messages[-1].content
    model_name = chat_request.model

    callback = AsyncIteratorCallbackHandler()
    llm = get_llm(callback)
    chain = ConversationChain(llm=llm, memory=ConversationBufferMemory())

    if "### Task:" in prompt:
        result = await llm.ainvoke(prompt)
        result = ChatTokenUtils.remove_think_block(result)
        result = ChatTokenUtils.extract_json_key(result,"title")
        return ChatTokenUtils.build_chat_response({"title": result}, model_name, is_json=True)
    else:
        if chat_request.stream:
            return StreamingResponse(
                token_stream(chain, model_name, prompt, callback, request),
                media_type="text/event-stream"
            )
        else:
            try:
                result = await asyncio.wait_for(llm.ainvoke(prompt), timeout=TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                print("No Stream LLM call timed out.")
                # Optionally stop the model if still running
                result = "The request took too long and was stopped."
            return ChatTokenUtils.build_chat_response(result, model_name)


# ---- Models Listing Endpoint for OpenWebUI Compatibility
@app.get("/models")
async def list_models():
    try:
        response = requests.get(f"{os.getenv('OLLAMA_API_BASE')}/api/tags")
        response.raise_for_status()
        tags = response.json().get("models", [])
    except Exception as e:
        return {"error": f"Failed to fetch models: {str(e)}"}

    return {
        "object": "list",
        "data": [
            {
                "id": model["name"],
                "object": "model",
                "size": model.get("size"),
                "modified": model.get("modified_at"),
                "owned_by": "user"
            } for model in tags
        ]
    }
