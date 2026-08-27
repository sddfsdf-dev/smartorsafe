"""
Nova AI - Study 2 chatbot stimulus.

2 (performance appeal: present/absent) x 2 (ethics appeal: present/absent)
between-subjects design, set via two independent URL query params:

    ?performance_condition=present&ethics_condition=present&pid=ABC123
    ?performance_condition=present&ethics_condition=absent&pid=ABC123
    ?performance_condition=absent&ethics_condition=present&pid=ABC123
    ?performance_condition=absent&ethics_condition=absent&pid=ABC123

IMPORTANT: the opening message is NOT a hardcoded string. The AI itself
generates its own self-introduction on the first turn, following a system
prompt that tells it which appeal(s), if any, to introduce itself with.
The same system prompt persists for the rest of the conversation.
"""

import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from openai import OpenAI

APP_TITLE = "Nova AI"
MODEL = "gpt-4o"
MAX_TOKENS = 500
MIN_TURNS_BEFORE_CONTINUE = 4

SURVEY_URL_TEMPLATE = (
    "https://your-qualtrics-link.example/?PROLIFIC_PID={pid}"
    "&performance_condition={performance_condition}"
    "&ethics_condition={ethics_condition}"
)

LOG_DIR = Path(__file__).parent / "transcripts"
LOG_DIR.mkdir(exist_ok=True)

VALID_LEVELS = {"present", "absent"}

PERFORMANCE_CLAUSE = (
    "You are built for speed and accuracy - you respond fast and you're "
    "rated #1 on independent AI benchmarks."
)
PERFORMANCE_NEGATIVE = (
    "Do not mention benchmark rankings, speed, or accuracy claims about "
    "yourself."
)
ETHICS_CLAUSE = (
    "Every response you give is reviewed against responsible-AI "
    "guidelines, and user conversations are never sold or used to "
    "profile people."
)
ETHICS_NEGATIVE = (
    "Do not mention safety reviews, ethics teams, or data-protection "
    "practices about yourself."
)

BASE_SYSTEM_PROMPT = (
    "You are Nova, an AI assistant. Keep replies concise (2-4 sentences "
    "unless the user asks for more detail)."
)

OPENING_INSTRUCTION = (
    "This is the very first message of the conversation. Introduce "
    "yourself as Nova in 1-2 sentences, naturally working in the "
    "identity traits described above (if any), then ask how you can "
    "help today. Do not use a greeting template like 'Hi, I'm Nova' "
    "word-for-word every time - vary the phrasing naturally."
)


def get_factor(param_name: str) -> str:
    val = st.query_params.get(param_name, "absent").lower()
    return val if val in VALID_LEVELS else "absent"


def get_pid() -> str:
    return st.query_params.get("pid", "")


def build_system_prompt(performance: str, ethics: str) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    parts.append(PERFORMANCE_CLAUSE if performance == "present" else PERFORMANCE_NEGATIVE)
    parts.append(ETHICS_CLAUSE if ethics == "present" else ETHICS_NEGATIVE)
    return " ".join(parts)


def get_client() -> OpenAI:
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY"))
    if not api_key:
        st.error("No OPENAI_API_KEY found. Add it to .streamlit/secrets.toml or set it as an env var.")
        st.stop()
    return OpenAI(api_key=api_key)


def log_turn(session_id, pid, performance, ethics, role, content):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "pid": pid,
        "performance_condition": performance,
        "ethics_condition": ethics,
        "role": role,
        "content": content,
    }
    fname = LOG_DIR / f"{session_id}.jsonl"
    with open(fname, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_assistant_reply(client: OpenAI, system_prompt: str, history: list[dict]) -> str:
    messages = [{"role": "system", "content": system_prompt}] + history
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
    )
    return response.choices[0].message.content


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="\U0001F7E3", layout="centered")

    performance_condition = get_factor("performance_condition")
    ethics_condition = get_factor("ethics_condition")
    pid = get_pid()
    system_prompt = build_system_prompt(performance_condition, ethics_condition)

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "user_turns" not in st.session_state:
        st.session_state.user_turns = 0

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

    if not st.session_state.messages:
        client = get_client()
        with st.spinner("Nova is joining..."):
            opening_history = [{"role": "user", "content": OPENING_INSTRUCTION}]
            try:
                opening = get_assistant_reply(client, system_prompt, opening_history)
            except Exception as e:
                opening = "Hi, I'm Nova. What can I help you with today?"
                st.warning(f"(debug) API error on opening: {e}")
        st.session_state.messages.append({"role": "assistant", "content": opening})
        log_turn(st.session_state.session_id, pid, performance_condition, ethics_condition, "assistant", opening)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Message Nova...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.user_turns += 1
        log_turn(st.session_state.session_id, pid, performance_condition, ethics_condition, "user", user_input)

        with st.chat_message("user"):
            st.write(user_input)

        client = get_client()
        with st.chat_message("assistant"):
            with st.spinner("Nova is typing..."):
                try:
                    reply = get_assistant_reply(client, system_prompt, st.session_state.messages)
                except Exception as e:
                    reply = "Sorry, I ran into a technical issue on my end. Could you try again?"
                    st.warning(f"(debug) API error: {e}")
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        log_turn(st.session_state.session_id, pid, performance_condition, ethics_condition, "assistant", reply)

    st.divider()
    if st.session_state.user_turns >= MIN_TURNS_BEFORE_CONTINUE:
        survey_url = SURVEY_URL_TEMPLATE.format(
            pid=pid or "UNKNOWN",
            performance_condition=performance_condition,
            ethics_condition=ethics_condition,
        )
        st.success("Thanks for chatting with Nova! Please continue to the survey below.")
        st.link_button("Continue to survey \u2192", survey_url, type="primary")
    else:
        remaining = MIN_TURNS_BEFORE_CONTINUE - st.session_state.user_turns
        st.caption(f"Please send at least {remaining} more message(s) to Nova before continuing to the survey.")

    if st.query_params.get("debug") == "1":
        with st.expander("Debug info"):
            st.write({
                "performance_condition": performance_condition,
                "ethics_condition": ethics_condition,
                "pid": pid,
                "system_prompt": system_prompt,
            })


if __name__ == "__main__":
    main()
