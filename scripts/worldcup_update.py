#!/usr/bin/env python3
"""Pull the latest numbers out of worldcup-forecaster's auto-updated README
and rewrite the WC block on the profile README."""

import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT, "README.md")
SOURCE = "https://raw.githubusercontent.com/VirajMishra1/worldcup-forecaster/main/README.md"


def main():
    src = urllib.request.urlopen(SOURCE, timeout=30).read().decode()

    odds = re.findall(r"\|\s*(\S+)\s+([A-Za-z ]+?)\s*\|\s*([\d.]+%)\s*\|", src)[:3]
    acc = re.search(r"\|\s*W/D/L accuracy\s*\|\s*([\d.]+%)\s*\|", src)
    n_matches = re.search(r"Live Track Record \((\d+) matches\)", src)
    if not (odds and acc and n_matches):
        raise SystemExit("source README format changed, refusing to write garbage")

    top = " · ".join(f"{flag} {team.strip()} {pct}" for flag, team, pct in odds)
    block = (
        f"the model's title favorites right now: {top}\n\n"
        f"live track record: **{acc.group(1)} W/D/L accuracy** over {n_matches.group(1)} scored matches "
        f"(random guessing gets 33.3%). every prediction locked to git before kickoff. "
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
