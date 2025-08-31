import os
import json
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh  # pip install streamlit-autorefresh

st.set_page_config(page_title="Ollama Manager", page_icon="🤖")
default_base_url = os.getenv('OLLAMA_HOST')

# --- Helpers ---
def get_pulled_models(base_url=None):
    base_url = base_url or default_base_url

    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        r.raise_for_status()
        data = r.json()
        # Ollama typically returns {"models": [{"name": "llama3.1:8b", ...}, ...]}
        models = [m.get("name") if isinstance(m, dict) else str(m) for m in data.get("models", [])]
        return models, data

    except requests.RequestException as e:
        return [], str(e)

def pull_model_stream(model_name, base_url=None):
    base_url = base_url or default_base_url

    url = f"{base_url}/api/pull"

    try:
        with requests.post(url, json={"name": model_name}, stream=True) as r:
            r.raise_for_status()
            for raw in r.iter_lines():
                if raw:
                    yield raw.decode("utf-8", errors="replace")

    except requests.RequestException as e:
        yield f"ERROR: {e}"

# --- Helper: Stream from Ollama /api/chat ---
def stream_chat_ollama(messages, *, model, base_url=None, temperature=0.7, max_tokens=0):

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

# --- Ensure session_state key exists so code later can safely read it ---
if "chosen_model" not in st.session_state:
    st.session_state["chosen_model"] = None

# --- Sidebar ---
with st.sidebar:
    st.title("⚙️  Controls - app-3")

    # --- Setup variables
    base_url = st.sidebar.text_input("Ollama Base URL", value=default_base_url, help="e.g., http://ollama:11434")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7)
    max_tokens = st.sidebar.number_input("Max Tokens (0 = Ollama default)", min_value=0, value=0, step=100)
    clear = st.sidebar.button("Clear chat history")

    st.markdown("---")
    st.subheader("🩺 Ollama Health / Status")
    pulled_models, health_info = get_pulled_models()

    # Use a container so only this part refreshes
    health_placeholder = st.empty()

    # auto-refresh the sidebar every 10s (updates health & pulled models)
    st_autorefresh(interval=5*60*1000, key="ollama_health")

    if isinstance(health_info, str):
        # health_info is an error message
        st.error(f"❌ Healthcheck failed: {health_info}")
    else:
        # container is healthy
        st.success("✅ Ollama healthy")
        if pulled_models:
            st.info("Pulled: " + ", ".join(pulled_models))
        else:
            st.info("No models pulled yet.")

    st.markdown("---")
    st.subheader("Choose model (pulled only)")

    # If there are pulled models, ensure session_state has a valid default and bind selectbox to it
    if pulled_models:
        # if current chosen_model is missing or no longer valid, default to first pulled model
        if st.session_state.get("chosen_model") not in pulled_models:
            st.session_state["chosen_model"] = pulled_models[0]
        # bind selectbox to session_state["chosen_model"] so it always exists after this point
        st.selectbox("Choose model:", options=pulled_models, key="chosen_model")
    else:
        # No selectbox created — keep chosen_model None so other code can detect this case safely
        st.session_state["chosen_model"] = None
        st.info("No pulled models available. Pull a model below.")

    st.markdown("---")
    st.subheader("⬇️ Pull Model")

    # freeform text input instead of selectbox
    model_to_pull = st.text_input("Enter model name to pull:", key="pull_text", help="See https://ollama.com/search for all available Ollama models.")
    if st.button("Pull model", key="pull_button") and model_to_pull.strip():
        progress = st.empty()
        with st.spinner(f"Pulling {model_to_pull}..."):
            last_line = ""
            for line in pull_model_stream(model_to_pull.strip()):
                last_line = line
                progress.text(line)
            # after pull attempt, re-check pulled models
            new_pulled, _ = get_pulled_models()
            if model_to_pull.strip() in new_pulled:
                st.success(f"✅ {model_to_pull} pulled successfully")
                # force a rerun so the Choose-model selectbox refreshes
                st.experimental_rerun()
            else:
                st.error(f"❌ Pull finished but {model_to_pull} not found in pulled models.")
                st.text("Last output:\n" + (last_line or "<no output>"))

# --- Session state ---
if "messages" not in st.session_state or clear:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

# --- Main App Body ---
st.title("💬 Ollama Chat - app-3")
st.caption("This interface connects to your local Ollama server and streams the responses.")

# read the chosen model safely
model = st.session_state.get("chosen_model")
if model:
    st.write(f"Selected model: **{model}**")
    # proceed to use `model` when calling Ollama
else:
    st.warning("No model selected. Either pull a model or wait until Ollama is healthy.")

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
