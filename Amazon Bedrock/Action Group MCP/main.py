from mcp import StdioServerParameters

from InlineAgent.tools import MCPStdio
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent

server_params = StdioServerParameters(
    command="mcp",
    args=["run", "[path to mcp server]/__main__.py"],
)

async def main():
    coveo_mcp_client = await MCPStdio.create(server_params=server_params)
    
    try:
        coveo_action_group = ActionGroup(
            name="CoveoActionGroup",
            description="Helps user get an answer from Coveo external sources.",
            mcp_clients=[coveo_mcp_client],
        )
        
        await InlineAgent(
            foundation_model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            instruction="""You are a friendly assistant that is responsible for resolving user queries. """,
            agent_name="coveo_agent",
            action_groups=[coveo_action_group],
        ).invoke(input_text="Who is beyonce")
    
    finally:
        await time_mcp_client.cleanup()

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
