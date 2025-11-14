import os
import json
import urllib
import uuid
from typing import Optional
import requests
import boto3
import streamlit as st
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("app.log"), 
        logging.StreamHandler(),    
    ],
)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="Bedrock AgentCore Agent", page_icon="🤖", layout="wide")

st.sidebar.title("Settings")
default_aws_org_id = "[AWS Organization ID]"
default_client_id = "[Cognito Client ID]"
default_region = "us-east-1"
default_agent = "[Agentcore Runtime Agent ID ]"
default_runtime_user_id = "[Runtime User ID]"
default_qualifier = "DEFAULT"
default_user_id = "[Cognito Username]"
default_user_pwd= "[Cognito Password]"
default_mcp_url = "https://platform.cloud.coveo.com/api/private/organizations/[org_d]/mcp/server/[mcp_config_id]"

region_name = st.sidebar.text_input("AWS region", value=default_region)
mcp_url = st.sidebar.text_input("MCP Server", value=default_mcp_url)
boto3.setup_default_session(region_name=region_name)

agent_name = st.sidebar.text_input("Agent", value=default_agent)
runtime_user_id = st.sidebar.text_input(
    "Runtime User ID",
    value=default_runtime_user_id
)
qualifier = st.sidebar.text_input("Qualifier", value=default_qualifier)

if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = uuid.uuid4().hex + "z"
col_a, col_b = st.sidebar.columns([3, 1])
col_a.text_input(
    "Runtime Session ID",
    value=st.session_state.runtime_session_id,
    key="runtime_session_id_input",
)
if col_b.button("↻", help="Generate a new session id"):
    st.session_state.runtime_session_id = uuid.uuid4().hex + "z"
    st.rerun()


def generate_auth_header(region: str) -> str:
    client_id = os.getenv("COGNITO_CLIENT_ID", default_client_id)
    username = os.getenv("COGNITO_USERNAME", default_user_id)
    password = os.getenv("COGNITO_PASSWORD", default_user_pwd)
    if not username or not password:
        raise RuntimeError(
            "Missing COGNITO_USERNAME/COGNITO_PASSWORD env vars; do not hardcode secrets in code."
        )

    client = boto3.client("cognito-idp", region_name=region)
    resp = client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return resp["AuthenticationResult"]["AccessToken"]

def send_query(prompt: str):
    logger.info(f"User input: {prompt}")

    bearer_token = generate_auth_header(region_name)

    escaped_arn = urllib.parse.quote(f"arn:aws:bedrock-agentcore:{default_region}:{default_aws_org_id}:runtime/{agent_name}", safe="")
    url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": st.session_state.runtime_session_id,
        "X-Amzn-Bedrock-AgentCore-Runtime-User-Id": runtime_user_id,
    }

    body = {"prompt": prompt,
            "mcp_url" : mcp_url,
            "user_id": default_user_id,
            "session_id" : st.session_state.runtime_session_id
            }
    print(body)

    try:
        with requests.post(
            url,
            params={"qualifier": qualifier},
            headers=headers,
            json=body,
            timeout=None,
            stream=True,
        ) as response:
            response.raise_for_status()
            ctype = (response.headers.get("Content-Type") or "").lower()

            if "text/event-stream" in ctype:
                for raw in response.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    if raw.startswith(":"):
                        continue
                    if raw.startswith("data:"):
                        payload = raw[5:].strip()
                        if not payload:
                            continue
                        if payload == "[DONE]":
                            break
                        try:
                            yield json.loads(payload)
                        except Exception:
                            yield {"text": payload}
                return

            try:
                yield response.json()
            except Exception:
                yield {"text": response.text}

    except requests.exceptions.RequestException as e:
        logger.error("Failed to invoke agent endpoint: %s", str(e))
        raise


st.title("🤖 Agent Studio")

if "messages" not in st.session_state:
    st.session_state.messages = []

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])
if ctrl_col1.button("Clear chat"):
    st.session_state.messages.clear()
    st.rerun()

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Type your message")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty() 
        status_area = st.empty()   
        streamed_text = ""         

        buffer = ""
        FLUSH_AT = 32

        try:
            for event in send_query(prompt):
                logging.info(event)
                try:
                    data = json.loads(event)
                except:
                    data = {"text":event}

                if isinstance(data, dict) and "auth_url" in data:
                    status_area.info(f"[Click to authorize]({data['auth_url']})")
                    continue

                if isinstance(data, dict) and "error" in data:
                    status_area.error(data["error"])
                    continue

                if isinstance(data, dict) and "status" in data:
                    status = data["status"]
                    if status == "Begin":
                        status_area.write("⌛ starting…")
                        continue
                    elif status == "End":
                        status_area.write("")
                        continue
                    else:
                        status_area.write(f"• {status}")
                        continue
                    continue

                if isinstance(data, dict) and ("text" in data) and ("answer" not in data):
                    status_area.write(data["text"])  # keep out of final transcript
                    continue

                token: Optional[str] = None
                if isinstance(data, dict) and "answer" in data:
                    token = str(data["answer"])
                elif isinstance(data, dict) and "text" in data:
                    token = data["text"]
                elif isinstance(data, str):
                    token = data
                else:
                    # unknown shape; surface for debugging without killing the stream
                    token = "\n```\n" + json.dumps(data, indent=2) + "\n```"

              
                if token is None:
                    continue

                buffer += token
                # flush when buffer is big enough or ends with whitespace
                if len(buffer) >= FLUSH_AT or buffer.endswith((" ", "\n")):
                    streamed_text += buffer
                    buffer = ""
                    placeholder.markdown(streamed_text)

        except Exception as e:
            st.error(f"Invocation failed: {e}")
        finally:
            if buffer:
                streamed_text += buffer
                placeholder.markdown(streamed_text)

            st.session_state.messages.append({"role": "assistant", "content": streamed_text})
