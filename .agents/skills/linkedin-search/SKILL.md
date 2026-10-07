---
name: linkedin-search
version: 1.0.0
description: >
  Search live job listings from LinkedIn's public job board for any country/region or remotely.
  No authentication, no API key, and zero runtime dependencies (runs with pure Python).
  Trigger phrases: find a job, job search, search for jobs, job openings, vacancies, hiring,
  LinkedIn jobs, "are there any X jobs in <place>", look up this job posting.
context: fork
enabled: true
allowed-tools: RunCommand(python .agents/skills/linkedin-search/cli.py *)
---

# LinkedIn Search Skill

Search live job listings from LinkedIn's public job board for **any country/region** (and remote).
No credentials, no API keys, and **zero external dependencies** — runs directly using standard Python 3.

## Commands

### Search Job Postings

```bash
python .agents/skills/linkedin-search/cli.py search --location "<place>" [flags]
```

Flags:
- `--location <text>` / `-l <text>` — **Required.** Location string, e.g. `"Australia"`, `"Sydney, Australia"`, `"Canada"`, `"Saudi Arabia"`, `"Remote"`.
- `--query <text>` / `-q <text>` — Keyword search (title, skill, role, e.g. `"BIM Manager"`, `"Architect"`).
- `--jobage <days>` — Posted within N days (`1`, `7`, `14`, `30`).
- `--remote <mode>` — `remote`, `hybrid`, or `onsite`.
- `--page <n>` — Page number (1-indexed, 10 results per page).
- `--limit <n>` / `-n <n>` — Maximum number of results to output.
- `--format json|table|plain` — Default: `json`.

### Fetch Full Job Detail

```bash
python .agents/skills/linkedin-search/cli.py detail <id|url> [--format json|plain]
```

Fetches the complete job description, requirements, company info, and location.

## Examples

```bash
python .agents/skills/linkedin-search/cli.py search -q "BIM Manager" -l "Australia" --format table
python .agents/skills/linkedin-search/cli.py search -q "Architect" -l "Canada" --jobage 7 --format json
python .agents/skills/linkedin-search/cli.py detail 4426311357 --format plain
```
