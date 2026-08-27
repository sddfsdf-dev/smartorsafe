# Nova AI — Study 2 Chatbot Stimulus

A real, live-LLM chatbot used as the Study 2 stimulus. The manipulation
happens in the assistant's **opening message** (a performance appeal, an
ethics appeal, both, or neither), and the persona is held consistent for
the rest of the conversation via the system prompt — so the effect isn't
just a one-line intro that gets diluted by turn 3.

## 1. Local setup

```bash
cd chatbot_study2
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and paste your real OpenAI API key
streamlit run app.py
```

Then open, e.g.:
- `http://localhost:8501/?condition=performance&pid=TEST123`
- `http://localhost:8501/?condition=ethics&pid=TEST123`
- `http://localhost:8501/?condition=both&pid=TEST123`
- `http://localhost:8501/?condition=control&pid=TEST123`

Add `&debug=1` to see the assigned condition on-screen.

## 2. Conditions

| `condition` value | Opening message emphasizes |
|---|---|
| `performance` | Speed, accuracy, benchmark ranking |
| `ethics` | Safety review, data protection |
| `both` | Both of the above |
| `control` | Neither (plain greeting) |

If `condition` is missing or invalid, the app defaults to `control`.

## 3. Wiring it into Qualtrics / Prolific

1. In Qualtrics, use **Randomizer** (or an Embedded Data field set by URL
   parameter) to assign each respondent one of the four condition values.
2. Insert a clickable link/button in Qualtrics that opens this app with
   both the condition and the respondent's Prolific ID piped in, e.g.:
   `https://your-deployed-app.streamlit.app/?condition=${e://Field/condition}&pid=${e://Field/PROLIFIC_PID}`
3. Set `SURVEY_URL_TEMPLATE` at the top of `app.py` to the Qualtrics URL
   participants should land on **after** chatting (so they can resume the
   survey). The app auto-fills `{pid}` and `{condition}` into that URL.
4. After `MIN_TURNS_BEFORE_CONTINUE` user messages (default 4), a
   "Continue to survey" button appears.

## 4. Transcripts

Every turn is appended to `transcripts/<session_id>.jsonl` (one JSON
object per line: timestamp, session_id, pid, condition, role, content).
Download or sync this folder periodically — it is **not** the same as
your survey data and needs to be joined on `pid`.

> Note: if you deploy on Streamlit Community Cloud, the filesystem is
> ephemeral (wiped on redeploy/restart). For a real study, point
> `LOG_DIR` at persistent storage, or write turns to a database /
> Google Sheet / S3 bucket instead of local files.

## 5. Deploying

Easiest path: push this folder to a GitHub repo and deploy on
[Streamlit Community Cloud](https://streamlit.io/cloud) (free). Add
`OPENAI_API_KEY` under the app's "Secrets" settings instead of
committing `secrets.toml`.

## 6. Model / cost

Uses `gpt-4o` with `max_tokens=500`. Adjust `MODEL` in `app.py` if you
want a cheaper/faster model for a large N study (e.g. `gpt-4o-mini`).
