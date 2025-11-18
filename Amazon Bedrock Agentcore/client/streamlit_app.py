import json
import urllib
import uuid
from typing import Optional
import requests
import boto3
import streamlit as st
import logging
from datetime import datetime

# ----------------------
# Logging
# ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ----------------------
# Streamlit app config
# ----------------------
st.set_page_config(page_title="Bedrock AgentCore Chat", page_icon="🤖", layout="wide")

# ----------------------
# Sidebar configuration
# ----------------------
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

mcp_url = st.sidebar.text_input("MCP Server", value=default_mcp_url)
boto3.setup_default_session(region_name=default_region)

# ----------------------
# Session state
# ----------------------
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

if "messages" not in st.session_state:
    st.session_state.messages = []

# ----------------------
# Status log (per-run; do NOT persist across runs)
# ----------------------
# We'll reset these at the start of *each* prompt so previous runs never reprint.
if "status_log" not in st.session_state:
    st.session_state.status_log = []
if "last_status_msg" not in st.session_state:
    st.session_state.last_status_msg = None
if "recent_status_set" not in st.session_state:
    st.session_state.recent_status_set = set()

def _reset_status_state():
    st.session_state.status_log = []
    st.session_state.last_status_msg = None
    st.session_state.recent_status_set = set()

def log_status(message: str, level: str = "info"):
    """De-dupes consecutive and already-seen messages (per run)."""
    # de-dupe by semantic key (no timestamp)
    key = (level, message)
    if key in st.session_state.recent_status_set:
        return
    st.session_state.recent_status_set.add(key)

    # format with timestamp for display only
    ts = datetime.now().strftime("%H:%M:%S")
    display_msg = f"[{ts}] {message}"

    # de-dupe consecutive identical display line
    if st.session_state.last_status_msg == (level, display_msg):
        return
    st.session_state.last_status_msg = (level, display_msg)

    st.session_state.status_log.append((level, display_msg))

# ----------------------
# Auth helper
# ----------------------
def generate_auth_header() -> str:
    # Prefer Streamlit secrets; fallback to env vars
    client_id = default_client_id
    username = default_user_id
    password = default_user_pwd

    client = boto3.client("cognito-idp", region_name=default_region)
    resp = client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return resp["AuthenticationResult"]["AccessToken"]

# ----------------------
# Agent invocation
# ----------------------
def send_query(prompt: str):
    logger.info(f"User input: {prompt}")

    bearer_token = generate_auth_header()

    escaped_arn = urllib.parse.quote(
        f"arn:aws:bedrock-agentcore:{default_region}:381491957401:runtime/{default_agent}",
        safe="",
    )
    url = f"https://bedrock-agentcore.{default_region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": st.session_state.runtime_session_id,
        "X-Amzn-Bedrock-AgentCore-Runtime-User-Id": default_runtime_user_id,
    }

    body = {
        "prompt": prompt,
        "mcp_url": mcp_url,
        "user_id": default_user_id,
        "session_id": st.session_state.runtime_session_id,
    }

    try:
        with requests.post(
            url,
            params={"qualifier": default_qualifier},
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

            # Non-SSE fallback
            try:
                yield response.json()
            except Exception:
                yield {"text": response.text}

    except requests.exceptions.RequestException as e:
        logger.error("Failed to invoke agent endpoint: %s", str(e))
        raise

# ----------------------
# UI
# ----------------------
st.title("🤖 Agent Studio")

# Past transcript
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Type your message")
if prompt:
    # Record user msg
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Collapsible status panel (use a placeholder so we REPLACE, not append)
        expander = st.expander("Run status (click to expand)", expanded=False)
        log_placeholder = expander.empty()

        def render_log():
            ICON = {"info": "ℹ️", "warn": "⚠️", "error": "❌"}
            if not st.session_state.status_log:
                log_placeholder.markdown("_No status yet…_")
                return
            md = "\n".join(f"- {ICON.get(level,'•')} {msg}"
                           for level, msg in st.session_state.status_log)
            log_placeholder.markdown(md)

        # Start a brand-new status area for THIS run only
        _reset_status_state()
        render_log()

        # Loading indicator while streaming
        loading = st.empty()
        loading.markdown("⏳ Generating answer…")

        # Where streamed assistant text goes
        placeholder = st.empty()
        streamed_text = ""
        buffer = ""
        FLUSH_AT = 32

        try:
            for event in send_query(prompt):
                logging.info(event)

                # Normalize event into dict/str
                data = event
                if isinstance(event, str):
                    try:
                        data = json.loads(event)
                    except Exception:
                        data = {"text": event}

                # Handle auth URL
                if isinstance(data, dict) and "auth_url" in data:
                    placeholder.markdown(f"[Click to authorize]({data['auth_url']})")
                    continue

                # Handle explicit errors
                if isinstance(data, dict) and "error" in data:
                    log_status(str(data["error"]), "error")
                    render_log()
                    continue

                # Structured status updates
                if isinstance(data, dict) and "status" in data:
                    s = str(data["status"])
                    if s == "Begin":
                        log_status("starting…", "info")
                    elif s == "End":
                        log_status("finished.", "info")
                    else:
                        log_status(s, "info")
                    render_log()
                    continue

                # Progress text that shouldn't enter final transcript
                if isinstance(data, dict) and ("text" in data) and ("answer" not in data):
                    log_status(str(data["text"]), "info")
                    render_log()
                    continue

                # Streamed answer tokens
                token: Optional[str] = None
                if isinstance(data, dict) and "answer" in data:
                    token = str(data["answer"])
                elif isinstance(data, dict) and "text" in data:
                    token = str(data["text"])
                elif isinstance(data, str):
                    token = data
                else:
                    token = "\n```\n" + json.dumps(data, indent=2) + "\n```"

                if token is None:
                    continue

                # Buffered flush for smoother UI
                buffer += token
                if len(buffer) >= FLUSH_AT or buffer.endswith((" ", "\n")):
                    streamed_text += buffer
                    buffer = ""
                    placeholder.markdown(streamed_text)

        except Exception as e:
            log_status(f"Invocation failed: {e}", "error")
            render_log()
            st.error(f"Invocation failed: {e}")
        finally:
            if buffer:
                streamed_text += buffer
                placeholder.markdown(streamed_text)

            loading.markdown("✅ Finished")
            st.session_state.messages.append({"role": "assistant", "content": streamed_text})

# Controls
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 2])
if ctrl_col1.button("Clear chat"):
    st.session_state.messages.clear()
    _reset_status_state()
    st.rerun()