---
name: end-dialog-github-sync-and-tweet
description: End-of-session closure workflow for conversations where the user says "结束当前对话并生成推文" (or equivalent). Use this skill to decide whether the current task is fully implemented or still in progress. If fully implemented, sync deliverables to GitHub with a detailed commit and push, then generate a detailed Chinese tweet including a verified GitHub link. If in progress, skip GitHub sync and generate a Chinese progress tweet covering goal, plan, current status, and next steps.
---

# End Dialog GitHub Sync and Tweet

## Workflow

1. Detect trigger.
- Trigger this skill when the user says `结束当前对话并生成推文` or uses equivalent wording asking to close the conversation and publish a tweet.

2. Determine task status.
- Mark as `completed` only when requested deliverables are implemented and no blocking gap remains.
- Mark as `in_progress` when key deliverables are missing, unverified, blocked, or explicitly half-done.
- Inspect workspace evidence before deciding: changed files, implemented features, test/check results, and unresolved TODOs.

3. For `completed`, run GitHub sync first.
- Confirm Git context:
  - `git rev-parse --is-inside-work-tree`
  - `git status --short`
  - `git remote get-url origin`
- Sync only task-related files. Avoid committing unrelated local changes.
- Create a detailed commit message that includes:
  - background/problem statement
  - implemented features
  - important technical decisions
  - verification/testing results
  - follow-up items
- Push current branch to GitHub.
- Capture a verified URL from the real remote and branch/commit.
- Never fabricate GitHub links. If no valid URL is available, ask the user for the target repository URL before finalizing.
- If push fails (auth/network/repo settings), report the exact failure and still generate tweet content with a clear note.

4. For `in_progress`, skip GitHub sync.
- Do not commit or push.
- Generate a progress tweet that clearly includes:
  - task objective
  - implementation plan
  - current progress
  - pending work or blockers
  - next immediate actions

5. Generate final tweet text in Chinese.
- For `completed`, include:
  - what was delivered
  - project capabilities now available
  - technical highlights
  - future iteration directions
  - GitHub link
- For `in_progress`, include:
  - objective and expected value
  - estimated progress percentage
  - milestone status
  - next milestone
- Keep content specific to the current task. Avoid generic claims.

## Output Contract

- Return section `执行结果`:
  - `任务状态`: `completed` or `in_progress`
  - `GitHub同步`: `已完成` / `未执行` / `失败(原因)`
  - `GitHub链接`: verified URL or `无`
- Return section `推文文案` with final publish-ready Chinese text.

## References

- Use `references/tweet_templates.md` to structure the final copy.
