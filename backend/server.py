"""
FastAPI server for the Financial Approval System.

Follows the official CopilotKit + LangGraph FastAPI quickstart pattern:
https://docs.copilotkit.ai/langgraph/quickstart?agent=bring-your-own
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from backend.agent.checkpointer import create_async_checkpointer
from backend.config import LANGSMITH_API_KEY, LANGSMITH_PROJECT

# Enable LangSmith tracing if configured
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT


def build_graph(checkpointer):
    """Try the student's graph first; fall back to the demo graph."""
    try:
        from backend.agent.graph import create_approval_graph
        graph = create_approval_graph(checkpointer=checkpointer)
        print("[server] Loaded student approval graph")
    except Exception as exc:
        from backend.agent.demo_graph import create_demo_graph
        graph = create_demo_graph(checkpointer=checkpointer)
        print(f"[server] Student graph not ready ({type(exc).__name__}), using demo graph")
    return graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # AG-UI calls the graph's async API, so the checkpointer must be the async
    # AsyncSqliteSaver, which has to be opened inside the running event loop.
    async with create_async_checkpointer() as checkpointer:
        routes_before = list(app.router.routes)
        # Attach the LangGraph agent as an AG-UI endpoint (official CopilotKit pattern)
        add_langgraph_fastapi_endpoint(
            app=app,
            agent=LangGraphAGUIAgent(
                name="approval_agent",
                description="Financial approval workflow agent",
                graph=build_graph(checkpointer),
            ),
            path="/",
        )
        try:
            yield
        finally:
            # Drop the endpoint bound to this checkpointer before it closes, so a
            # second startup in the same process (e.g. tests) registers a fresh one.
            app.router.routes[:] = routes_before


# FastAPI app
app = FastAPI(title="Financial Approval System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "financial-approval-system"}


@app.get("/api/pipeline/history")
async def pipeline_history():
    """Return completed request history from SQLite checkpoints for the Dashboard."""
    import sqlite3
    import langgraph.checkpoint.serde.jsonplus
    from backend.config import CHECKPOINT_DB

    if not os.path.exists(CHECKPOINT_DB):
        return []

    serializer = langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer()
    try:
        con = sqlite3.connect(CHECKPOINT_DB)
        cur = con.cursor()
        cur.execute("SELECT thread_id, type, checkpoint FROM checkpoints ORDER BY checkpoint_id DESC;")
        rows = cur.fetchall()
        con.close()
    except Exception:
        return []

    seen = set()
    completed = []
    for thread_id, ctype, blob in rows:
        try:
            data = serializer.loads_typed((ctype, blob))
            vals = data.get("channel_values", {})
            status = vals.get("status")
            title = vals.get("title")
            if status in ("approved", "rejected") and title:
                req_id = vals.get("request_id") or thread_id[:8]
                if req_id not in seen:
                    seen.add(req_id)
                    completed.append({
                        "request_id": req_id,
                        "title": title,
                        "amount": float(vals.get("amount", 0)),
                        "department": vals.get("department", "engineering"),
                        "requester": vals.get("requester", "Requester"),
                        "risk_level": vals.get("risk_level", "low"),
                        "status": status,
                        "human_reviews": len(vals.get("decisions", [])) if vals.get("decisions") else 0,
                    })
        except Exception:
            continue
    return completed


if __name__ == "__main__":
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
