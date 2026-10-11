# Collaboration rules

## Current setup

<!-- Pick one mode and remove the others. Fill in the AI names and work scope. Use One AI if there is no worker. -->
- Mode: One AI
- Lead: the AI in this session
- Workers: none
<!-- One lead + one worker: lead = for example, Claude Code; worker = for example, Codex CLI. State which directories and tasks the worker may handle. -->
<!-- Several workers: list each AI, working directory, and permission boundary. Only one worker may write to a file at a time. -->

## Starting or resuming work

Begin every report with your identity and role, such as "Claude, lead:" or "Codex, worker:", so the user knows who is responsible. On opening a project, read this file, HANDOFF.md, and STATUS.md; read DISPATCH-LOG.md when dispatch history is needed. Before acting, report the goal, progress, one next step, trust level, and boundaries. "Continue" means restore context only; it does not authorize the step under Next. Report first and wait for explicit authorization. If information is missing or conflicts, say so and ask instead of guessing.

## User preferences

<!-- Example: report in English; keep changes small; ask for human review before publishing. Replace with actual preferences. -->
- Language and reporting style: to be filled in
- Approvals and prohibited actions: to be filled in

## Roles and dispatch

The lead breaks down tasks, checks results, and maintains HANDOFF.md and STATUS.md. Workers stay within their authorized scope. A task sent to a worker must start with `[LEAD DISPATCH]` and state its goal, directory, permissions, success criteria, and how to report back. The lead checks `git status` before and after dispatch to establish ownership and scope of changes, checks each piece of evidence, then records the task, result, and review in DISPATCH-LOG.md. A worker's own account is AGENT_REPORTED; it does not become VERIFIED automatically.

**Where the worker CLI lives** (the usual snag after switching machines): first try `command -v codex` (and the like). If not found, on macOS the Codex bundled with the ChatGPT desktop app is at `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`. Still not found: ask the user where it is installed, then write the full path into "Current setup" above and use it from then on.

## Changing hands

- Worker unavailable: retry at most once and tell the user why it failed. The lead may do the work directly only after the user confirms. Do not switch to a paid call to get around a quota limit.
- Lead unavailable: if the user contacts an AI directly in its interface and the message does not start with `[LEAD DISPATCH]`, that AI becomes acting lead. It first reads the files and reports status, then waits for user authorization before acting. Add an "Acting Lead" section at the top of HANDOFF.md with the takeover time, scope, changes, and items awaiting review. When the original lead returns, it reviews the interim changes and updates status.

## Several projects at once

Give each project its own directory, session, and progress files. Confirm the path before entering a project, then read that project's rules. Confirm the scope of each cross-project task separately. Do not carry facts, authorization, or files from one project into another. Coordinate before parallel work writes to the same file.

## Safety boundaries

Default to read-only. Write files, run external commands, use the network, commit, or push only as authorized for the task. Ask the user before incurring costs; never switch to a paid option automatically because of a quota limit. Never permanently delete files; explain and get authorization before removing them. Do not commit keys, credentials, private identities, or personal paths; check for private information before sharing. Keep sensitive content out of progress files and logs. If a safety boundary is unclear, stop and ask.
