"""
Fortune 🥠 — GitHub API Scanner
Fetches stargazers and user profiles from the GitHub REST API.
No scraping. No third-party services. Just public API calls.
"""

import time
import re
from datetime import datetime, timezone
from typing import Optional, Callable

import requests

from .heuristics import score_user

GITHUB_API = "https://api.github.com"
_RETRY_ATTEMPTS = 3
_BASE_SLEEP = 0.05   # seconds between user fetches (respectful pacing)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_repo_url(url: str) -> tuple:
    """
    Accept any of:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
      github.com/owner/repo
      owner/repo
    Returns (owner, repo).
    """
    url = url.strip().rstrip("/")
    url = re.sub(r"\.git$", "", url)

    if "github.com" in url:
        path = url.split("github.com/", 1)[-1]
    else:
        path = url

    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(
            f"Cannot parse GitHub repository from: '{url}'\n"
            "Expected format: https://github.com/owner/repo"
        )
    return parts[0], parts[1]


def _headers(token: Optional[str] = None) -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _star_headers(token: Optional[str] = None) -> dict:
    """Accept header variant that includes starred_at timestamps."""
    h = _headers(token)
    h["Accept"] = "application/vnd.github.star+json"
    return h


def _check_rate_limit(response: requests.Response, log: Callable) -> None:
    """Block until rate-limit resets if we're out of calls."""
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    if remaining == 0:
        reset_ts = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(reset_ts - time.time(), 1) + 2   # +2s buffer
        log(f"GitHub rate limit reached — waiting {wait:.0f}s for reset...")
        time.sleep(wait)


def _get(url: str, headers: dict, params: dict = None, log: Callable = None) -> requests.Response:
    """GET with retry on 429/403 rate-limit responses."""
    log = log or (lambda _: None)
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.exceptions.Timeout:
            log(f"Request timed out (attempt {attempt + 1}/{_RETRY_ATTEMPTS})...")
            time.sleep(2 ** attempt)
            continue
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Network error: {e}") from e

        if resp.status_code in (403, 429):
            _check_rate_limit(resp, log)
            continue   # retry after wait

        return resp

    raise RuntimeError(f"Failed to GET {url} after {_RETRY_ATTEMPTS} attempts")


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def _fetch_repo(owner: str, repo: str, token: Optional[str], log: Callable) -> dict:
    log(f"Fetching repository metadata for {owner}/{repo}...")
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    resp = _get(url, _headers(token), log=log)

    if resp.status_code == 404:
        raise ValueError(f"Repository not found: https://github.com/{owner}/{repo}")
    if resp.status_code == 401:
        raise ValueError("GitHub token is invalid or expired.")
    resp.raise_for_status()
    return resp.json()


def _fetch_stargazer_pages(
    owner: str,
    repo: str,
    token: Optional[str],
    sample_size: int,
    deep: bool,
    log: Callable,
) -> list:
    """
    Return a list of {starred_at, user} dicts from the stargazers endpoint.
    In sample mode, stops after `sample_size` entries.
    In deep mode, fetches all pages.
    """
    collected = []
    page = 1
    per_page = 100

    while True:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/stargazers"
        resp = _get(url, _star_headers(token), params={"per_page": per_page, "page": page}, log=log)
        resp.raise_for_status()

        data = resp.json()
        if not data:
            break

        collected.extend(data)
        log(f"Fetched {len(collected)} stargazer(s)...")

        # Stop early in sample mode
        if not deep and len(collected) >= sample_size:
            collected = collected[:sample_size]
            break

        # Check for next page
        if 'rel="next"' not in resp.headers.get("Link", ""):
            break

        page += 1
        time.sleep(0.1)   # polite pacing between pagination calls

    return collected


def _fetch_user(username: str, token: Optional[str], log: Callable) -> Optional[dict]:
    """Fetch a single user profile. Returns None if the account is deleted."""
    url = f"{GITHUB_API}/users/{username}"
    resp = _get(url, _headers(token), log=log)

    if resp.status_code == 404:
        return None   # Account deleted — treat as suspicious in caller
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public scan entry point
# ---------------------------------------------------------------------------

def scan_repo(
    url: str,
    token: Optional[str] = None,
    sample_size: int = 1000,
    deep: bool = False,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Scan a GitHub repository for fake stars.

    Args:
        url:               GitHub repository URL or "owner/repo" shorthand.
        token:             GitHub personal access token.
                           Without: 60 req/hr.  With: 5 000 req/hr.
        sample_size:       How many stargazers to examine (default 1 000).
                           Results are extrapolated to the full star count.
        deep:              If True, scan ALL stargazers regardless of count.
        progress_callback: Optional callable(str) for progress messages.

    Returns:
        A dict with keys: repo, scan, results, suspicious_users, all_results.
    """
    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    owner, repo_name = _parse_repo_url(url)

    # ── Step 1: Repo metadata ────────────────────────────────────────────────
    repo_info   = _fetch_repo(owner, repo_name, token, log)
    total_stars = int(repo_info.get("stargazers_count", 0))

    target = total_stars if deep else min(sample_size, total_stars)
    log(f"Repository has {total_stars:,} star(s). Targeting {target:,} for analysis.")

    if total_stars == 0:
        raise ValueError("This repository has no stars to analyse.")

    # ── Step 2: Fetch stargazer list ─────────────────────────────────────────
    stargazers = _fetch_stargazer_pages(
        owner, repo_name, token, sample_size=sample_size, deep=deep, log=log
    )
    sampled_count = len(stargazers)
    log(f"Collected {sampled_count:,} stargazers. Beginning account analysis...")

    # ── Step 3: Analyse each stargazer ──────────────────────────────────────
    all_results        = []
    rate_limited_count = 0

    for idx, sg in enumerate(stargazers):
        star_date_str = sg.get("starred_at", "")
        basic_user    = sg.get("user", {})
        username      = basic_user.get("login", "unknown")

        if idx % 50 == 0:
            log(f"Analysing account {idx + 1}/{sampled_count}: @{username}")

        user_detail = _fetch_user(username, token, log)

        if user_detail is None:
            # Deleted account — definitely suspicious
            all_results.append({
                "username":  username,
                "star_date": star_date_str,
                "suspicious": True,
                "score":     100,
                "reasons":   ["Account has been deleted or does not exist"],
                "user_data": None,
            })
            time.sleep(_BASE_SLEEP)
            continue

        is_suspicious, reasons, score = score_user(user_detail, star_date_str)

        all_results.append({
            "username":   username,
            "star_date":  star_date_str,
            "suspicious": is_suspicious,
            "score":      score,
            "reasons":    reasons,
            "user_data":  {
                "created_at":       user_detail.get("created_at"),
                "updated_at":       user_detail.get("updated_at"),
                "followers":        user_detail.get("followers", 0),
                "following":        user_detail.get("following", 0),
                "public_repos":     user_detail.get("public_repos", 0),
                "public_gists":     user_detail.get("public_gists", 0),
                "bio":              user_detail.get("bio"),
                "name":             user_detail.get("name"),
                "location":         user_detail.get("location"),
                "email":            user_detail.get("email"),
                "blog":             user_detail.get("blog"),
                "twitter_username": user_detail.get("twitter_username"),
                "html_url":         user_detail.get("html_url"),
            },
        })

        time.sleep(_BASE_SLEEP)  # polite pacing

    # ── Step 4: Statistics ───────────────────────────────────────────────────
    analysed_count = len(all_results)
    fake_count     = sum(1 for r in all_results if r["suspicious"])

    fake_rate = fake_count / analysed_count if analysed_count > 0 else 0.0

    estimated_total_fake = round(fake_rate * total_stars)
    estimated_real       = total_stars - estimated_total_fake

    # Confidence scales with sample size
    if sampled_count >= 1000:
        confidence = "High"
        margin     = round(fake_rate * 0.05 * total_stars)
    elif sampled_count >= 500:
        confidence = "Medium"
        margin     = round(fake_rate * 0.10 * total_stars)
    else:
        confidence = "Low"
        margin     = round(fake_rate * 0.20 * total_stars)

    suspicious_users = sorted(
        [r for r in all_results if r["suspicious"]],
        key=lambda r: r["score"],
        reverse=True,
    )

    return {
        "repo": {
            "owner":       owner,
            "name":        repo_name,
            "full_name":   f"{owner}/{repo_name}",
            "url":         f"https://github.com/{owner}/{repo_name}",
            "total_stars": total_stars,
            "description": repo_info.get("description") or "",
            "created_at":  repo_info.get("created_at") or "",
            "language":    repo_info.get("language") or "",
            "forks":       repo_info.get("forks_count", 0),
            "watchers":    repo_info.get("watchers_count", 0),
            "open_issues": repo_info.get("open_issues_count", 0),
        },
        "scan": {
            "mode":                   "deep" if deep else "sample",
            "sampled":                sampled_count,
            "analysed":               analysed_count,
            "rate_limited_skipped":   rate_limited_count,
            "scanned_at":             datetime.now(timezone.utc).isoformat(),
        },
        "results": {
            "fake_in_sample":       fake_count,
            "real_in_sample":       analysed_count - fake_count,
            "fake_rate_pct":        round(fake_rate * 100, 2),
            "estimated_total_fake": estimated_total_fake,
            "estimated_real":       estimated_real,
            "confidence":           confidence,
            "margin":               margin,
        },
        "suspicious_users": suspicious_users,
        "all_results":      all_results,
    }
