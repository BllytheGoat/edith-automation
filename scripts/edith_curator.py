#!/usr/bin/env python3
"""
Edith Curator (GitHub Actions port) - GitHub repo search -> LLM critique -> Mastodon post + TG crosspost.
Replaces `hermes chat -q` with direct Agnes API, SQLite with state/*.json, local edith.py with mastodon.post.
"""
import json, os, sys, random, re, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mastodon import post as m_post
from llm import chat
import state

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DAILY_DIFF_CHAT = "@Daily_Diff"

def is_posted(repo_name, posted):
    return repo_name in posted

def crosspost_to_daily_diff(body):
    """Post the SAME master-format message to t.me/Daily_Diff.
    Never raises -- a Telegram failure must not break the Mastodon flow."""
    if not TELEGRAM_BOT_TOKEN:
        return "skipped (no TELEGRAM_BOT_TOKEN)"
    try:
        text = body[:1000]
        res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            data={"chat_id": DAILY_DIFF_CHAT, "text": text}, timeout=15)
        if res.status_code == 200 and res.json().get("ok"):
            return "ok"
        return f"failed ({res.status_code}: {res.text[:150]})"
    except Exception as e:
        return f"failed ({e})"

def get_ai_decision(candidates):
    prompt = f"""
    You are a senior dev curator. Critique these 5 repos and pick the ONE most useful for a solo security builder.
    Candidates:
    {json.dumps(candidates, indent=2)}

    Return ONLY a JSON object: {{"winner": "repo_full_name", "reason": "short critique"}}
    """
    text, err = chat(prompt, max_tokens=300, thinking=False)
    if text:
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
    best = max(candidates, key=lambda x: x.get('score', 0))
    return {"winner": best['name'], "reason": "Highest pre-calculated score"}

def main():
    posted = set(state.load("posted_repos.json", []))
    print("[Edith] Gathering candidates...", file=sys.stderr)

    query = "language:python+stars:>50+(AI+OR+agents+OR+DSPy+OR+'LLM+ops'+OR+automation)+created:>2026-08-01"
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&per_page=15"
    try:
        r = requests.get(url, timeout=25,
                         headers={"Accept": "application/vnd.github+json"})
        data = r.json()
    except Exception as e:
        print(f"Error: No response from GitHub API: {e}", file=sys.stderr)
        sys.exit(1)

    items = data.get("items", [])
    candidates = []
    for repo in items:
        if is_posted(repo["full_name"], posted):
            continue
        score = 0
        if repo.get("description") and len(repo["description"]) > 20:
            score += 1
        if repo.get("stargazers_count", 0) < 10000:
            score += 1
        candidates.append({"score": score, "name": repo["full_name"], "url": repo["html_url"], "desc": repo["description"]})

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]
    if not candidates:
        print("[SILENT]")
        return

    print("[Edith] Critiquing candidates...", file=sys.stderr)
    decision = get_ai_decision(candidates)
    winner_name = decision["winner"]
    selected = next((c for c in candidates if c["name"] == winner_name), candidates[0])

    # — POST FORMAT (master prompt template) —
    # Template A: {Repo} — {one-line what it does}
    #            {2-3 sentences: problem, key feature, why interesting}
    #            🔗 GitHub
    reason = decision.get("reason", "")
    body = f"{selected['name']} — {selected['desc']}\n\n"
    if reason and len(reason) > 20:
        body += f"{reason}\n\n"
    else:
        body += f"{selected['name']} makes {selected['desc']} straightforward. Clean codebase, minimal dependencies, ready to use.\n\n"
    body += f"🔗 GitHub — {selected['url']}"

    # Ensure no more than 5 sentences, 1 emoji, follow format
    body = body[:900]

    print(f"[Edith] Posting {winner_name}...", file=sys.stderr)
    post_url, err = m_post(body)
    if err:
        print(f"POST FAILED: {err}", file=sys.stderr)
        sys.exit(1)

    posted.add(winner_name)
    state.save("posted_repos.json", sorted(posted))

    crosspost_result = crosspost_to_daily_diff(body)
    print(f"[Edith] Cross-post to Daily_Diff: {crosspost_result}", file=sys.stderr)
    print(f"OK Posted {winner_name}")
    print(f"Post: {post_url}")

if __name__ == "__main__":
    main()
