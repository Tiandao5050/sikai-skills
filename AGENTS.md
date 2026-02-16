## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

### Available skills
- skill-creator: Guide for creating effective skills. Use when creating or updating skills. (file: /home/sikai/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into `$CODEX_HOME/skills` from curated list or GitHub repo path. (file: /home/sikai/.codex/skills/.system/skill-installer/SKILL.md)
- end-dialog-github-sync-and-tweet: End-of-session closure workflow. Trigger when user says “结束当前对话并生成推文”; if task is complete, sync to GitHub then generate detailed tweet with repo link, otherwise generate progress-only tweet. (file: /home/sikai/.codex/skills/end-dialog-github-sync-and-tweet/SKILL.md)
- x-tutorial-to-action: Capture an X tutorial thread, convert it into an actionable execution plan, and run verified steps safely. Use for installation/debug tutorial execution tasks from X links. (file: /home/sikai/ai-workspace/skills/x-tutorial-to-action/SKILL.md)
- x-viral-structure-lab: Analyze viral X posts for writing structure and content strategy, then produce a plan for your target topic. Must confirm plan before drafting final content. (file: /home/sikai/ai-workspace/skills/x-viral-structure-lab/SKILL.md)
- x-batch-notes-notion-sync: Process multiple X links, classify/summarize into grouped learning notes, and optionally sync the grouped note to Notion. (file: /home/sikai/ai-workspace/skills/x-batch-notes-notion-sync/SKILL.md)
- x-link-capture-analyze: Unified entry for X links. Paste link(s) and purpose, then it captures and routes analysis automatically (tutorial/viral/batch) without manual command choreography. (file: /home/sikai/ai-workspace/skills/x-link-capture-analyze/SKILL.md)

### How to use skills
- Discovery: The list above is the skills available in this workspace (name + description + file path).
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description, use that skill for that turn.
- Progressive disclosure:
  1) Open the skill `SKILL.md` first and read only what is needed.
  2) Resolve relative paths from the skill directory first.
  3) Load references selectively instead of bulk-loading.
  4) Prefer skill scripts under `scripts/` for deterministic workflows.
