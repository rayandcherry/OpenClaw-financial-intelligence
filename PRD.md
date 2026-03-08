# PRD.md

## Project
OpenClaw Financial Intelligence

## Goal
Build a reliable financial-intelligence workflow that scans markets, generates structured reports, and supports disciplined iteration on signal quality, reporting quality, and operational reliability.

## Product Intent
This project should evolve as a managed feature workspace:
- clear scope
- clear task sequencing
- validated code changes
- review before meaningful commits
- compact project memory files instead of ad hoc chat-only context

## Current Focus
- keep scan/report pipeline stable
- improve reproducibility and testability
- maintain reliable LLM/report generation path
- separate fast local validation from live/integration validation

## Near-Term Priorities
1. preserve passing local test workflow
2. keep integration tests explicit and non-default
3. improve dependency reproducibility over time
4. reduce noisy/deprecated dependencies
5. improve feature planning and architecture visibility
