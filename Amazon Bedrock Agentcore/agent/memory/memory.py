from strands.hooks import HookProvider, HookRegistry, MessageAddedEvent, AgentInitializedEvent, AfterInvocationEvent
import logging
from bedrock_agentcore.memory.session import MemorySession
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
import re

logger = logging.getLogger(__name__)

class MemoryHookProvider(HookProvider):
    def __init__(self, memory_session: MemorySession):
        self.memory_session = memory_session
    
    def retrieve_context(self, event: MessageAddedEvent):
        logger.info(f"✅ Loaded on_agent_initialized")
        try:
            recent_turns = self.memory_session.get_last_k_turns(k=3)
            
            if recent_turns:
                context_messages = []
                for turn in recent_turns:
                    for message in turn:
                        if hasattr(message, 'role') and hasattr(message, 'content'):
                            role = message['role']
                            content = message['content']
                        else:
                            role = message.get('role', 'unknown')
                            content = message.get('content', {}).get('text', '')
                        context_messages.append(f"{role}: {content}")
                
                context = "\n".join(context_messages)
                
                event.agent.system_prompt = event.agent.system_prompt.split("### Recent conversation:")[0]
                event.agent.system_prompt += f"\n\n### Recent conversation:\n{context}"
                logger.info(f"✅ Loaded {len(recent_turns)} conversation turns using MemorySession")
                
        except Exception as e:
            logger.error(f"Memory load error: {e}")

    def save_interaction(self, event: AfterInvocationEvent):
        """Store messages in memory using MemorySession"""
        messages = event.agent.messages
        try:
            if messages and len(messages) > 0 and messages[-1]["content"][0].get("text") and "Reprase this query" not in messages[-1]["content"][0]["text"]:
                message_text = messages[-1]["content"][0]["text"]
                message_role = MessageRole.USER if messages[-1]["role"] == "user" else MessageRole.ASSISTANT
                
                if message_role == MessageRole.USER:
                    match = re.search(r"<query>(.*?)</query>", message_text)
                    if match:
                        message_text = match.group(1).strip()

                logger.error(f"Storing message. Role: {message_role.value}, Text: {message_text}")

               
                result = self.memory_session.add_turns(
                    messages=[ConversationalMessage(message_text, message_role)]
                )
                
                event_id = result['eventId']
                logger.info(f"✅ Stored message with Event ID: {event_id}, Role: {message_role.value}")
                
        except Exception as e:
            logger.error(f"Memory save error: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
    
    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(MessageAddedEvent, self.retrieve_context)
        registry.add_callback(AfterInvocationEvent, self.save_interaction)
        registry.add_callback(AgentInitializedEvent, self.retrieve_context) 
        logger.info("✅ Memory hooks registered with MemorySession")