# Match Analyst — Football Prediction Agent

An LLM agent that predicts football match outcomes. Ask it "who wins Manchester
City vs Arsenal?" and it resolves the teams, gathers head-to-head record and
recent form from a local database, runs a from-scratch Dixon-Coles Poisson
statistical model, and answers with a probability, expected goals, and the
most likely scorelines — grounded in real historical data, not just an LLM's
best guess.

**Live app:** [https://football-analytics-bot.streamlit.app/](https://football-analytics-bot.streamlit.app/)



## What it does

- Ask about any matchup across the Premier League, La Liga, Serie A,
  Bundesliga, Ligue 1, or the Champions League
- Get a win/draw/loss probability, each team's expected goals, and the
  top 3 most likely exact scorelines
- Ask general questions too — "what do you think of Arsenal's form" — and
  get a genuine analytical read grounded in real data, not a data dump
- The agent asks for clarification when it needs it (e.g. which team is
  playing at home) and remembers context across a conversation

## How it works

**Agent & tools.** A LangChain agent (Gemini `2.5-flash`) has access to a set
of tools backed by a local SQLite database: team/league lookup, head-to-head
record, recent form, squad info, and the prediction model itself. The agent
decides which tools to call and in what order based on the question — this
is standard tool-use / function-calling, not RAG (no embeddings or vector
search involved; the "retrieval" here is structured SQL queries).

**Data.** A one-time sync script pulls teams, fixtures, and player data from
the [API-Football](https://www.api-football.com/) free tier into a local
SQLite database, covering 5 major leagues plus the Champions League across
the 2022, 2023, and 2024 seasons. The app queries this local database at
runtime instead of hitting the live API — faster, and avoids the API's
rate limits (100 requests/day, 10/minute on the free tier).

**The prediction model.** A from-scratch implementation of the
[Dixon-Coles (1997)](https://www.jstor.org/stable/2986283) extension to the
independent-Poisson football model:
- Each team's attack/defense strength is computed from their season's goals,
  **time-weighted** so recent matches count more than older ones
- A **low-score correction** (`rho`) adjusts the four cells where plain
  Poisson underestimates real football — 0-0, 1-0, 0-1, and 1-1 all occur
  more often in reality than a naive Poisson model predicts
- The full scoreline probability matrix is built, then summed into
  win/draw/loss and searched for the most likely exact scorelines

**Validated, not just implemented.** I backtested the model against a real
Premier League matchday (10 matches, results known) and compared it to a
plain Poisson baseline. Same pick accuracy (5/10), but the Dixon-Coles
version had a **lower average log loss (1.013 vs 1.062)** — meaningfully
better calibrated, especially on draws, which plain Poisson systematically
underestimates.

## Architecture

```
User question
    ↓
Streamlit chat UI (app.py)
    ↓
LangChain agent + tools (main.py)
    ↓
    ├─ find_team / find_league / get_team_league   → team & league resolution
    ├─ get_head_to_head_summary                     → historical record
    ├─ get_form_summary                              → last 5 matches
    ├─ get_squad_summary                              → squad by position
    └─ get_win_probability                            → Dixon-Coles Poisson model
    ↓
SQLite database (football.db)
    ↑
data/build_database.py — one-time/resumable sync from API-Football
```

## Known limitations

Stated plainly rather than hidden:

- **Simulated "current date"**: the app reasons as if it's January 1, 2024.
  Predictions, form, and injuries (not yet implemented) are all scoped
  relative to that fixed point, not real time. This is a deliberate
  consequence of the free-tier API's season restrictions — flagged, not
  disguised as live data.
- **No injuries data** — deferred for now, no reliable data source synced yet.
- **Squad data sync is incremental** — one league/season processed per sync
  run, to respect API rate limits. May not be fully complete for every
  league/season combination.
- **Free-tier data scope**: seasons 2022-2024 only, 5 major leagues +
  Champions League. Not real-time, not comprehensive.

## Tech stack

Python · LangChain · Google Gemini · SQLite · Streamlit · scipy/numpy ·
API-Football

## Running it locally

```bash
git clone https://github.com/yourusername/Football-Analytics.git
cd Football-Analytics
uv sync   # or: pip install -r requirements.txt

# add your keys to a .env file:
# GEMINI_API_KEY=...
# SPORTS_API_KEY=...   (only needed if you want to (re)build the database)

uv run streamlit run app.py
```

The repo includes a pre-built `football.db`, so you don't need an
API-Football key just to run the app — only to regenerate or extend the
database via `data/build_database.py`.

## What's next

- Cloud database migration (to support live data updates without redeploying)
- A secondary web-scraping data pipeline to extend coverage beyond the
  free-tier API's season limits
- Multi-agent architecture (a supervisor delegating to specialized
  prediction / analysis / news agents)
- MLE-fitted Dixon-Coles parameters (the full academic version, fitting
  all teams' attack/defense simultaneously rather than independently)