#!/usr/bin/env python3
"""Community wordle board for the profile README.

Guesses arrive as GitHub issues titled "wordle GUESS". The board lives
between WORDLE_START/WORDLE_END markers in README.md, state in
wordle/state.json. The daily answer is derived from the date, so it is
technically peekable by reading this file -- it's a game on a README,
not a bank vault.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "wordle", "state.json")
README_PATH = os.path.join(ROOT, "README.md")
SQUARES = {0: "⬛", 1: "\U0001f7e8", 2: "\U0001f7e9"}
MAX_GUESSES = 6


def load_words():
    with open(os.path.join(ROOT, "wordle", "answers.txt")) as f:
        answers = f.read().split()
    with open(os.path.join(ROOT, "wordle", "allowed.txt")) as f:
        allowed = set(f.read().split()) | set(answers)
    return answers, allowed


def feedback(guess, answer):
    """Standard wordle feedback: 2 green, 1 yellow, 0 gray. Two-pass so
    duplicate letters are scored the way the real game scores them."""
    res = [0] * 5
    counts = {}
    for i in range(5):
        if guess[i] == answer[i]:
            res[i] = 2
        else:
            counts[answer[i]] = counts.get(answer[i], 0) + 1
    for i in range(5):
        if res[i] == 0 and counts.get(guess[i], 0) > 0:
            res[i] = 1
            counts[guess[i]] -= 1
    return tuple(res)


def todays_answer(answers, date_str):
    h = int(hashlib.sha256(f"{date_str}|viraj-profile-wordle".encode()).hexdigest(), 16)
    return answers[h % len(answers)]


def surviving(cands, guess, pattern):
    return [a for a in cands if feedback(guess, a) == pattern]


def candidates(answers, history):
    cands = answers
    for word, pattern in history:
        cands = surviving(cands, word, tuple(pattern))
    return cands


def best_guess(cands):
    """Highest expected-information guess over the candidate set."""
    if not cands:
        return None, 0.0
    n = len(cands)
    best, best_bits = None, -1.0
    for g in cands:
        dist = {}
        for a in cands:
            p = feedback(g, a)
            dist[p] = dist.get(p, 0) + 1
        bits = -sum((c / n) * math.log2(c / n) for c in dist.values())
        if bits > best_bits:
            best, best_bits = g, bits
    return best, best_bits


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


def fresh_state(date_str, prev_answer=None, prev_solved=None):
    return {
        "date": date_str,
        "guesses": [],
        "solved": False,
        "yesterday": prev_answer,
        "yesterday_solved": prev_solved,
    }


def render(state, cands_left):
    lines = []
    for g in state["guesses"]:
        squares = "".join(SQUARES[c] for c in g["pattern"])
        letters = " ".join(g["word"].upper())
        lines.append(
            f"{squares} `{letters}` — [@{g['user']}](https://github.com/{g['user']}), "
            f"{g['bits']:.1f} bits (solver liked {g['solver_pick'].upper()}, {g['solver_bits']:.1f} bits)"
        )
    for _ in range(MAX_GUESSES - len(state["guesses"])):
        lines.append("⬜⬜⬜⬜⬜ `_ _ _ _ _`")
    lines.append("")
    if state["solved"]:
        lines.append(f"**solved in {len(state['guesses'])}.** new word at midnight UTC.")
    elif len(state["guesses"]) >= MAX_GUESSES:
        lines.append("**out of guesses.** the word reveals itself at midnight UTC.")
    else:
        lines.append(f"{cands_left} possible words remain. board resets at midnight UTC.")
    if state.get("yesterday"):
        outcome = "solved" if state.get("yesterday_solved") else "unsolved"
        lines.append(f"yesterday's word: **{state['yesterday'].upper()}** ({outcome})")
    return "\n".join(lines)


def write_readme_block(content):
    with open(README_PATH) as f:
        readme = f.read()
    new = re.sub(
        r"(<!-- WORDLE_START -->\n).*?(\n<!-- WORDLE_END -->)",
        lambda m: m.group(1) + content + m.group(2),
        readme,
        flags=re.DOTALL,
    )
    with open(README_PATH, "w") as f:
        f.write(new)


def emit(comment, updated):
    with open("/tmp/wordle_comment.md", "w") as f:
        f.write(comment + "\n")
    print(f"updated={'true' if updated else 'false'}")


def cmd_new_day():
    answers, _ = load_words()
    today = datetime.date.today().isoformat()
    old = load_state()
    prev_answer = prev_solved = None
    if old and old["date"] != today:
        prev_answer = todays_answer(answers, old["date"])
        prev_solved = old["solved"]
    state = fresh_state(today, prev_answer, prev_solved)
    save_state(state)
    write_readme_block(render(state, len(answers)))


def cmd_guess(raw_guess, user):
    answers, allowed = load_words()
    today = datetime.date.today().isoformat()
    state = load_state()
    if state is None or state["date"] != today:
        prev_answer = prev_solved = None
        if state:
            prev_answer = todays_answer(answers, state["date"])
            prev_solved = state["solved"]
        state = fresh_state(today, prev_answer, prev_solved)

    guess = re.sub(r"[^a-z]", "", raw_guess.lower())
    if state["solved"] or len(state["guesses"]) >= MAX_GUESSES:
        emit("today's board is already done — come back after midnight UTC for a fresh word.", False)
        return
    if len(guess) != 5 or guess not in allowed:
        emit(f"`{guess or raw_guess}` isn't in the word list. five letters, real wordle words only. try again!", False)
        return
    if any(g["word"] == guess for g in state["guesses"]):
        emit(f"`{guess.upper()}` has already been played today. pick a new word.", False)
        return

    answer = todays_answer(answers, today)
    history = [(g["word"], g["pattern"]) for g in state["guesses"]]
    cands_before = candidates(answers, history)
    solver_pick, solver_bits = best_guess(cands_before)
    pattern = feedback(guess, answer)
    cands_after = surviving(cands_before, guess, pattern)
    bits = math.log2(len(cands_before) / max(len(cands_after), 1)) if cands_before else 0.0

    state["guesses"].append({
        "word": guess,
        "pattern": list(pattern),
        "user": user,
        "bits": round(bits, 2),
        "solver_pick": solver_pick,
        "solver_bits": round(solver_bits, 2),
    })
    if pattern == (2, 2, 2, 2, 2):
        state["solved"] = True
    save_state(state)
    write_readme_block(render(state, len(cands_after)))

    squares = "".join(SQUARES[c] for c in pattern)
    if state["solved"]:
        comment = f"{squares} — **{guess.upper()}** is the word! solved in {len(state['guesses'])}. nice."
    else:
        comment = (
            f"{squares} — `{guess.upper()}` earned **{bits:.1f} bits** of information "
            f"({len(cands_before)} candidates → {len(cands_after)}). "
            f"the solver would have played `{solver_pick.upper()}` ({solver_bits:.1f} bits expected). "
            f"board is updated on [the profile](https://github.com/VirajMishra1)."
        )
    emit(comment, True)


def self_test():
    assert feedback("crane", "crane") == (2, 2, 2, 2, 2)
    assert feedback("aaaaa", "abbbb") == (2, 0, 0, 0, 0)
    # duplicate handling: one 'l' in "hello"? answer "world" has one l one o
    assert feedback("llama", "world") == (1, 0, 0, 0, 0)
    assert feedback("speed", "erase") == (1, 0, 1, 1, 0)
    answers, allowed = load_words()
    assert "crane" in allowed and len(answers) > 2000
    a1 = todays_answer(answers, "2026-07-08")
    assert a1 == todays_answer(answers, "2026-07-08") and a1 in answers
    cands = surviving(answers, "crane", feedback("crane", a1))
    assert a1 in cands and len(cands) < len(answers)
    print(f"self-test ok (answer pool {len(answers)}, today's candidates after CRANE: {len(cands)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-day", action="store_true")
    ap.add_argument("--guess")
    ap.add_argument("--user", default="someone")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    elif args.new_day:
        cmd_new_day()
    elif args.guess:
        cmd_guess(args.guess, args.user)
    else:
        ap.print_help()
        sys.exit(1)
