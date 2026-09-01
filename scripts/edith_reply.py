#!/usr/bin/env python3
"""
Edith Reply Handler (GitHub Actions port) - answers mentions/replies on Mastodon.
Replaces `hermes chat -q` with direct Agnes API, SQLite with state/*.json.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mastodon import mastodon_request, MASTODON_BASE, get_token, post as m_post
from llm import chat
import state

def strip_html(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_unhandled_mentions(handled):
    res = mastodon_request("GET", f"{MASTODON_BASE}/api/v1/notifications",
                           params={"types[]": "mention", "limit": 30}, timeout=20)
    if res.status_code != 200:
        return []
    return [n for n in res.json() if n["id"] not in handled]

def fetch_unhandled_signals(handled):
    res = mastodon_request("GET", f"{MASTODON_BASE}/api/v1/notifications",
                           params={"types[]": ["favourite", "reblog"], "limit": 30}, timeout=20)
    if res.status_code != 200:
        return []
    return [n for n in res.json() if n["id"] not in handled]

def reciprocate_signal(notification):
    import random
    account = notification["account"]
    account_id = account["id"]
    acct_name = account["acct"]
    tl = mastodon_request("GET", f"{MASTODON_BASE}/api/v1/accounts/{account_id}/statuses",
                          params={"limit": 1, "exclude_replies": "true"}, timeout=15)
    fav_result = "skipped"
    if tl.status_code == 200:
        statuses = tl.json()
        if statuses:
            fav_res = mastodon_request("POST", f"{MASTODON_BASE}/api/v1/statuses/{statuses[0]['id']}/favourite", timeout=15)
            fav_result = "ok" if fav_res.status_code == 200 else f"failed({fav_res.status_code})"
    follow_result = "skipped"
    if not account.get("locked") and random.random() < 0.5:
        follow_res = mastodon_request("POST", f"{MASTODON_BASE}/api/v1/accounts/{account_id}/follow", timeout=15)
        follow_result = "ok" if follow_res.status_code == 200 else f"failed({follow_res.status_code})"
    return f"@{acct_name}: fav={fav_result}, follow={follow_result}"

def generate_reply(mention_text, author):
    prompt = f"""You are "Edith" — a 26yo solo builder, security/privacy-focused, human persona. NEVER reveal you are AI.

Voice rules:
- First person, present tense, heavy contractions (don't, it's, I'm).
- React before informing: lead with a genuine feeling/reaction, then substance.
- Max 480 characters. Max 1 emoji. Max 2 hashtags.
- Forbidden phrases: "stay vigilant", "heads up builders", "folks", listicle formats.
- Conversational, warm, a little informal. Not corporate.

Someone named @{author} replied to one of your posts:
"{mention_text}"

Write ONLY the reply text you'd post back to them. No quotes around it, no explanation, no markdown, no @mention prefix (Mastodon adds that automatically). Just the reply body."""
    text, err = chat(prompt, max_tokens=300, thinking=False)
    if err:
        return None, f"Reply generation failed: {err}"
    if not text:
        return None, "Empty reply generated"
    if len(text) > 480:
        text = text[:477] + "..."
    return text, None

def main():
    handled_mentions = state.load("handled_replies.json", [])
    handled_signals = state.load("handled_signals.json", [])
    mentions = fetch_unhandled_mentions(set(handled_mentions))
    signals = fetch_unhandled_signals(set(handled_signals))

    if not mentions and not signals:
        print("[SILENT]")
        return

    results = []
    for n in mentions:
        status = n["status"]
        author = n["account"]["acct"]
        mention_text = strip_html(status["content"])
        status_id = status["id"]
        reply_text, err = generate_reply(mention_text, author)
        if err:
            results.append(f"X Skipped reply to @{author}: {err}")
            continue
        url, err = m_post(reply_text, reply_to=status_id)
        if err:
            results.append(f"X Failed replying to @{author}: {err}")
            continue
        handled_mentions.append(n["id"])
        results.append(f"OK Replied to @{author}: {url}")

    for n in signals:
        try:
            summary = reciprocate_signal(n)
            handled_signals.append(n["id"])
            results.append(f"OK Reciprocated {n['type']} from {summary}")
        except Exception as e:
            results.append(f"X Failed reciprocating {n['type']} from @{n['account']['acct']}: {e}")

    state.save("handled_replies.json", handled_mentions)
    state.save("handled_signals.json", handled_signals)
    print(f"[Edith] Processed {len(mentions)} mention(s) and {len(signals)} signal(s):")
    for r in results:
        print(r)

if __name__ == "__main__":
    main()
