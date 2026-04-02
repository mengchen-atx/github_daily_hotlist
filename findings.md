# Findings

## Project Notes
- Repository starts empty, so all required files will be created from scratch.
- Using GitHub Trending HTML scraping avoids reliance on unofficial API endpoints for trending.
- Python stdlib (`urllib`, `html.parser`, `smtplib`) is sufficient; no third-party dependencies required.

## Design Decisions
- Keep selection deterministic: first 5 entries from daily trending list.
- Use repository metadata from trending cards: name, URL, description, language, stars today.
- Generate clean HTML blocks per project for readable email output.

