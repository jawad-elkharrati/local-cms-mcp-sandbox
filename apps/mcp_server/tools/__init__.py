from mcp.server import MCPServer

from . import articles, audit, intelligence, media, revisions, safety, system, taxonomy


def register_tools(mcp: MCPServer) -> None:
    for module in [system, articles, revisions, taxonomy, media, intelligence, safety, audit]:
        module.register(mcp)
