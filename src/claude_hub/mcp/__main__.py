"""MCP stdio server exposing project discovery, session spawning, and conversation search."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from . import projects, search, spawner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("claude-hub-projects")

server: Server = Server("claude-hub-projects")


def _json_text(payload) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, indent=2))]


@server.list_tools()
async def _list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_projects",
            description=(
                "List projects with conversation history in ~/.claude/projects/, "
                "sorted by most recently used first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200},
                },
            },
        ),
        Tool(
            name="spawn_session",
            description=(
                "Start a new `claude remote-control` process in the given directory so a new "
                "environment appears in claude.ai/code. Returns the environment URL. "
                "If the given or derived name already exists for a running session, "
                "a numeric suffix is added (e.g. foo-2)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute directory path to open the session in."},
                    "name": {
                        "type": ["string", "null"],
                        "description": "Optional display name. Defaults to the basename of path.",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="list_running_sessions",
            description="List sessions previously started by spawn_session, with alive status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="stop_session",
            description="Stop a previously spawned session by name.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="search_conversations",
            description=(
                "Search past conversations across all projects for a substring. "
                "Returns matches with project path, session id, timestamp, snippet, and hit count."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Substring to search for."},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 200},
                    "case_sensitive": {"type": "boolean", "default": False},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "list_projects":
            limit = int(arguments.get("limit", 20))
            result = projects.list_projects(limit=limit)
            return _json_text([asdict(p) for p in result])

        if name == "spawn_session":
            path = str(arguments["path"])
            nm = arguments.get("name")
            nm = str(nm) if nm is not None else None
            result = spawner.spawn_session(path=path, name=nm)
            return _json_text(asdict(result))

        if name == "list_running_sessions":
            result = spawner.list_running()
            return _json_text([asdict(r) for r in result])

        if name == "stop_session":
            nm = str(arguments["name"])
            result = spawner.stop_session(name=nm)
            return _json_text(asdict(result))

        if name == "search_conversations":
            query = str(arguments["query"])
            limit = int(arguments.get("limit", 20))
            case_sensitive = bool(arguments.get("case_sensitive", False))
            result = search.search_conversations(
                query=query, limit=limit, case_sensitive=case_sensitive
            )
            return _json_text([asdict(m) for m in result])

        return _json_text({"error": f"unknown tool: {name}"})
    except Exception as e:
        log.exception("tool %s failed", name)
        return _json_text({"error": str(e), "type": type(e).__name__})


async def _run() -> None:
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_run())
