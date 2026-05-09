import os
from fastapi import FastAPI, WebSocket, HTTPException
from pydantic import BaseModel
import asyncio
from typing import Optional, List

# Agent core imports
from biomni.agent import A1

app = FastAPI(title="Biomni Agent API Gateway", version="1.0")

class ChatRequest(BaseModel):
    query: str
    path: str = "./data" # Default sandbox path, can be overridden by API
    llm: str = "claude-sonnet-4-5"
    source: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    expected_data_lake_files: List[str] = []

class ChatResponse(BaseModel):
    result: str

import queue

# Biomni Agent Service: Decoupling hardcoded local interactions
class BiomniAgentService:
    @staticmethod
    def _create_agent(req: ChatRequest) -> A1:
        # Override config based on request to avoid hardcoded ENVs
        if req.base_url:
            os.environ["BIOMNI_CUSTOM_BASE_URL"] = req.base_url
        if req.api_key:
            os.environ["BIOMNI_CUSTOM_API_KEY"] = req.api_key
            
        return A1(
            path=req.path,
            llm=req.llm,
            source=req.source,
            base_url=req.base_url,
            api_key=req.api_key,
            expected_data_lake_files=req.expected_data_lake_files
        )

    @staticmethod
    def process_query(req: ChatRequest) -> str:
        agent = BiomniAgentService._create_agent(req)
        return agent.go(req.query)

    @staticmethod
    def process_query_stream(req: ChatRequest, q: queue.Queue):
        try:
            agent = BiomniAgentService._create_agent(req)
            last_out = ""
            for step in agent.go_stream(req.query):
                out = step.get("output", "")
                if out:
                    q.put({"status": "streaming", "output": out})
                    last_out = out
            q.put({"status": "completed", "result": last_out})
        except Exception as e:
            q.put({"status": "error", "message": str(e)})

# 1. Standard HTTP REST API
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    try:
        # Execute agent in a separate thread to prevent blocking the async event loop
        result = await asyncio.to_thread(BiomniAgentService.process_query, req)
        return ChatResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. WebSocket endpoint for streaming reasoning and execution progress
@app.websocket("/api/v1/chat/stream")
async def chat_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        req = ChatRequest(**data)
        
        await websocket.send_json({"status": "thinking", "message": "Agent Planner initialized..."})
        
        q = queue.Queue()
        loop = asyncio.get_running_loop()
        
        # Run agent in thread
        task = loop.run_in_executor(None, BiomniAgentService.process_query_stream, req, q)
        
        # Wait for messages and send
        while True:
            try:
                msg = q.get_nowait()
                await websocket.send_json(msg)
                if msg["status"] in ["completed", "error"]:
                    break
            except queue.Empty:
                await asyncio.sleep(0.1)
                
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    # Run the gateway
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
