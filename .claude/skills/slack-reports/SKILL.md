---
name: slack-reports
description: Fetch the user's Slack daily reports from the last ~38 days, summarize them in 3-5 one-sentence English bullets, and send the summary via Telegram. Trigger on phrases like "slack reports", "summarize my slack reports", "monthly report summary", or /slack-reports.
allowed-tools: Bash, Read, mcp__telegram__send_message
disable-model-invocation: true
---

# slack-reports

End-to-end workflow: pull this user's own daily reports from Slack, summarize, send via Telegram.

## Steps (always perform in this order)

1. **Run the fetcher** from the output dir so generated files land there:
   ```bash
   cd ~/volume/reports/output && ~/max-eliseev-venv/bin/python ~/volume/reports/reports.py
   ```
   - The venv at `~/max-eliseev-venv` is required — system `python3` lacks `slack_sdk`.
   - The script writes `my_daily_reports_<timestamp>.md` and `.json` to the cwd.

2. **Pick the newest `.md`** in `~/volume/reports/output/`:
   ```bash
   ls -t ~/volume/reports/output/my_daily_reports_*.md | head -1
   ```
   Read that file with the Read tool.

3. **Write the summary in English**, 3–5 bullets, exactly one sentence each. Source reports are usually in Russian — translate to English. Cover the highest-signal themes (projects driven, docs shipped, research/papers, notable proposals, blockers), not a chronological log.

4. **Send via Telegram** using `mcp__telegram__send_message` with `parse_mode: "Markdown"`. Start with a bold title like `*Monthly work summary (<earliest-date> – <latest-date>):*` (dates inferred from the report file's first and last `## YYYY-MM-DD` headings). Then the bullets.

5. **Report back** to the user with: the output `.md` path, the report count, and confirmation that Telegram was sent.

## Constraints

- Always English in the Telegram message, regardless of source language.
- Send immediately — do not ask for confirmation before calling `mcp__telegram__send_message`.
- Do not modify `~/volume/reports/reports.py` or the venv as part of this skill.
