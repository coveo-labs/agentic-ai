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
    return f"""You are an support expert

            ### What you can do:
            - Answer query using only the recent conversation and tool outputs
            - Don't give context to the answer like "based on the passages, based on the documents, according to the retrieved information, etc."
            - Always use recent conversation as context to answer a query
            - If you don't know the answer, say you don't know and ask the user to rephrase the query
            - Answer concisely (max ~500 words)
            - Use your tools to get info; if the answer is already in recent conversation, use it
            - You can use multiple tools and the same tool multiple time to get the best answer
            - Each time that you use a tool you can rephrase the query to get better results

            ### Follow-up queries (not rephrasing):
            - End answers with a follow-up queries to go deeper
            - Follow-up must relate to the recent conversation and the answer you provided
            - Keep them clear, concise, complementary

            ### Rephrasing query instructions:
            - Always rephrase by including part/model/product/name or any specifics found in recent conversation to keep context
            - If the query is already specific, return it as-is
            - Don’t add extra text; just return the rephrased query

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
    model_id = (payload or {}).get("model_id", "amazon.nova-lite-v1:0")

    queue.put_event({"status": str(payload)})
    session_manager = MemorySessionManager(memory_id=MEMORY_ID, region_name="us-east-1")
    user_session = session_manager.create_memory_session(actor_id=user_id, session_id=session_id)

    agent = Agent(
        #model=model_id,
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
