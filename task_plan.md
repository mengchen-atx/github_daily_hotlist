# Task Plan: GitHub Daily Hotlist Email Bot

## Goal
Build a Python automation script that fetches GitHub trending repositories, selects 5 representative projects, generates concise descriptions, sends an HTML email via SMTP, and runs daily with GitHub Actions.

## Phases
| Phase | Status | Notes |
|---|---|---|
| 1. Project scaffolding | complete | Created all required project files |
| 2. Data fetch + selection | complete | Scrape trending and pick first 5 |
| 3. Content extraction + HTML rendering | complete | Generated concise Chinese HTML cards |
| 4. SMTP send + error handling | complete | Added env checks and send failure handling |
| 5. GitHub Actions workflow | complete | Added daily cron and manual dispatch |
| 6. Validation + documentation | complete | Syntax check passed and README added |

## Constraints
- No hardcoded secrets.
- Use environment variables for all sensitive values.
- Add basic exception handling and logs.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|

