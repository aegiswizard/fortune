"""
Fortune 🥠 — Report Formatter
Renders scan results as human-readable text or structured JSON.
"""

import json
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def verdict(fake_rate_pct: float) -> str:
    if fake_rate_pct < 5.0:
        return "✅  LIKELY CLEAN — Low fake star rate detected"
    elif fake_rate_pct < 15.0:
        return "⚠️   MODERATE — Some suspicious activity detected"
    elif fake_rate_pct < 35.0:
        return "🚨  CONCERNING — High fake star rate detected"
    else:
        return "🔴  CRITICAL — Majority of sampled stars appear fake"


def verdict_short(fake_rate_pct: float) -> str:
    if fake_rate_pct < 5.0:
        return "LIKELY_CLEAN"
    elif fake_rate_pct < 15.0:
        return "MODERATE"
    elif fake_rate_pct < 35.0:
        return "CONCERNING"
    else:
        return "CRITICAL"


# ---------------------------------------------------------------------------
# Score bar helper
# ---------------------------------------------------------------------------

def _bar(score: int, width: int = 10) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Text report
# ---------------------------------------------------------------------------

def format_text_report(data: dict) -> str:
    repo    = data["repo"]
    scan    = data["scan"]
    results = data["results"]
    susp    = data["suspicious_users"]

    fake_pct   = results["fake_rate_pct"]
    estimated  = results["estimated_total_fake"]
    margin     = results["margin"]
    confidence = results["confidence"]

    divider = "━" * 56

    lines = [
        "",
        f"🥠 {divider}",
        f"   FORTUNE REPORT  ·  {repo['full_name']}",
        f"🥠 {divider}",
        "",
        f"   {verdict(fake_pct)}",
        "",
        "   📦  REPOSITORY",
        f"       URL          {repo['url']}",
        f"       Description  {repo['description'] or '—'}",
        f"       Language     {repo['language'] or '—'}",
        f"       Stars        {repo['total_stars']:,}",
        f"       Forks        {repo['forks']:,}",
        f"       Created      {repo['created_at'][:10] if repo['created_at'] else '—'}",
        "",
        "   🔬  SCAN",
        f"       Mode         {'Deep (all stargazers)' if scan['mode'] == 'deep' else 'Sample'}",
        f"       Sampled      {scan['sampled']:,} stargazers",
        f"       Analysed     {scan['analysed']:,} accounts",
        f"       Timestamp    {scan['scanned_at'][:19].replace('T', ' ')} UTC",
        "",
        "   🎯  RESULTS",
        f"       Fake in sample    {results['fake_in_sample']:,} / {scan['analysed']:,}",
        f"       Fake rate         {fake_pct}%",
        f"       Est. total fake   ~{estimated:,}  (±{margin:,})",
        f"       Est. real stars   ~{results['estimated_real']:,}",
        f"       Confidence        {confidence}",
        "",
    ]

    if susp:
        lines.append(f"   👻  SUSPICIOUS ACCOUNTS  ({len(susp)} flagged in sample)")
        lines.append("")
        for user in susp[:25]:
            bar   = _bar(user["score"])
            lines.append(f"       [{bar}] {user['score']:3d}/100  @{user['username']}")
            for reason in user["reasons"][:2]:
                lines.append(f"                ↳ {reason}")
            lines.append("")

        if len(susp) > 25:
            lines.append(f"       … and {len(susp) - 25} more. Use --output json for full list.")
            lines.append("")
    else:
        lines.append("   ✅  No suspicious accounts found in sample.")
        lines.append("")

    lines += [
        f"   {divider}",
        "   ⚠️   DISCLAIMER",
        "       Fortune uses public heuristics and statistical extrapolation.",
        "       False positives are possible. Some repos are targeted by fake",
        "       stars without the owner's knowledge. Results are indicative,",
        "       not definitive.",
        "",
        f"   🛠️   Fortune v1.0.0  ·  MIT License",
        f"       https://github.com/aegiswizard/fortune",
        "",
        f"🥠 {divider}",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def format_json_report(data: dict) -> str:
    fake_pct = data["results"]["fake_rate_pct"]

    output = {
        "fortune_version": "1.0.0",
        "repository":      data["repo"],
        "scan":            data["scan"],
        "results":         data["results"],
        "verdict":         verdict(fake_pct),
        "verdict_code":    verdict_short(fake_pct),
        "suspicious_users": [
            {
                "username":   u["username"],
                "github_url": f"https://github.com/{u['username']}",
                "score":      u["score"],
                "star_date":  u["star_date"],
                "reasons":    u["reasons"],
                "user_data":  u.get("user_data"),
            }
            for u in data["suspicious_users"]
        ],
    }

    return json.dumps(output, indent=2, default=str)


# ---------------------------------------------------------------------------
# Minimal summary (for agent use)
# ---------------------------------------------------------------------------

def format_summary(data: dict) -> str:
    """One-paragraph summary suitable for embedding in an agent's response."""
    repo    = data["repo"]
    results = data["results"]
    scan    = data["scan"]

    return (
        f"Fortune scanned {repo['full_name']} ({repo['total_stars']:,} stars). "
        f"Sample: {scan['sampled']:,} stargazers analysed. "
        f"Fake rate: {results['fake_rate_pct']}% — "
        f"estimated {results['estimated_total_fake']:,} fake stars out of {repo['total_stars']:,} total "
        f"(±{results['margin']:,}, {results['confidence']} confidence). "
        f"Verdict: {verdict_short(results['fake_rate_pct'])}."
    )
