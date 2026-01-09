"""MCP client wrapper for VGC tools."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class Tool:
    """An MCP tool definition."""

    name: str
    description: str
    input_schema: dict

    def to_anthropic_tool(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class MCPConnection:
    """Manages connection to the VGC MCP server."""

    command: list[str]
    _session: ClientSession | None = field(default=None, repr=False)
    _tools: list[Tool] = field(default_factory=list)
    _read: Any = field(default=None, repr=False)
    _write: Any = field(default=None, repr=False)
    _context_manager: Any = field(default=None, repr=False)

    async def connect(self) -> None:
        if self._session is not None:
            return
        server_params = StdioServerParameters(
            command=self.command[0],
            args=self.command[1:] if len(self.command) > 1 else [],
        )
        self._context_manager = stdio_client(server_params)
        self._read, self._write = await self._context_manager.__aenter__()
        self._session = ClientSession(self._read, self._write)
        await self._session.__aenter__()
        await self._session.initialize()
        tools_response = await self._session.list_tools()
        self._tools = [
            Tool(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in tools_response.tools
        ]

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._context_manager is not None:
            await self._context_manager.__aexit__(None, None, None)
            self._context_manager = None

    @property
    def tools(self) -> list[Tool]:
        return self._tools

    def get_tools_for_agent(self, tool_names: list[str]) -> list[Tool]:
        return [t for t in self._tools if t.name in tool_names]

    def get_anthropic_tools(self, tool_names: list[str] | None = None) -> list[dict]:
        tools = self._tools if tool_names is None else self.get_tools_for_agent(tool_names)
        return [t.to_anthropic_tool() for t in tools]

    async def call_tool(self, name: str, arguments: dict) -> Any:
        if self._session is None:
            raise RuntimeError("Not connected to MCP server")
        result = await self._session.call_tool(name, arguments)
        if hasattr(result, "content"):
            if isinstance(result.content, list):
                texts = [block.text for block in result.content if hasattr(block, "text")]
                return "\n".join(texts) if texts else str(result.content)
            return result.content
        return result


@dataclass
class MCPConnectionPool:
    """Pool of MCP connections for concurrent agent use."""

    command: list[str]
    pool_size: int = 1
    _connections: list[MCPConnection] = field(default_factory=list)
    _available: asyncio.Queue[MCPConnection] | None = field(default=None)
    _initialized: bool = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._available = asyncio.Queue()
        for _ in range(self.pool_size):
            conn = MCPConnection(command=self.command)
            await conn.connect()
            self._connections.append(conn)
            await self._available.put(conn)
        self._initialized = True

    async def shutdown(self) -> None:
        for conn in self._connections:
            await conn.disconnect()
        self._connections.clear()
        self._initialized = False

    async def acquire(self) -> MCPConnection:
        if not self._initialized:
            await self.initialize()
        if self._available is None:
            raise RuntimeError("Pool not initialized")
        return await self._available.get()

    async def release(self, conn: MCPConnection) -> None:
        if self._available is not None:
            await self._available.put(conn)

    @property
    def tools(self) -> list[Tool]:
        return self._connections[0].tools if self._connections else []
