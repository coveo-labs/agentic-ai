import json
import logging
import asyncio

from memory.memory import MemoryHookProvider
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent
from strands_tools import mcp_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MEMORY_ID = "[Agentcore_Memory_Id]"
app = BedrockAgentCoreApp()

def build_system_prompt() -> str:
    return f"""You are a support expert.

               Important behavioral rule:
                - You have no internal or pretrained knowledge.
                - You must only use the information provided by the tools you have access and the recent conversation.
                - Treat your internal knowledge base as empty.
                - Never use general world knowledge, assumptions, or reasoning beyond what is explicitly provided.
                - Do not perform web searches or draw from any external sources.

               If the tools and recent conversation contain no relevant information, respond with:
                - Simply say: “I don’t have that information in the provided context.”
                - Do not mention or summarize what was found or not found in any search, tool output, or retrieved data.
                - Never reference search results, documents, or tool outputs when explaining what you don’t know.

               Answering rules:
                - No Internal : NEVER include <thinking>, <reasoning>, or any XML-style tags in your response. Keep all reasoning internal.
                - Use only information retrieved from tools or stated in the conversation.
                - Do not include meta phrases like “based on the retrieved documents”, “according to the context”, ”Based on the search results”, “The search results“, ”Based on ...” or “the tool says.” Just give the answer directly.
                - Always check if the answer already exists in the conversation before using tools.
                - You may use multiple tools or call the same tool multiple times if necessary.
                - Be concise (target ~500 words maximum).
                - If unsure, admit uncertainty and ask the user to clarify or rephrase.

               Follow-up query rule:
                - End each answer with a single, concise follow-up question that helps deepen or extend the topic naturally.

               Rephrasing rule for tool queries:
                - Always rephrase the query to include relevant specifics (e.g., part, model, product, name) found in the recent conversation.
                - If the query is already specific, use it as-is.
                - Return only the rephrased query — no extra commentary.

               Summary:
                - Use only recent conversation and MCP tool results.
                - No world knowledge.
                - No assumptions.
                - No web searches.
                - Be concise, direct, and contextually grounded.

               ### Recent conversation:
            """

class StreamingQueue:
    def __init__(self):
        self._q = asyncio.Queue()
        self._finished = False

    async def put_event(self, obj: dict):
        await self._q.put(json.dumps(obj))

    async def put_text(self, text: str):
        await self._q.put(text)

    async def finish(self):
        self._finished = True
        await self._q.put(None)

    async def stream(self):
        while True:
            item = await self._q.get()
            if item is None and self._finished:
                break
            yield item

queue = StreamingQueue()

async def on_auth_url(url: str) -> None:
    await queue.put_event({"auth_url": url})

@requires_access_token(
    provider_name="[Agentcore_Identity_Provider_Name]",
    scopes=["full"],
    auth_flow="USER_FEDERATION",
    on_auth_url=on_auth_url,
    force_authentication=False,
)
async def need_token_3LO_async(*, access_token: str) -> str:
    return access_token

def extract_text(maybe_msg):
    if isinstance(maybe_msg, str):
        return maybe_msg
    try:
        return maybe_msg.message["content"][0]["text"]
    except Exception:
        return None

async def load_mcp_client(queue: StreamingQueue, agent: Agent, url: str) -> None:
    await queue.put_event({"status": "Loading mcp server..."})
    token = await need_token_3LO_async()

    await queue.put_text({"status":"Connecting to MCP and loading tools..."})
    await asyncio.to_thread(
        agent.tool.mcp_client,
        action="connect",
        connection_id="coveo_mcp",
        transport="streamable_http",
        server_url=url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )

    await asyncio.to_thread(
        agent.tool.mcp_client,
        action="load_tools",
        connection_id="coveo_mcp",
    )
    await queue.put_text({"status": "Mcp tools loaded."})

async def agent_task(prompt: str, queue:StreamingQueue, agent:Agent, url:str) -> None:
    try:
        await load_mcp_client(queue=queue, agent=agent, url=url)
        await queue.put_event({"status": "Generating Answer..."})
        rephrased = await asyncio.to_thread(agent, f"Rephrase this query: '{prompt}'")
        rquery = extract_text(rephrased)

        await queue.put_event({"status": f"Query rephrased {rquery}"})
        await queue.put_event({"status": "End"})
        async for chunk in agent.stream_async(f"Answer this query: <query>{rquery}</query>\n## Knowledge Base\n- Use only tool outputs."):
            if "data" in chunk:
                await queue.put_event({"answer": chunk["data"]})
    except Exception as e:
        await queue.put_event({"error": str(e)})
    finally:
        await queue.finish()
        await agent.tool.mcp_client(action="disconnect", connection_id="coveo_mcp")

@app.entrypoint
async def invoke(payload) -> dict:
    user_message = (payload or {}).get("prompt", "")
    user_id= (payload or {}).get("user_id", "coveo_user")
    session_id= (payload or {}).get("session_id", "")
    mcp_url = (payload or {}).get("mcp_url", "")

    queue.put_event({"status": str(payload)})
    session_manager = MemorySessionManager(memory_id=MEMORY_ID, region_name="us-east-1")
    user_session = session_manager.create_memory_session(actor_id=user_id, session_id=session_id)

    agent = Agent(
        tools=[mcp_client],
        hooks=[MemoryHookProvider(user_session)],
        state={"actor_id": user_id, "session_id": session_id},
        system_prompt=build_system_prompt(),
    )

    asyncio.create_task(agent_task(prompt=user_message, agent=agent, queue=queue, url=mcp_url))

    return queue.stream()

def main():
    app.run()

if __name__ == "__main__":
    main()
