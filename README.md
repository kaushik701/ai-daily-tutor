# AI Daily Tutor

> An autonomous learning agent that emails me one AI/ML concept every morning at 11 AM PT for 90 days — fundamentals on day 1, production AI engineering by day 90 — and quizzes me every Sunday.

[![Daily Lesson](https://github.com/USERNAME/ai-daily-tutor/actions/workflows/daily.yml/badge.svg)](https://github.com/USERNAME/ai-daily-tutor/actions/workflows/daily.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why this exists

I am job-hunting for AI Engineering and ML Engineering roles. Instead of cramming flashcards, I built an agent that delivers one short, well-structured concept to my inbox every day for 90 days, ending at exactly the topics that show up on senior AI Engineering JDs — RAG, agents, evals, MCP, observability.

Three weeks in and the habit is sticking. The 90 emails will also live in this repo as a public archive, so the project doubles as a study log.

## What recruiters can see at a glance

1. **The output**: 90 days of generated emails in [`examples/sent/`](examples/sent/). Open any HTML file to see what landed in my inbox that day. Two hand-picked samples are in [`examples/sample_emails/`](examples/sample_emails/).
2. **The architecture**: see [ARCHITECTURE.md](ARCHITECTURE.md).
3. **The state**: SQLite tracker at `data/state.db` records every email, quiz, and topic — committed on every run.

## Architecture (v1)

```
┌──────────────────────┐
│ GitHub Actions cron  │  18:00 UTC + 19:00 UTC daily (covers DST)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐    ┌──────────────────────┐
│   src/main.py        │───▶│  curriculum.yaml     │  90 topics, 3 phases
│  (orchestrator)      │    └──────────────────────┘
└──────────┬───────────┘
           │
           ├──▶ generate.py ──▶ Groq API (Llama 3.3 70B, OpenAI-compatible)
           │                    └─ Pydantic-validated JSON output, 1 retry on malformed JSON
           │
           ├──▶ state.py    ──▶ SQLite (data/state.db)
           │                    └─ idempotency, week tracking, quiz history
           │
           ├──▶ send.py     ──▶ Jinja2 HTML render ──▶ Resend API ──▶ Gmail
           │                    └─ also archives to examples/sent/
           │
           └──▶ git commit + push (state.db + archived email)
```

**Key design decisions**:

- **Cron runs twice (18:00 and 19:00 UTC)** to land at 11 AM Pacific year-round despite DST. In-app idempotency guard in `state.already_sent_today()` prevents double-sends.
- **Structured outputs** via Pydantic, not free-form text. If the model misformats, the run fails loudly rather than sending a broken email.
- **State lives in git**: the SQLite DB and archived HTML emails are committed after each successful run. This means the entire history is in version control — no extra database, no extra cost, fully reproducible.
- **Quiz logic is data-driven**: every Sunday (UTC), the orchestrator queries the last 6 lessons and asks Claude to write a quiz on them. No hardcoded quiz schedules.

## The 90-day curriculum

Three phases, 30 topics each. Full schedule in [`curriculum/curriculum.yaml`](curriculum/curriculum.yaml).

| Phase | Days | Theme |
|---|---|---|
| 1. ML/DL Fundamentals | 1–30 | Gradient descent → backprop → CNNs → attention → transformers |
| 2. LLM Concepts | 31–60 | Tokenization → RAG → fine-tuning → RLHF/DPO → evals |
| 3. AI Engineering | 61–90 | Agents → MCP → multi-agent → observability → production |

Each topic ships with: a plain-English explanation, a real-world analogy, a 5–15 line code example when relevant, a "why interviewers ask this" angle, and a single-sentence takeaway.

## Roadmap to v2 (MCP architecture)

v1 is a clean cron + API client. v2 will rebuild the same functionality on top of the Model Context Protocol so the project doubles as a portfolio piece for the MCP-heavy 2026 AI Engineering job market.

| Concern | v1 (this) | v2 (planned) |
|---|---|---|
| Generation | Direct Claude API call | Claude Agent SDK driving a custom FastMCP `curriculum-mcp` server |
| State | SQLite via Python | SQLite exposed as MCP **resources** (`curriculum://day/{n}`, `state://stats`) |
| Quality control | Pydantic validation | DeepEval pytest suite (`PedagogicalClarityMetric`, `CodeCorrectnessMetric`) run nightly in CI |
| Observability | GitHub Actions logs | Langfuse traces with per-call latency, token cost, eval score |
| Distribution | This repo only | `.mcpb` desktop extension so anyone can run the curriculum locally |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full v2 migration plan.

## Setup (15 minutes, one time)

### 1. Fork or clone this repo
```bash
git clone https://github.com/USERNAME/ai-daily-tutor.git
cd ai-daily-tutor
```

### 2. Get the three keys

| Service | What you need | How |
|---|---|---|
| Groq | API key | [console.groq.com](https://console.groq.com/) → Sign up free → API Keys → Create. Free tier covers the whole 90 days. |
| Resend | API key | [resend.com](https://resend.com) → Sign up free → API Keys → Create. Free tier: 3,000 emails/mo. |
| Gmail | Just your address | The address that will receive the emails. |

### 3. Add three GitHub Secrets

In your fork: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `GROQ_API_KEY` | `gsk_...` |
| `RESEND_API_KEY` | `re_...` |
| `RECIPIENT_EMAIL` | your Gmail address |

Optional: `RESEND_FROM` if you want to send from your own verified domain instead of the default `onboarding@resend.dev`.

### 4. Enable Actions

GitHub disables Actions on forks by default. Open the **Actions** tab in your fork and click **I understand my workflows, go ahead and enable them**.

### 5. Test it

Open Actions → **Daily AI Lesson** → **Run workflow** → set `dry_run` to `false`. You should get an email in under 60 seconds.

The first scheduled run will fire at the next 18:00 UTC.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # then fill in real keys

# Generate + send today's lesson
python -m src.main

# Generate + render only, do not send (for iterating on templates)
python -m src.main --dry-run

# Force a quiz even on a weekday
python -m src.main --force-quiz --dry-run

# Run the test suite
pytest tests/ -v
```

## Cost

Running cost for the full 90 days, end to end:

| Component | Cost |
|---|---|
| Groq API (Llama 3.3 70B, ~2K tokens/email × 90 lessons + 13 quizzes) | $0 (free tier) |
| Resend | $0 (well within free tier) |
| GitHub Actions | $0 (well within free tier for public repos) |
| **Total** | **$0 for 90 days** |

## Security model

- **Secrets**: all three keys live in GitHub Encrypted Secrets, never in code or commit history.
- **Email destination**: hardcoded to one Gmail address via `RECIPIENT_EMAIL`. The workflow has no way to send to anywhere else.
- **Write scope**: the workflow's `GITHUB_TOKEN` is scoped to `contents: write` on this repo only, so it can commit the email archive and state DB but nothing else.
- **No PII in prompts**: the only data sent to Claude is the curriculum YAML and recent topic titles. No email content, no personal data.

## What I would do with another month

- Build the v2 MCP architecture described in ARCHITECTURE.md.
- Add a DeepEval suite that scores each generated lesson on clarity, factual accuracy, and code correctness, gated in CI.
- Cross-model bench: generate the same lesson with Sonnet, Opus, and Haiku and let me pick the winner via reply-vote.
- Spaced repetition: surface a "throwback" concept from 30 days ago alongside each new lesson.
- Public dashboard at `tutor.kaushik.dev` showing progress (current day, retention %, topics covered).

## License

MIT — fork it, use it, improve it.
