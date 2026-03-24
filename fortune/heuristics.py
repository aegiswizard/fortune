"""
Fortune 🥠 — Heuristics Engine
Scores each GitHub account for likelihood of being a fake/bot star.

Scoring Guide:
  0–29   → Likely real
  30–49  → Suspicious
  50+    → Likely fake
"""

import re
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _same_day(d1: Optional[datetime], d2: Optional[datetime]) -> bool:
    if d1 is None or d2 is None:
        return False
    return d1.date() == d2.date()


def _days_between(d1: Optional[datetime], d2: Optional[datetime]) -> Optional[int]:
    if d1 is None or d2 is None:
        return None
    return abs((d1 - d2).days)


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_user(user: dict, star_date_str: str) -> tuple:
    """
    Score a GitHub user against all fake-star heuristics.

    Returns:
        (is_suspicious: bool, reasons: list[str], score: int 0-100)
    """
    score = 0
    reasons: list[str] = []

    # Parse dates
    star_date  = _parse(star_date_str)
    created_at = _parse(user.get("created_at"))
    updated_at = _parse(user.get("updated_at"))

    # Profile fields
    followers    = int(user.get("followers") or 0)
    following    = int(user.get("following") or 0)
    pub_repos    = int(user.get("public_repos") or 0)
    pub_gists    = int(user.get("public_gists") or 0)
    bio          = (user.get("bio") or "").strip()
    email        = (user.get("email") or "").strip()
    blog         = (user.get("blog") or "").strip()
    twitter      = (user.get("twitter_username") or "").strip()
    name         = (user.get("name") or "").strip()
    location     = (user.get("location") or "").strip()
    login        = (user.get("login") or "").strip()

    # ── HEURISTIC 1 ─────────────────────────────────────────────────────────
    # Account was created the exact same day it starred the repo.
    # This is the single strongest signal and accounts for most cheap bots.
    if _same_day(created_at, star_date):
        score += 40
        reasons.append(
            "Account created on the same day as the star"
            + (f" ({created_at.date()})" if created_at else "")
        )

    # ── HEURISTIC 2 ─────────────────────────────────────────────────────────
    # Zero followers — real developers accumulate at least a few.
    if followers == 0:
        score += 15
        reasons.append("Zero followers")
    elif followers <= 2:
        score += 7
        reasons.append(f"Extremely few followers ({followers})")

    # ── HEURISTIC 3 ─────────────────────────────────────────────────────────
    # Following nobody — bots rarely follow anyone.
    if following == 0:
        score += 10
        reasons.append("Following nobody")
    elif following <= 2:
        score += 5
        reasons.append(f"Following very few accounts ({following})")

    # ── HEURISTIC 4 ─────────────────────────────────────────────────────────
    # No public repositories — real developers push code.
    if pub_repos == 0:
        score += 15
        reasons.append("No public repositories")
    elif pub_repos <= 2:
        score += 7
        reasons.append(f"Very few public repositories ({pub_repos})")

    # ── HEURISTIC 5 ─────────────────────────────────────────────────────────
    # Completely empty profile — bots don't fill out bios, names, etc.
    empty = sum([
        1 if not bio      else 0,
        1 if not email    else 0,
        1 if not blog     else 0,
        1 if not twitter  else 0,
        1 if not name     else 0,
        1 if not location else 0,
    ])
    if empty == 6:
        score += 10
        reasons.append("Profile is completely empty (no bio, name, email, blog, location, or Twitter)")
    elif empty >= 4:
        score += 5
        reasons.append(f"Profile is nearly empty ({empty}/6 fields blank)")

    # ── HEURISTIC 6 ─────────────────────────────────────────────────────────
    # Account was never meaningfully updated after creation.
    if created_at and updated_at:
        stale_days = _days_between(created_at, updated_at)
        if stale_days is not None and stale_days <= 1:
            score += 10
            reasons.append("Account shows no activity after creation day")

    # ── HEURISTIC 7 ─────────────────────────────────────────────────────────
    # Account was very new at the time of starring (but not same day).
    if created_at and star_date and not _same_day(created_at, star_date):
        age = _days_between(created_at, star_date)
        if age is not None:
            if age <= 7:
                score += 10
                reasons.append(f"Account was only {age} day(s) old when it starred this repo")
            elif age <= 30:
                score += 4
                reasons.append(f"Account was only {age} days old when it starred this repo")

    # ── HEURISTIC 8 ─────────────────────────────────────────────────────────
    # Suspicious username pattern — many bots use word+number combos
    # or long strings of random lowercase letters.
    num_digits = len(re.findall(r'\d', login))
    if num_digits >= 5:
        score += 5
        reasons.append(f"Username contains many digits, possible bot pattern ({login})")
    elif re.match(r'^[a-z]{5,10}\d{4,}$', login, re.IGNORECASE):
        score += 5
        reasons.append(f"Username matches common bot pattern ({login})")

    # ── HEURISTIC 9 ─────────────────────────────────────────────────────────
    # Ghost account combo bonus: zero of everything simultaneously.
    if followers == 0 and following == 0 and pub_repos == 0 and pub_gists == 0 and empty == 6:
        score += 15
        reasons.append("Ghost account: zero activity across every measurable metric")

    # Cap at 100
    score = min(score, 100)

    # Threshold: ≥ 50 is suspicious
    is_suspicious = score >= 50

    return is_suspicious, reasons, score
