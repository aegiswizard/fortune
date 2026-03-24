"""
Fortune 🥠 — Command-Line Interface
Usage: fortune check <github-url> [options]
"""

import argparse
import json
import os
import sys


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = """
  🥠  Fortune — Fake GitHub Star Detector  v1.0.0
      github.com/aegiswizard/fortune  ·  MIT License
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fortune",
        description="🥠 Fortune — Detect fake GitHub stars on any public repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  fortune check https://github.com/owner/repo
  fortune check https://github.com/owner/repo --token ghp_xxxx
  fortune check https://github.com/owner/repo --sample 500
  fortune check https://github.com/owner/repo --deep
  fortune check https://github.com/owner/repo --output json
  fortune check https://github.com/owner/repo --output json > report.json

environment variables:
  GITHUB_TOKEN   GitHub personal access token (recommended)
                 Without a token: 60 API requests/hr (very slow for large repos)
                 With a token:  5 000 API requests/hr (analysing 1 000 stars ≈ 4 min)
                 Get a free token: https://github.com/settings/tokens
        """,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # ── check subcommand ────────────────────────────────────────────────────
    check = subparsers.add_parser(
        "check",
        help="Scan a GitHub repository for fake stars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument(
        "url",
        help="GitHub repository URL  (e.g. https://github.com/owner/repo)",
    )
    check.add_argument(
        "--token", "-t",
        default=os.environ.get("GITHUB_TOKEN"),
        metavar="TOKEN",
        help="GitHub personal access token  (default: $GITHUB_TOKEN env var)",
    )
    check.add_argument(
        "--sample", "-s",
        type=int,
        default=1000,
        metavar="N",
        help="Stargazers to sample  (default: 1 000). Results are extrapolated to the full count.",
    )
    check.add_argument(
        "--deep", "-d",
        action="store_true",
        help="Deep mode: scan ALL stargazers. Slow for large repos, always free.",
    )
    check.add_argument(
        "--output", "-o",
        choices=["text", "json"],
        default="text",
        help="Output format  (default: text)",
    )
    check.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages  (stderr)",
    )

    # ── version subcommand ──────────────────────────────────────────────────
    subparsers.add_parser("version", help="Print version and exit")

    args = parser.parse_args()

    # Default: print help
    if not args.command:
        print(BANNER)
        parser.print_help()
        sys.exit(0)

    if args.command == "version":
        print("fortune 1.0.0")
        sys.exit(0)

    # ── Run check ───────────────────────────────────────────────────────────
    if args.command == "check":
        from fortune.scanner import scan_repo
        from fortune.report import format_text_report, format_json_report

        def progress(msg: str) -> None:
            if not args.quiet and args.output == "text":
                print(f"  ⏳ {msg}", file=sys.stderr)

        # Token warning
        if not args.token:
            print(
                "\n  ⚠️  No GitHub token detected.\n"
                "     Fortune works without a token but is limited to 60 API requests/hour.\n"
                "     For a 1 000-star sample you need ~1 011 requests — this will rate-limit.\n\n"
                "     ➜  Set a token:  export GITHUB_TOKEN=ghp_xxxx\n"
                "     ➜  Or pass one:  fortune check <url> --token ghp_xxxx\n"
                "     ➜  Get one free: https://github.com/settings/tokens\n",
                file=sys.stderr,
            )

        print(BANNER, file=sys.stderr)
        print(f"  Scanning → {args.url}\n", file=sys.stderr)

        try:
            data = scan_repo(
                url=args.url,
                token=args.token,
                sample_size=args.sample,
                deep=args.deep,
                progress_callback=progress,
            )
        except ValueError as exc:
            print(f"\n  ❌  {exc}\n", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n  Scan interrupted.\n", file=sys.stderr)
            sys.exit(0)
        except Exception as exc:
            print(f"\n  ❌  Unexpected error: {exc}\n", file=sys.stderr)
            sys.exit(1)

        if args.output == "json":
            print(format_json_report(data))
        else:
            print(format_text_report(data))


if __name__ == "__main__":
    main()
