# decisions.md

## Workspace Model
- `clawd` is the control tower / agent HQ.
- feature repos should live in dedicated sibling workspaces, not inside `clawd` when avoidable.
- this project now lives at `/Users/bytedance/features/OpenClaw-financial-intelligence`.

## Execution Model
- Elon manages planning, sequencing, delegation, validation, and review.
- Claude Code is the primary implementation engine.
- Codex is the review/approval engine for meaningful code changes.

## Testing Model
- default local runs should exclude integration tests
- integration/live tests should be explicitly marked and run separately

## Recent Technical Decisions
- Gemini SDK migrated from `google-generativeai` to `google-genai`
- default test workflow uses `pytest.ini`
- `requirements-dev.txt` holds test tooling such as pytest
- the repo was repaired with Claude Code and then reviewed/committed/pushed with Codex
- project-management files were added locally to support CEO-style planning and should be committed only by deliberate choice
