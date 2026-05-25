# Quickstart Checklist

The 15-minute setup, step by step. Do these in order.

## ✅ Step 1: Create the GitHub repo (3 min)

1. Go to [github.com/new](https://github.com/new)
2. Repo name: `ai-daily-tutor`
3. **Public** (this is the portfolio play — recruiters need to see it)
4. Don't initialize with README — we have our own
5. Create

Then locally:
```bash
cd C:\Users\Kaushik\OneDrive\Desktop\ai-daily-tutor\ai-daily-tutor
# Unzip or copy the project files here
git init
git add .
git commit -m "feat: initial ai-daily-tutor v1"
git branch -M main
git remote add origin https://github.com/kaushik701/ai-daily-tutor.git
git push -u origin main
```

## ✅ Step 2: Get your Groq API key (3 min)

1. [console.groq.com](https://console.groq.com/) → Sign up free (no credit card)
2. **API Keys** in the left sidebar → **Create API Key**
3. Name it "ai-daily-tutor"
4. **Copy the `gsk_...` key now — you only see it once**

Groq's free tier covers this project easily (you'll use ~1.5K tokens/day, well under the daily limit).

## ✅ Step 3: Get your Resend API key (3 min)

1. [resend.com](https://resend.com) → Sign up (free, no credit card)
2. **API Keys** in the left sidebar → **Create API Key**
3. Name it "ai-daily-tutor", permission "Sending access"
4. **Copy the `re_...` key**

Resend's free tier is 3,000 emails/month and 100/day — you'll use about 100 emails in the whole 90 days. Default sender is `onboarding@resend.dev`, which works fine for personal use.

## ✅ Step 4: Add the 3 GitHub Secrets (3 min)

In your new repo on github.com:

**Settings** (top right of the repo page) → **Secrets and variables** → **Actions** → **New repository secret**

Add three secrets:

| Name | Value |
|---|---|
| `GROQ_API_KEY` | The `gsk_...` key from step 2 |
| `RESEND_API_KEY` | The `re_...` key from step 3 |
| `RECIPIENT_EMAIL` | Your Gmail address (e.g. `kaushik@gmail.com`) |

Optional secret: `GROQ_MODEL` if you want to override the default `llama-3.3-70b-versatile`.

## ✅ Step 5: Enable Actions and run a test (3 min)

1. **Actions** tab → click the green button to enable workflows
2. Click **Daily AI Lesson** in the left sidebar
3. Click **Run workflow** (top right) → leave `dry_run` as `false` → **Run workflow**
4. Wait ~30 seconds, refresh, click the run, watch the logs
5. **Check your Gmail inbox** — Day 1 lesson should be there

If something fails, the logs will tell you exactly what. The most common issue is a typo in one of the three secret names.

## ✅ Step 6: You're done

The cron is now active. Tomorrow at 11 AM PT you'll get Day 2 automatically.

---

## Troubleshooting

**No email arrived**: Check the Actions log. Look for the Resend response — it should contain an `id` if successful. If you see a 403, your Resend API key is wrong. If you see a Groq error, the key is wrong or you've hit a rate limit (wait 1 minute and retry).

**JSON validation errors**: Groq's open-source models sometimes return malformed JSON. The code retries once automatically; if it still fails, try switching `GROQ_MODEL` to `llama-3.1-70b-versatile` or `qwen-2.5-32b`.

**Email landed in spam**: Mark it "Not spam" once. Reply to the email or move it to inbox. Future emails will land correctly.

**Workflow didn't run at 11 AM**: GitHub Actions cron has a typical 5–15 minute drift on free tier — this is normal. Email will still land within ~20 min of 11 AM PT.

**I want to change the time**: Edit `.github/workflows/daily.yml` and change the two `cron:` lines. The format is `MIN HOUR * * *` in UTC. For 9 AM Eastern year-round, use `0 13 * * *` and `0 14 * * *`.

**I want to skip a day**: Easiest is to just disable the workflow for that day (Actions tab → workflow → ⋮ → Disable). Re-enable when ready.

**I want to restart from day 1**: Delete `data/state.db` and commit.
