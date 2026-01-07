# --- START OF FILE CodexProject/codex_server/main.py ---
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import os

from codex_engine.core.db_manager import DBManager
from codex_engine.core.db_adapter import SQLTreeAdapter
from .schemas import TreeNodeResponse, TreeNodeSummary, NodeUpdate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_adapter():
    return SQLTreeAdapter(DBManager())

@app.get("/api/tree", response_model=List[TreeNodeSummary])
async def get_roots(adapter = Depends(get_adapter)):
    return adapter.get_roots()

@app.get("/api/tree/{uid}", response_model=TreeNodeResponse)
async def get_node(uid: str, adapter = Depends(get_adapter)):
    node = adapter.get_node(uid)
    if not node: raise HTTPException(404, "Node not found")
    return node

@app.patch("/api/tree/{uid}")
async def update_node(uid: str, payload: NodeUpdate, adapter = Depends(get_adapter)):
    adapter.update_node(uid, payload.data)
    return {"status": "success"}

# Serve the static Web Client
current_dir = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(current_dir, "static")

if not os.path.exists(static_path): 
    os.makedirs(static_path)

app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
