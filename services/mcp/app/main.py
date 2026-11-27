"""ASGI entrypoint for the private MCP inventory service."""

from app.server import create_mcp_app

app = create_mcp_app()
