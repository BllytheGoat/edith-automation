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

def crosspost_to_daily_diff(repo_name, desc, url):
    if not TELEGRAM_BOT_TOKEN:
        return "skipped (no TELEGRAM_BOT_TOKEN)"
    try:
        text = f"🔍 Repo pick: {repo_name}\n\n{desc}\n\n{url}"[:1000]
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

    VIBES = [
        {"mood": "Caffeinated", "hook": ["Too much coffee. Found this:", "Insomnia hit. Look at this:", "3am finds are the best. Found:"]},
        {"mood": "Skeptical", "hook": ["Actually works? Found {repo}:", "Surprised this exists. {repo}:", "Finally, something that doesn't suck:", "Wait, why isn't everyone using this?"]},
        {"mood": "Hyped", "hook": ["This is a gamechanger.", "Absolute gold mine found:", "Stop everything and look at {repo}:", "Actual magic here:"]},
        {"mood": "Chill", "hook": ["Lazy afternoon find:", "Just some cool stuff for the pile:", "Quietly staring at this repo:", "Slow burn discovery:"]},
        {"mood": "Frustrated", "hook": ["Why did I only find this now?", "Tired of manual work. Found {repo}:", "My current build is broken, so I found this:", "I just want a tool that works. Finally:"]},
    ]
    vibe = random.choice(VIBES)
    hook = random.choice(vibe["hook"]).format(repo=selected["name"])
    text = f"{hook} {selected['name']} — {selected['desc']}. {selected['url']} #buildingpublic"
    text = (text[:475] + "...") if len(text) > 480 else text

    print(f"[Edith] Posting {winner_name} with {vibe['mood']} vibe...", file=sys.stderr)
    post_url, err = m_post(text)
    if err:
        print(f"POST FAILED: {err}", file=sys.stderr)
        sys.exit(1)

    posted.add(winner_name)
    state.save("posted_repos.json", sorted(posted))

    crosspost_result = crosspost_to_daily_diff(selected["name"], selected["desc"], selected["url"])
    print(f"[Edith] Cross-post to Daily_Diff: {crosspost_result}", file=sys.stderr)
    print(f"OK Posted {winner_name} ({vibe['mood']})")
    print(f"Post: {post_url}")

if __name__ == "__main__":
    main()
