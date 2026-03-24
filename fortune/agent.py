"""
Fortune 🥠 — Agent Interface
Clean, single-function API for OpenClaw, Hermes, Claude, and any other agent framework.

Usage from any agent:
    from fortune.agent import check

    result = check("https://github.com/owner/repo", token="ghp_xxx")
    print(result["report_text"])
    print(result["verdict"])
    print(result["fake_rate_pct"])
"""

import json
import os
from typing import Optional, Callable

from .scanner import scan_repo
from .report import format_text_report, format_json_report, format_summary, verdict, verdict_short


def check(
    url: str,
    token: Optional[str] = None,
    sample_size: int = 1000,
    deep: bool = False,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Scan a GitHub repository for fake stars.

    This is the primary entry point for agent frameworks.
    One URL in → one structured dict out. No side effects.

    Args:
        url:               GitHub repository URL or "owner/repo".
        token:             GitHub personal access token.
                           Falls back to $GITHUB_TOKEN environment variable.
                           Strongly recommended — without it rate limits are severe.
        sample_size:       Stargazers to sample (default 1 000).
                           Results are extrapolated to the full star count.
        deep:              If True, scan every stargazer (slow for large repos).
        progress_callback: Optional callable(str) for live progress messages.

    Returns a dict with the following keys:

        report_text   (str)   Full human-readable text report
        report_json   (dict)  Structured data — parse this for programmatic use
        summary       (str)   One-paragraph plain-English summary
        verdict       (str)   Human verdict string  e.g. "🚨 CONCERNING …"
        verdict_code  (str)   Machine verdict code  e.g. "CONCERNING"
        fake_rate_pct (float) Percentage of sampled stars flagged as fake
        estimated_fake(int)   Estimated fake stars across the full repo
        total_stars   (int)   Reported star count from GitHub
        sampled       (int)   How many accounts were actually examined
        confidence    (str)   "High" | "Medium" | "Low"
        margin        (int)   ±margin on the estimated fake count
        suspicious_users (list) List of flagged accounts with scores and reasons
        raw           (dict)  Full unmodified scanner output

    Raises:
        ValueError  if the URL cannot be parsed or the repo does not exist.
        RuntimeError if GitHub API is unreachable.
    """
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")

    raw = scan_repo(
        url=url,
        token=token,
        sample_size=sample_size,
        deep=deep,
        progress_callback=progress_callback,
    )

    results = raw["results"]
    scan    = raw["scan"]
    fp      = results["fake_rate_pct"]

    return {
        "report_text":      format_text_report(raw),
        "report_json":      json.loads(format_json_report(raw)),
        "summary":          format_summary(raw),
        "verdict":          verdict(fp),
        "verdict_code":     verdict_short(fp),
        "fake_rate_pct":    fp,
        "estimated_fake":   results["estimated_total_fake"],
        "total_stars":      raw["repo"]["total_stars"],
        "sampled":          scan["sampled"],
        "confidence":       results["confidence"],
        "margin":           results["margin"],
        "suspicious_users": raw["suspicious_users"],
        "raw":              raw,
    }
