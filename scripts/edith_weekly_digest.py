#!/usr/bin/env python3
"""
Edith Weekly Digest (GitHub Actions port) - Mastodon stats + state aggregation.
No LLM needed. Reads state/*.json instead of local SQLite DBs.
"""
import os, sys, json, requests
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mastodon import mastodon_request, MASTODON_BASE, get_token
import state

def main():
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    H = {"Authorization": f"Bearer {get_token()}"}

    me = requests.get(f"{MASTODON_BASE}/api/v1/accounts/verify_credentials", headers=H, timeout=20).json()
    followers = me.get("followers_count", "?")
    following = me.get("following_count", "?")
    posts = me.get("statuses_count", "?")

    shipped = state.load("shipped_tools.json", [])
    tools = [t for t in shipped if t.get("shipped_at", "") >= week_ago] if shipped else []

    repos = state.load("posted_repos.json", [])

    handled = state.load("handled_replies.json", [])
    signals = state.load("handled_signals.json", [])

    lines = []
    lines.append("EDITH WEEKLY DIGEST")
    lines.append(f"Followers: {followers} | Following: {following} | Total posts: {posts}")
    lines.append("")
    lines.append(f"Tools shipped this week: {len(tools)}")
    for t in tools:
        lines.append(f"  - {t.get('title', '?')}: {t.get('url', '?')}")
    lines.append("")
    lines.append(f"Repos posted: {len(repos)}")
    lines.append("")
    lines.append(f"Replies handled: {len(handled)}")
    lines.append(f"Signals reciprocated: {len(signals)}")
    lines.append("")
    lines.append("---")
    lines.append("Managed by Edith automation suite")

    output = "\n".join(lines)
    print(output)

if __name__ == "__main__":
    main()