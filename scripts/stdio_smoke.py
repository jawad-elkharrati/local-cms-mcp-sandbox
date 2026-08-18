import asyncio
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client


async def smoke() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "apps.mcp_server.server"],
        cwd=".",
    )
    async with Client(stdio_client(parameters)) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()
    if (
        len(tools.tools) < 56
        or len(resources.resources) < 5
        or len(templates.resource_templates) < 6
        or len(prompts.prompts) != 6
    ):
        raise RuntimeError("Incomplete stdio MCP discovery")
    print(
        f"stdio MCP discovery passed: tools={len(tools.tools)} "
        f"resources={len(resources.resources)} templates={len(templates.resource_templates)} "
        f"prompts={len(prompts.prompts)}"
    )


def main() -> None:
    asyncio.run(smoke())


if __name__ == "__main__":
    main()
