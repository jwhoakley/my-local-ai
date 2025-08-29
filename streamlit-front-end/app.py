import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="Ollama Chat (Streamlit)", page_icon="🤖")

# --- Sidebar settings ---
st.sidebar.title("Settings")
default_base_url = os.getenv('OLLAMA_HOST')
base_url = st.sidebar.text_input("Ollama Base URL", value=default_base_url, help="e.g., http://ollama:11434")
model = st.sidebar.text_input("Model", value="llama3.1:8b")
temperature = st.sidebar.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
max_tokens = st.sidebar.number_input("Max Tokens (0 = Ollama default)", min_value=0, value=0, step=100)
clear = st.sidebar.button("Clear chat history")

# --- Session state ---
if "messages" not in st.session_state or clear:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

st.title("🤖 Ollama Chat via Streamlit")
st.caption("Connects to your local Ollama server and streams responses.")

# --- Helper: Stream from Ollama /api/chat ---
def stream_chat_ollama(messages, *, model, base_url, temperature=0.7, max_tokens=0):
    """
    Yields chunks of text from Ollama's /api/chat streaming endpoint.
    """
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": float(temperature)},
    }
    if max_tokens and int(max_tokens) > 0:
        payload["options"]["num_predict"] = int(max_tokens)

    try:
        with requests.post(url, json=payload, stream=True, timeout=600) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # Ollama streams json per line
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # Skip non-JSON lines just in case
                    continue

                if "error" in data:
                    # Surface errors from Ollama
                    raise RuntimeError(data["error"])

                # Each chunk has optional message.content and a done flag
                msg = data.get("message", {})
                chunk = msg.get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
    except requests.exceptions.RequestException as e:
        # Connection / HTTP issues
        raise RuntimeError(f"Failed to reach Ollama at {base_url}: {e}") from e

# --- Render history (skip initial system message) ---
for m in st.session_state.messages:
    if m["role"] == "system":
        continue
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- Input box ---
user_prompt = st.chat_input("Type your message")

if user_prompt:
    # Add user message to history and render it
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Prepare assistant container
    with st.chat_message("assistant"):
        # Stream the response and collect it so we can append to history
        full_response = ""
        try:
            # Stream chunks into the UI
            for chunk in st.write_stream(
                stream_chat_ollama(
                    st.session_state.messages,
                    model=model,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            ):
                full_response += chunk
        except Exception as e:
            st.error(str(e))
            full_response = ""

    # Save assistant message if we received anything
    if full_response.strip():
        st.session_state.messages.append({"role": "assistant", "content": full_response})
