# Execution Rules

## Default Mode
- Start in planning mode.
- Execute only after explicit user confirmation.

## Risk Controls
- Do not run destructive commands by default.
- Require explicit approval before package installs or system-level changes.
- Keep all project writes inside workspace unless user asks otherwise.

## Validation Pattern
- Run minimal verification after each major step.
- Record command, exit code, and key output.
- If a step fails, report root cause and best next fix.

## Output Format
For each step report:
- `step`
- `command`
- `result`
- `evidence`
- `next`
