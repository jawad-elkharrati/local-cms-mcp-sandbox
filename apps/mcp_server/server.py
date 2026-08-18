from mcp.server import MCPServer

from apps.mcp_server.prompts import register_prompts
from apps.mcp_server.resources import register_resources
from apps.mcp_server.tools import register_tools


def create_server() -> MCPServer:
    server = MCPServer(
        name="local-cms-mcp-lab",
        description="Local-only model-friendly adapter for a fictional authenticated CMS API.",
        instructions="Everything is fictional and local. Read before writing, use expected versions, and never escalate credentials.",
        version="0.1.0",
    )
    register_tools(server)
    register_resources(server)
    register_prompts(server)
    return server


mcp = create_server()


if __name__ == "__main__":
    mcp.run(transport="stdio")
