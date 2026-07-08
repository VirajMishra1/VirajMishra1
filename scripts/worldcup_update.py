#!/usr/bin/env python3
"""Pull the latest numbers off the worldcup-forecaster live dashboard
(static HTML, rebuilt by its daily action) and rewrite the WC block on
the profile README. The dashboard is fresher than the source repo's
README, so it is the one source of truth here."""

import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT, "README.md")
SOURCE = "https://virajmishra1.github.io/worldcup-forecaster/"


def main():
    html = urllib.request.urlopen(SOURCE, timeout=30).read().decode()

    odds = re.findall(
        r'wteam-col">([^<]+)</td>\s*<td class="wpct">([\d.]+%)', html
    )[:3]
    rec = re.search(
        r'stat-frac">(\d+)/(\d+)</div>\s*<div class="stat-label">Win/Draw/Loss correct',
        html,
    )
    if not (len(odds) == 3 and rec):
        raise SystemExit("dashboard format changed, refusing to write garbage")

    hits, total = int(rec.group(1)), int(rec.group(2))
    pct = 100 * hits / total
    top = " · ".join(f"{team.strip()} {p}" for team, p in odds)
    block = (
        f"the model's title favorites right now: {top}\n\n"
        f"live track record: **{pct:.1f}% W/D/L accuracy** ({hits}/{total} scored matches, "
        f"random guessing gets 33.3%). every prediction locked to git before kickoff. "
        f"[full table + every scoreline](https://virajmishra1.github.io/worldcup-forecaster/)"
    )

    with open(README_PATH) as f:
        readme = f.read()
    new = re.sub(
        r"(<!-- WC_START -->\n).*?(\n<!-- WC_END -->)",
        lambda m: m.group(1) + block + m.group(2),
        readme,
        flags=re.DOTALL,
    )
    with open(README_PATH, "w") as f:
        f.write(new)
    print(block)


if __name__ == "__main__":
    main()
