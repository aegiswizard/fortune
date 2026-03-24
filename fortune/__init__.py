"""
Fortune 🥠 — Fake GitHub Star Detector
MIT License | github.com/aegiswizard/fortune

Quick start:
    from fortune import scan_repo, format_text_report

    data   = scan_repo("https://github.com/owner/repo", token="ghp_xxx")
    report = format_text_report(data)
    print(report)

Or via the agent interface:
    from fortune.agent import check
    result = check("https://github.com/owner/repo")
"""

__version__  = "1.0.0"
__author__   = "Aegis Wizard"
__license__  = "MIT"
__url__      = "https://github.com/aegiswizard/fortune"

from .scanner import scan_repo
from .report  import format_text_report, format_json_report, format_summary

__all__ = [
    "scan_repo",
    "format_text_report",
    "format_json_report",
    "format_summary",
]
