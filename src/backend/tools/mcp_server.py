"""MCP Server for ProCare Agentic OS.

Exposes the full ProCare API surface to MCP clients (Claude Desktop, Antigravity IDE):
- Knowledge graph search
- Agent orchestration
- Operations (Inventory, Tasks, Sales)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend to path so we can import app modules
BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
import mcp.types as types

from sqlalchemy.orm import Session
from app.db.base import engine, SessionLocal
from app.db import models as m
from app.services import knowledge, agent_orchestration, inventory

server = Server("procare-os")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for ProCare MCP."""
    return [
        types.Tool(
            name="search_knowledge",
            description="Search the ProCare knowledge graph (docs, schemas, findings, Procare Vault).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="list_agents",
            description="List all available agents and their status.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="dispatch_agent",
            description="Dispatch a task to an AI agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent ID (hermes, claude, gemini, antigravity)"},
                    "task": {"type": "string", "description": "Task prompt"},
                    "confirm": {"type": "boolean", "default": False, "description": "Set to true to actually run, false to dry-run"}
                },
                "required": ["agent", "task"],
            },
        ),
        types.Tool(
            name="query_db",
            description="Run a SELECT-only query on the ProCare database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL SELECT query"}
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    args = arguments or {}

    if name == "search_knowledge":
        results = knowledge.search(args["query"], args.get("limit", 5))
        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "list_agents":
        status = agent_orchestration.agent_status()
        return [types.TextContent(type="text", text=json.dumps(status, indent=2))]

    elif name == "dispatch_agent":
        with SessionLocal() as session:
            result = agent_orchestration.dispatch(
                agent=args["agent"],
                task=args["task"],
                session=session,
                confirm=args.get("confirm", False),
            )
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "query_db":
        query = args["query"].strip()
        if not query.lower().startswith("select") and not query.lower().startswith("with"):
            return [types.TextContent(type="text", text="Error: Only SELECT queries are allowed via MCP.")]
        
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text(query))
            rows = [dict(row._mapping) for row in result.fetchmany(100)]
            
            # Format datetime objects for json
            for row in rows:
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        row[k] = v.isoformat()
                    elif hasattr(v, "__float__"): # decimals
                        row[k] = float(v)
                        
            return [types.TextContent(type="text", text=json.dumps(rows, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    # Run using stdio
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="procare-os",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
