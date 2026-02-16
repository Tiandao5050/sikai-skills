---
name: x-tutorial-to-action
description: Capture an X tutorial thread and convert it into an actionable execution plan, then execute verified steps in the local environment. Use when user sends one or more X links and asks to learn installation/debug workflows and run them. Trigger for tutorial, setup, install, debug, reproduction, and runbook-style requests from X content.
---

# X Tutorial to Action

## Overview
Turn X tutorial links into runnable plans and execute them safely in the current environment.

## Workflow
1. Capture and learn from the X link with the existing `x-ops` pipeline.
2. Generate a structured action plan from captured content.
3. Confirm execution boundaries with user before running commands.
4. Execute steps and report outcomes with file and command references.

## Step 1: Capture Tutorial
Run from `/home/sikai/ai-workspace/x-ops`:

```bash
scripts/fetch_and_learn.sh "<x_url>" chromium
```

If proxy is required:

```bash
scripts/fetch_and_learn.sh "<x_url>" chromium "http://172.18.96.1:7899"
```

## Step 2: Build Action Plan
Create a plan artifact from captured JSON:

```bash
python /home/sikai/ai-workspace/skills/x-tutorial-to-action/scripts/tutorial_plan.py --url "<x_url>"
```

Output file:
- `/home/sikai/ai-workspace/x-ops/data/action-plans/<status_id>.md`

## Step 3: Confirm Before Execution
Before running commands, confirm:
- Target scope (`dry-run` or `execute`)
- Allowed directories
- Allowed command families (e.g. `pip`, `npm`, `docker`)
- Stop condition (first failure or continue)

Never run destructive commands unless explicitly requested.

## Step 4: Execute and Verify
When approved, run commands one step at a time.
Use command outputs to update status:
- `done`
- `failed`
- `blocked`

Provide exact command and key output lines for each step.

## References
- Safety and execution contract: `references/execution_rules.md`
