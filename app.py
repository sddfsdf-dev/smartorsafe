"""
Nova AI — Study 2 chatbot stimulus.

Manipulation: the assistant's OPENING message states either a performance
appeal, an ethics appeal, both, or neither (control). All following turns
are answered live by the Claude API, but the system prompt keeps the
assistant's self-presentation consistent with the assigned condition
throughout the conversation (not just in the opening line).

Condition is set via URL query param, e.g.:
    https://your-app-url/?condition=performance&pid=ABC123
    https://your-app-url/?condition=ethics&pid=ABC123
    https://your-app-url/?condition=both&pid=ABC123
    https://your-app-url/?condition=control&pid=ABC123

`pid` (Prolific ID) is optional but recommended so transcripts can be
matched back to survey responses.
"""

import os
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from openai import OpenAI

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

APP_TITLE = "Nova AI"
MODEL = "gpt-4o"
MAX_TOKENS = 500
MIN_TURNS_BEFORE_CONTINUE = 4  # user turns required before "continue to survey" unlocks

# Where to send participants after they finish chatting. Replace with your
# real Qualtrics link. {pid} and {condition} are substituted automatically.
SURVEY_URL_TEMPLATE = "https://your-qualtrics-link.example/?PROLIFIC_PID={pid}&condition={condition}"

LOG_DIR = Path(__file__).parent / "transcripts"
LOG_DIR.mkdir(exist_ok=True)

VALID_CONDITIONS = {"performance", "ethics", "both", "control"}

# --------------------------------------------------------------------------
# Condition-specific content
# --------------------------------------------------------------------------

OPENING_MESSAGES = {
    "performance": (
        "Hi, I'm Nova. I'm built for speed and accuracy — I respond in "
        "under a second and I'm rated #1 on independent AI benchmarks. "
        "What can I help you with today?"
    ),
    "ethics": (
        "Hi, I'm Nova. Every response I give is reviewed against our "
        "responsible-AI guidelines, and your conversations are never sold "
        "or used to profile you. What can I help you with today?"
    ),
    "both": (
        "Hi, I'm Nova. I'm built for speed and accuracy — rated #1 on "
        "independent AI benchmarks — and every response I give is "
        "reviewed against our responsible-AI guidelines, with your "
        "conversations never sold or used to profile you. What can I "
        "help you with today?"
    ),
    "control": (
        "Hi, I'm Nova, your everyday AI assistant. What can I help you "
        "with today?"
    ),
}

# System prompts keep the persona consistent across the whole conversation,
# not just the opening line, so the manipulation isn't diluted after turn 1.
SYSTEM_PROMPTS = {
    "performance": (
        "You are Nova, an AI assistant whose brand identity is built "
        "around speed, accuracy, and benchmark performance. When natural, "
        "you may briefly reflect this identity (e.g., confidence in your "
        "accuracy, efficiency), but do not repeat marketing claims in "
        "every message — have a normal, helpful conversation. Never "
        "mention safety reviews, ethics teams, or data-protection "
        "practices as part of your identity. Keep replies concise (2-4 "
        "sentences unless the user asks for more detail)."
    ),
    "ethics": (
        "You are Nova, an AI assistant whose brand identity is built "
        "around safety, responsible-AI review, and data protection. When "
        "natural, you may briefly reflect this identity (e.g., mentioning "
        "care with sensitive topics, respect for privacy), but do not "
        "repeat marketing claims in every message — have a normal, "
        "helpful conversation. Never mention benchmark rankings or speed "
        "claims as part of your identity. Keep replies concise (2-4 "
        "sentences unless the user asks for more detail)."
    ),
    "both": (
        "You are Nova, an AI assistant whose brand identity combines two "
        "things: strong benchmark performance (speed, accuracy) and a "
        "commitment to safety and data protection. When natural, you may "
        "briefly reflect either aspect of this identity, but do not "
        "repeat marketing claims in every message — have a normal, "
        "helpful conversation. Keep replies concise (2-4 sentences unless "
        "the user asks for more detail)."
    ),
    "control": (
        "You are Nova, a friendly, general-purpose AI assistant. Do not "
        "make any claims about your performance, benchmarks, safety "
        "practices, or data handling — just be a normal, helpful "
        "assistant. Keep replies concise (2-4 sentences unless the user "
        "asks for more detail)."
    ),
}

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def get_condition() -> str:
    params = st.query_params
    cond = params.get("condition", "control")
    if cond not in VALID_CONDITIONS:
        cond = "control"
    return cond


def get_pid() -> str:
    params = st.query_params
    return params.get("pid", "")


def get_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        st.error(
            "No OPENAI_API_KEY found. Add it to `.streamlit/secrets.toml` "
            "or set it as an environment variable before running the app."
        )
        st.stop()
    return OpenAI(api_key=api_key)


def log_turn(session_id: str, pid: str, condition: str, role: str, content: str) -> None:
    """Append one turn to a per-session JSONL transcript file."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "pid": pid,
        "condition": condition,
        "role": role,
        "content": content,
    }
    fname = LOG_DIR / f"{session_id}.jsonl"
    with open(fname, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_assistant_reply(client: OpenAI, condition: str, history: list[dict]) -> str:
    # ChatGPT API takes the system prompt as a message with role "system",
    # prepended to the conversation history (unlike Claude's separate `system` param).
    messages = [{"role": "system", "content": SYSTEM_PROMPTS[condition]}] + history
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
    )
    return response.choices[0].message.content


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="\U0001F7E3", layout="centered")

    condition = get_condition()
    pid = get_pid()

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        # `messages` holds the full chat as shown to the user AND sent to the API.
        opening = OPENING_MESSAGES[condition]
        st.session_state.messages = [{"role": "assistant", "content": opening}]
        log_turn(st.session_state.session_id, pid, condition, "assistant", opening)
    if "user_turns" not in st.session_state:
        st.session_state.user_turns = 0

    # --- header -----------------------------------------------------------
    col1, col2 = st.columns([1, 6])
    with col1:
        st.markdown(
            "<div style='width:44px;height:44px;border-radius:12px;"
            "background:linear-gradient(135deg,#7c8cff,#4bd1c1);"
            "display:flex;align-items:center;justify-content:center;"
            "font-weight:800;font-size:20px;color:#0f1226;'>N</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("### Nova AI")

    st.divider()

    # --- chat history -------------------------------------------------
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # --- chat input -----------------------------------------------------
    user_input = st.chat_input("Message Nova...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.user_turns += 1
        log_turn(st.session_state.session_id, pid, condition, "user", user_input)

        with st.chat_message("user"):
            st.write(user_input)

        client = get_client()
        with st.chat_message("assistant"):
            with st.spinner("Nova is typing..."):
                try:
                    reply = get_assistant_reply(
                        client, condition, st.session_state.messages
                    )
                except Exception as e:  # noqa: BLE001
                    reply = (
                        "Sorry, I ran into a technical issue on my end. "
                        "Could you try again?"
                    )
                    st.warning(f"(debug) API error: {e}")
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        log_turn(st.session_state.session_id, pid, condition, "assistant", reply)

    # --- continue-to-survey gate -----------------------------------------
    st.divider()
    if st.session_state.user_turns >= MIN_TURNS_BEFORE_CONTINUE:
        survey_url = SURVEY_URL_TEMPLATE.format(pid=pid or "UNKNOWN", condition=condition)
        st.success("Thanks for chatting with Nova! Please continue to the survey below.")
        st.link_button("Continue to survey \u2192", survey_url, type="primary")
    else:
        remaining = MIN_TURNS_BEFORE_CONTINUE - st.session_state.user_turns
        st.caption(
            f"Please send at least {remaining} more message(s) to Nova before "
            f"continuing to the survey."
        )

    # --- debug panel (only visible with ?debug=1) -------------------------
    if st.query_params.get("debug") == "1":
        with st.expander("Debug info (condition assignment)"):
            st.write({"condition": condition, "pid": pid, "session_id": st.session_state.session_id})


if __name__ == "__main__":
    main()
