import os
import json
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh 

default_base_url = os.getenv('OLLAMA_HOST')

# --- Streamlit Page Title ---
st.set_page_config(page_title="Ollama Chat", page_icon="🤖")

# --- Helpers ---
def check_ollama_health(base_url=None):
    base_url = base_url or default_base_url
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=2)
        if r.status_code == 200:
            return True, r.json()  # expected to be a dict possibly containing "models"
        return False, f"Unexpected status: {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)

def get_pulled_models(base_url=None):
    base_url = base_url or default_base_url
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=2)
        r.raise_for_status()
        data = r.json()
        models = [m["name"] for m in data.get("models", [])]
        return models, data
    except requests.RequestException as e:
        return [], str(e)

def pull_model_stream(model_name, base_url=None):
    """Generator that yields lines of progress from the /api/pull endpoint."""
    base_url = base_url or default_base_url
    url = f"{base_url}/api/pull"
    try:
        with requests.post(url, json={"name": model_name}, stream=True) as r:
            r.raise_for_status()
            for raw in r.iter_lines():
                if raw:
                    yield raw.decode("utf-8", errors="replace")
    except requests.RequestException as e:
        # yield a single error line so caller can display it
        yield f"ERROR: {e}"

# --- Sidebar ---
with st.sidebar:
    # --- Controls ---
    st.title("⚙️  Controls")
    base_url = st.sidebar.text_input("Ollama Base URL", value=default_base_url, help="e.g., http://ollama:11434")

    # sidebar inputs
    # model_choice = st.selectbox("Choose model:", ["llama3.1:8b", "llama3:7b", "llama2:13b"], help="Set model you want to use.\nNote: this will need to be pulled and available in the local Ollama server.")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7)
    max_tokens = st.sidebar.number_input("Max Tokens (0 = Ollama default)", min_value=0, value=0, step=100)
    clear = st.sidebar.button("Clear chat history")

    # --- Healthcheck ---
    # Use a container so only this part refreshes
    # built-in auto-refresh
    st_autorefresh(interval=5*60*1000, key="ollama_health")

    pulled_models, health_raw = get_pulled_models()
    if pulled_models:
        st.success("✅ Ollama healthy")
        st.info("Pulled: " + ", ".join(pulled_models))

        # 🔑 Only allow choosing from *pulled models*
        chosen_model = st.selectbox("Choose model", pulled_models)
        st.session_state["chosen_model"] = chosen_model

    else:
        # If health_raw is a string it's likely an error message; otherwise just show no models
        if isinstance(health_raw, str):
            st.error(f"❌ Healthcheck failed: {health_raw}")
        else:
            st.info("No models pulled yet.")

    st.markdown("---")
    st.subheader("⬇️ Pull Model")

    # available models you want to allow pulling from
    available_models = ["llama3.1:8b", "llama3:7b", "llama2:13b"]
    models_to_pull = [m for m in available_models if m not in pulled_models]

    pull_section = st.container()
    with pull_section:
        if models_to_pull:
            # give the selectbox a stable key so Streamlit won't get confused across reruns
            pull_choice = st.selectbox("Select model to pull:", models_to_pull, key="pull_choice", help="See https://ollama.com/search for all available Ollama models.")
            if st.button(f"Pull {pull_choice}", key="pull_button"):
                progress_placeholder = st.empty()
                # stream the pull output line by line
                with st.spinner(f"Pulling {pull_choice}..."):
                    last_line = ""
                    for line in pull_model_stream(pull_choice):
                        last_line = line
                        # show the latest progress line (overwrite)
                        progress_placeholder.text(line)
                    # after streaming finishes, re-check the pulled models to confirm
                    new_pulled, _ = get_pulled_models()
                    if pull_choice in new_pulled:
                        st.success(f"✅ {pull_choice} pulled successfully")
                        # force a rerun so the sidebar re-queries /api/tags and the dropdown updates
                        st.experimental_rerun()
                    else:
                        # If we didn't find the model, try to present helpful info
                        st.error(f"❌ Pull finished but {pull_choice} not in pulled models.")
                        st.text("Last output from pull:\n" + (last_line or "<no output>"))
        else:
            st.info("All available models are already pulled.")

# --- Session state ---
if "messages" not in st.session_state or clear:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

# --- Main App Body ---
st.title("💬 Ollama Chat")
st.caption("This interface connects to your local Ollama server and streams the responses.")

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
