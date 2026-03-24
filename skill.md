# 🥠 Fortune — Fake GitHub Star Detector Skill

**Version:** 1.0.0  
**License:** MIT  
**Source:** https://github.com/aegiswizard/fortune  
**Compatible with:** OpenClaw · Hermes · Claude agents · Any Python agent framework

---

## What This Skill Does

Fortune detects fake GitHub stars on any public repository.  
It samples up to 1 000 stargazers, scores each account against 9 behavioral heuristics,
and extrapolates the fake rate to the full star count.  
No BigQuery. No cloud cost. Just the free GitHub REST API.

---

## Trigger Phrases

Your agent should invoke Fortune when the user says something like:

- `"check https://github.com/owner/repo for fake stars"`
- `"how many fake stars does [repo] have"`
- `"scan [url] with fortune"`
- `"is [github url] legit"`
- `"fortune check [url]"`
- `"run fortune on [url]"`
- `"are [repo] stars real"`

---

## Setup (one-time)

```bash
# 1. Clone or install Fortune
git clone https://github.com/aegiswizard/fortune.git
cd fortune
pip install -e .

# 2. Set your GitHub token (free, read-only scope is enough)
export GITHUB_TOKEN=ghp_your_token_here
# Get one at: https://github.com/settings/tokens
```

---

## Usage — CLI (quickest)

```bash
# Basic scan (samples 1 000 stars)
fortune check https://github.com/owner/repo

# Smaller sample (faster)
fortune check https://github.com/owner/repo --sample 200

# Full deep scan (all stars — slow for large repos)
fortune check https://github.com/owner/repo --deep

# JSON output (pipe to jq, files, or agent parsing)
fortune check https://github.com/owner/repo --output json

# Pass token inline
fortune check https://github.com/owner/repo --token ghp_xxx
```

---

## Usage — Python API (for agent code)

### Simple (text report)
```python
from fortune import scan_repo, format_text_report

data   = scan_repo("https://github.com/owner/repo", token="ghp_xxx")
report = format_text_report(data)
print(report)
```

### Agent interface (recommended for structured output)
```python
from fortune.agent import check

result = check("https://github.com/owner/repo", token="ghp_xxx")

# All available keys:
print(result["report_text"])        # Full human-readable report
print(result["summary"])            # One-sentence summary
print(result["verdict"])            # e.g. "🚨 CONCERNING — High fake star rate"
print(result["verdict_code"])       # e.g. "CONCERNING"
print(result["fake_rate_pct"])      # e.g. 8.7
print(result["estimated_fake"])     # e.g. 1078
print(result["total_stars"])        # e.g. 12400
print(result["sampled"])            # e.g. 1000
print(result["confidence"])         # "High" | "Medium" | "Low"
print(result["margin"])             # ± margin on estimated fake count
print(result["suspicious_users"])   # list of flagged accounts

# JSON-serialisable dict:
import json
print(json.dumps(result["report_json"], indent=2))
```

### JSON output keys
```python
{
  "fortune_version": "1.0.0",
  "repository": {
    "full_name":   "owner/repo",
    "url":         "https://github.com/owner/repo",
    "total_stars": 12400,
    "description": "...",
    "language":    "Python",
    "forks":       340,
    ...
  },
  "scan": {
    "mode":      "sample",      # or "deep"
    "sampled":   1000,
    "analysed":  1000,
    "scanned_at":"2026-03-24T12:00:00+00:00"
  },
  "results": {
    "fake_in_sample":        87,
    "real_in_sample":        913,
    "fake_rate_pct":         8.7,
    "estimated_total_fake":  1078,
    "estimated_real":        11322,
    "confidence":            "High",
    "margin":                54
  },
  "verdict":      "🚨 CONCERNING — High fake star rate detected",
  "verdict_code": "CONCERNING",
  "suspicious_users": [
    {
      "username":   "ghostbot123",
      "github_url": "https://github.com/ghostbot123",
      "score":      100,
      "star_date":  "2024-11-03T08:21:44Z",
      "reasons": [
        "Account created on the same day as the star",
        "Zero followers",
        "No public repositories",
        "Ghost account: zero activity across every measurable metric"
      ]
    },
    ...
  ]
}
```

---

## Verdict Codes

| Code           | Fake Rate   | Meaning                                      |
|----------------|-------------|----------------------------------------------|
| `LIKELY_CLEAN` | < 5%        | Low fake star rate — looks legitimate        |
| `MODERATE`     | 5% – 14%    | Some suspicious activity — worth watching    |
| `CONCERNING`   | 15% – 34%   | High fake rate — significant red flag        |
| `CRITICAL`     | ≥ 35%       | Majority of sampled stars appear fake        |

---

## Heuristics Applied (9 signals)

| # | Signal                                    | Max Points |
|---|-------------------------------------------|------------|
| 1 | Account created same day as star          | 40         |
| 2 | Zero followers                            | 15         |
| 3 | Zero public repositories                  | 15         |
| 4 | Following nobody                          | 10         |
| 5 | Completely empty profile (all 6 fields)   | 10         |
| 6 | Account never updated after creation      | 10         |
| 7 | Account very new at time of starring      | 10         |
| 8 | Suspicious username pattern               | 5          |
| 9 | Ghost account combo bonus                 | 15         |

**Threshold:** score ≥ 50 → flagged as suspicious.

---

## Environment Variables

| Variable       | Required    | Description                                        |
|----------------|-------------|----------------------------------------------------|
| `GITHUB_TOKEN` | Recommended | GitHub PAT (read-only scope sufficient)            |
|                |             | Without: 60 req/hr. With: 5 000 req/hr.            |
|                |             | Get free: https://github.com/settings/tokens       |

---

## Rate Limits & Speed

| Mode          | Sample | Est. API calls | Est. time (with token) |
|---------------|--------|----------------|------------------------|
| Sample (1000) | 1 000  | ~1 011         | ~4–5 minutes           |
| Sample (200)  | 200    | ~211           | ~1 minute              |
| Deep (50k)    | All    | ~50 010        | ~10 hours              |

Deep mode is free but slow. Sample mode is the practical default for most use cases.

---

## Statistical Methodology

Fortune uses stratified sampling: it examines the first N stargazers
(ordered by star date, oldest first) and measures the fake rate within
that sample. This rate is then extrapolated to the full star count.

```
fake_rate    = fake_in_sample / analysed
est_fake     = fake_rate × total_stars
margin       = fake_rate × confidence_factor × total_stars
```

Confidence factors: High (≥1000 sample) = 5%, Medium (≥500) = 10%, Low (<500) = 20%.

This is the same methodology used by Dagster's published research on fake stars.

---

## Disclaimer

Fortune uses public heuristics and statistical extrapolation.
False positives exist. Some repos are targeted by fake stars without
the owner's knowledge. Results are indicative, not definitive.
Fortune does not store or share any data it fetches.
