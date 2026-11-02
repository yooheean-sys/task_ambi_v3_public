---
name: hermes-skill-curation
version: 1.0.0
author: hermes-curator
license: MIT
tags: [skills, curation, skills.sh, installation, hermes]
related_skills: [find-skills, hermes-agent]
description: Finding, vetting, and installing external skills in Hermes.
---

# Hermes skill curation

Install counts are popularity, not fit — always read the candidate's SKILL.md before recommending. Skills.sh listings do not expose content, and the top-installed candidate often carries an API-key requirement that breaks a multi-profile org.

## When to use

Use when the user asks for a skill ("is there a skill for X", "find/install a deep research skill"), when choosing between skill-market candidates, or after installing a skill to make it live for profiles.

## Procedure

1. **Search the market.** `curl -s "https://skills.sh/api/search?q=<keywords>"` returns JSON with id/source/name/installs. Do not guess an `api.skills.sh/v1` endpoint — that path returns Vercel DEPLOYMENT_NOT_FOUND.

2. **Fetch and vet each candidate's SKILL.md.** Try `https://raw.githubusercontent.com/<owner>/<repo>/main/skills/<skill>/SKILL.md`; on 404 try `/<skill>/SKILL.md` at repo root or other layouts. A candidate whose raw file 404s is unverified — exclude it rather than recommending on listing data.

   Vet in this order:
   - **External API keys.** Frontmatter `inputs:` with `required: true` means every worker profile's .env needs the secret — a per-profile credential distribution burden. Prefer agent-native skills that run on the harness's built-in web/search tools with zero keys.
   - **Unattended-run fit.** A skill that opens with an interview question or leans on AskUserQuestion stalls an unattended kanban worker; it must be able to state assumptions and proceed, or degrade the question to a needs_input block.
   - **Where the loop runs.** Agent-side loops (agent searches, fetches, synthesizes itself) deliver real autonomous behavior; SaaS-side loops (agent submits a job and polls a paid API) delegate the loop and meter the bill per run.
   - **Harness compatibility.** `allowed-tools:` naming harness-specific tools (e.g. ultrathink, AskUserQuestion, Claude-Code subagent types) signals translation work — confirm the workflow is still executable with Hermes tools before installing.

3. **Install.** `hermes skills install <owner>/<repo>/<skill-id> -y`. Also accepts `official/<category>/<skill>` and a direct SKILL.md URL.

4. **Restart the gateway.** A running gateway caches the skills index in-process, so a skill installed while it runs is silently invisible to all its sessions — no error, no warning. `hermes gateway restart` after every install.

5. **Verify per profile, not globally.** `hermes skills list -p <profile> | grep <skill>` shows exactly what will load for that profile; confirm `enabled` for every worker profile that will use the skill. A default-profile check alone proves nothing about worker profiles.

## Multi-profile org rules

- Put shared skills in `~/.hermes/skills/` only. Never copy a skill into a profile's own `skills/` when a shared version exists — skill resolution prefers profile-local, so a stale local snapshot shadows future updates of the shared one.
- Optional binary dependencies declared by a skill (pandoc, md-to-pdf, etc.) are nice-to-have exports, not install blockers — the skill's core loop must work without them.
