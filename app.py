"""
app.py — Streamlit chat interface for the football prediction agent.
Stadium-scoreboard visual theme: amber-on-charcoal, condensed display type,
pitch-green accents. Wraps main.py's LangChain agent.
"""

import streamlit as st
from main import ask

st.set_page_config(page_title="Match Analyst", page_icon="⚽", layout="centered")

# ---------------------------------------------------------------------------
# Styling — condensed display type for headers, chalk/amber scoreboard palette
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.scoreboard-header {
    background: linear-gradient(180deg, #14261C 0%, #0D1B14 100%);
    border: 1px solid #2C4A38;
    border-radius: 4px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.5rem;
}

.scoreboard-title {
    font-family: 'Oswald', sans-serif;
    font-weight: 700;
    font-size: 2rem;
    letter-spacing: 0.02em;
    color: #F2A900;
    text-transform: uppercase;
    margin: 0;
    line-height: 1.1;
}

.scoreboard-subtitle {
    font-family: 'Inter', sans-serif;
    color: #A8B8AC;
    font-size: 0.92rem;
    margin-top: 0.4rem;
}

.league-strip {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 0.9rem;
}

.league-chip {
    font-family: 'Oswald', sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.03em;
    color: #A8B8AC;
    border: 1px solid #2C4A38;
    border-radius: 3px;
    padding: 0.2rem 0.6rem;
    text-transform: uppercase;
}

[data-testid="stChatMessage"] {
    border-radius: 6px;
    border: 1px solid #223328;
}

[data-testid="stSidebar"] {
    border-right: 1px solid #2C4A38;
}

[data-testid="stSidebar"] h2 {
    font-family: 'Oswald', sans-serif;
    color: #F2A900;
    text-transform: uppercase;
    font-size: 1.1rem;
    letter-spacing: 0.03em;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="scoreboard-header">
    <p class="scoreboard-title">Match Analyst</p>
    <p class="scoreboard-subtitle">
        Ask about a matchup — e.g. "who wins Manchester City vs Arsenal?" —
        and get a probability grounded in a Dixon-Coles Poisson model,
        head-to-head record, and recent form.
    </p>
    <div class="league-strip">
        <span class="league-chip">Premier League</span>
        <span class="league-chip">La Liga</span>
        <span class="league-chip">Serie A</span>
        <span class="league-chip">Bundesliga</span>
        <span class="league-chip">Ligue 1</span>
        <span class="league-chip">Champions League</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    avatar = "🧑" if message["role"] == "user" else "⚽"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

user_input = st.chat_input("Ask about a matchup or a team...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="⚽"):
        with st.spinner("Reading the form guide..."):
            try:
                response = ask(st.session_state.messages)
            except Exception as e:
                response = f"Something went wrong: {e}"
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("The Model")
    st.markdown(
        "**Dixon-Coles Poisson model** — time-weighted attack/defense strength "
        "per team, with a low-score correction for realistic draw rates. "
        "Backtested against real Premier League results: beat a plain Poisson "
        "baseline on log loss.\n\n"
        "**Data**: SQLite database built from API-Football, covering 5 major "
        "leagues plus the Champions League, seasons 2022-2024.\n\n"
        "**Simulated date**: predictions are grounded as of January 1, 2024 — "
        "a free-tier data limitation, disclosed rather than hidden."
    )
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()