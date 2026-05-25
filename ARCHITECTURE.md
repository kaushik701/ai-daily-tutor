# Architecture

## v1 — Cron + API client (this repo, today)

### Components

| File | Responsibility |
|---|---|
| `src/main.py` | Orchestrator. Decides lesson vs quiz, runs idempotency check, dispatches. |
| `src/curriculum.py` | Loads 90-topic YAML into typed dataclasses. |
| `src/generate.py` | Calls Claude API with a constrained JSON prompt, validates with Pydantic. |
| `src/state.py` | SQLite layer. Tracks sent emails, week number, quiz history. |
| `src/send.py` | Jinja2 HTML rendering + Resend API call + archive to disk. |
| `src/templates/*.j2` | HTML email templates for lessons and quizzes. |
| `.github/workflows/daily.yml` | Cron trigger + commit-back of state + archive. |

### Data flow per run

1. GitHub Actions cron fires at 18:00 or 19:00 UTC.
2. `main.py` decides: is it a quiz day (Sunday with ≥3 prior lessons)?
3. `state.already_sent_today()` checks the last 12 hours to prevent double-sends if both cron times fire on a DST boundary.
4. `generate.py` calls Claude Sonnet 4.5 with a tight system prompt requesting JSON.
5. Pydantic validates. Mismatch → workflow fails loudly (no broken email).
6. `send.py` renders HTML + plain-text alternative, sends via Resend.
7. Email is archived to `examples/sent/YYYY-MM-DD_<kind>_<id>.html`.
8. SQLite record inserted.
9. Workflow commits the archive file + updated DB and pushes.

### Failure modes and how each is handled

| Failure | Handling |
|---|---|
| Claude API down or rate-limited | Workflow fails. Next day's run picks up from `get_next_lesson_day()`, no gap. |
| Resend API down | Workflow fails after generation. State is not recorded, so the same lesson retries next day. |
| Malformed model output | Pydantic raises `ValidationError`, workflow fails. Same retry behavior. |
| Cron fires twice (DST overlap) | `state.already_sent_today()` returns True for the second run; it exits cleanly. |
| Day > 90 | Workflow is a no-op. Curriculum complete. |

### What is deliberately not in v1

- No retry logic. GitHub Actions retries are sufficient; complexity is not earned yet.
- No queueing. One sender, one recipient, daily cadence.
- No observability beyond Action logs. Adding Langfuse is the first v2 milestone.
- No eval harness. Same — first v2 milestone.

---

## v2 — MCP architecture (planned)

The goal of v2 is to refactor the same functionality onto Model Context Protocol so this project demonstrates the 2026 AI Engineering stack: custom MCP server, Claude Agent SDK, eval harness, observability.

### Target architecture

```
┌─────────────────────────────┐
│  GitHub Actions cron        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  scripts/run_tutor.py       │  Thin entrypoint
│  (Claude Agent SDK)         │
└──────────────┬──────────────┘
               │
               │ (stdio MCP)
               ▼
┌─────────────────────────────┐
│  curriculum_mcp/server.py   │  Custom FastMCP server
│                             │
│  Tools:                     │
│    - generate_lesson(day)   │
│    - generate_quiz(week)    │
│    - send_email(kind, html) │
│    - record_state(...)      │
│                             │
│  Resources:                 │
│    - curriculum://day/{n}   │
│    - state://stats          │
│    - history://last/{n}     │
│                             │
│  Prompts:                   │
│    - daily_lesson           │
│    - weekly_quiz            │
└─────────────────────────────┘
               │
               ├──▶ Langfuse traces (OpenInference SDK)
               ├──▶ DeepEval scores → committed to data/evals/
               └──▶ Resend → Gmail
```

### v2 migration plan (4 weekends)

**Weekend 1 — Wrap state and curriculum as MCP resources.**
- Convert `state.py` and `curriculum.py` into a FastMCP server exposing read-only resources.
- Verify with the MCP Inspector: every resource should fetch in <50ms.
- No behavior change; cron still calls `src/main.py`.

**Weekend 2 — Move generation behind MCP tools.**
- Add `generate_lesson(day_number)` and `generate_quiz(week_number)` as MCP tools.
- Rewrite the orchestrator as a Claude Agent SDK script that invokes those tools.
- Add OpenInference instrumentation; send traces to Langfuse cloud (free tier).

**Weekend 3 — Eval harness.**
- Build a small golden set of "what a good day-N lesson looks like" using the first 30 lessons already shipped from v1.
- Write DeepEval `pytest` cases:
  - `PedagogicalClarityMetric` (LLM-as-judge, custom)
  - `CodeCorrectnessMetric` (executes the snippet, checks it runs)
  - `AnalogyConcreteness` (LLM-as-judge, custom)
- Add `.github/workflows/evals.yml` running nightly. Failures post to repo Discussions.

**Weekend 4 — Package as `.mcpb`.**
- Bundle the `curriculum-mcp` server as a Desktop Extension.
- Add to Smithery registry so anyone can install and run their own 90-day curriculum.
- Write blog post: "I rebuilt my cron job as an MCP server; here is what I learned."

### What v2 demonstrates that v1 does not

| Capability | v1 | v2 |
|---|---|---|
| Direct Claude API call | ✓ | — |
| Custom MCP server (Python/FastMCP) | — | ✓ |
| MCP resources, tools, and prompts | — | ✓ |
| Claude Agent SDK as the runtime | — | ✓ |
| Observability with OpenInference + Langfuse | — | ✓ |
| Eval harness with DeepEval, gated in CI | — | ✓ |
| Distributable as `.mcpb` extension | — | ✓ |
| Resume bullet: "Custom MCP server with evals and tracing" | — | ✓ |

### Why v1 first

Shipping the cron version first means I get a working habit on day one and 30+ days of real lesson data before the v2 refactor. That data becomes the golden set for the eval harness — without it, v2 evals would be measured against synthetic lessons, which is the most common pitfall in agent eval work.

Also: every day v2 is delayed, v1 keeps teaching me. There is no penalty for v1 living for 30 days before v2 starts.
