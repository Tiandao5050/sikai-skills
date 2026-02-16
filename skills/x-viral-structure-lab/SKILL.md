---
name: x-viral-structure-lab
description: Analyze high-performing X posts to extract writing structure, content strategy, and reusable storytelling patterns, then design new post plans for a user topic. Use when user asks to study爆款推文,拆解结构,模仿行文,策划选题,或按某主题输出同风格内容. Must confirm plan with user before drafting final post text.
---

# X Viral Structure Lab

## Overview
Deconstruct viral X posts into reusable content blueprints and produce a confirmed writing plan before generating final copy.

## Workflow
1. Capture and learn from source link(s) via `x-ops`.
2. Run structure analyzer to produce objective breakdown.
3. Propose adaptation plan for the user's target theme.
4. Ask for explicit confirmation before drafting final posts.

## Step 1: Capture Source Post

```bash
cd /home/sikai/ai-workspace/x-ops
scripts/fetch_and_learn.sh "<x_url>" chromium
```

## Step 2: Analyze Structure

```bash
python /home/sikai/ai-workspace/skills/x-viral-structure-lab/scripts/viral_structure_analyzer.py --url "<x_url>"
```

Outputs:
- `/home/sikai/ai-workspace/x-ops/data/structure/<status_id>.json`
- `/home/sikai/ai-workspace/x-ops/data/structure/<status_id>.md`

## Step 3: Present Plan (Required)
Before writing the final post, present:
- Target audience
- Topic angle and core claim
- Hook style
- 3-5 section outline
- Evidence style (examples/data/case)
- CTA style

Then ask for explicit confirmation.

## Step 4: Draft After Confirmation
After user confirms the plan:
- Produce post variants (short / thread / checklist)
- Keep structure pattern, but avoid sentence-level imitation
- Keep factual integrity and source traceability

## References
- Pattern library: `references/viral_patterns.md`
