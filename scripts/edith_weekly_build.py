#!/usr/bin/env python3
"""
Edith Weekly Build (GitHub Actions port) - LLM generates tool HTML -> Vercel deploy -> Mastodon post.
Replaces `hermes chat -q` with direct Agnes API, SQLite with state/*.json.
"""
import json, os, sys, re, time, random, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mastodon import post as m_post, mastodon_request, MASTODON_BASE, get_token
from llm import chat
import state

VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
MASTODON_TOKEN = os.environ.get("MASTODON_TOKEN", "")
FOOTER_HTML = 'more free tools &amp; daily repo picks &rarr; <a href="https://t.me/Daily_Diff" target="_blank">t.me/Daily_Diff</a>'

CATEGORIES = [
    "converter", "encoder/decoder", "checker/validator", "generator",
    "analyzer/inspector", "calculator", "formatter/beautifier", "visualizer",
]

def recent_categories(shipped, n=2):
    recent = shipped[-n:] if len(shipped) >= n else shipped
    return [t.get("category") for t in recent if t.get("category")]

def slugify(title):
    s = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return f"{s[:30]}-edith"

def generate_tool_html(shipped):
    avoid_titles = [t.get("title", "") for t in shipped]
    avoid_txt = ("Do NOT repeat any of these already-shipped tools: " + "; ".join(avoid_titles)) if avoid_titles else "No prior tools shipped yet."
    recent_cats = recent_categories(shipped, 2)
    available_cats = [c for c in CATEGORIES if c not in recent_cats] or CATEGORIES
    chosen_category = random.choice(available_cats)

    prompt = f"""You invent ONE tiny, genuinely useful, purely client-side browser tool (single HTML file, inline CSS+JS, no external JS libraries, Google Fonts CDN allowed).

{avoid_txt}

The tool MUST be a "{chosen_category}" type tool (this category was chosen to keep variety across recent ships -- don't argue with it, build within it).

Requirements:
- Single self-contained HTML file, starts with <!DOCTYPE html>.
- Dark theme: background #000000, accent color #BFFF00 (neon lime), body text #e8e8e8.
- Mobile-first, responsive, one page, no backend/server calls -- everything runs in the browser.
- Include a <title> with the tool's name.
- Include a visible footer at the bottom of <body> with exactly this HTML: <footer>{FOOTER_HTML}</footer>
- Keep it small and focused: one clear utility. Security/privacy/dev-tool themed ideas preferred.
- Respect prefers-reduced-motion if you use any animation.

Return ONLY the raw HTML file content. No markdown code fences, no explanation, no commentary before or after."""

    raw, err = chat(prompt, max_tokens=4000, thinking=False, temperature=0.9)
    if err:
        return None, None, None, err
    if not raw:
        return None, None, None, "Empty LLM response"

    raw = re.sub(r'^```(?:html)?\s*', '', raw)
    raw = re.sub(r'```\s*$', '', raw).strip()

    if "<html" not in raw.lower() or "<!doctype" not in raw.lower():
        return None, None, None, "Generated output is not a valid HTML document"

    title_match = re.search(r'<title>(.*?)</title>', raw, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else None
    if not title:
        return None, None, None, "Generated HTML has no <title>"
    if title in avoid_titles:
        return None, None, None, f"Duplicate idea: {title}"

    if "Daily_Diff" not in raw:
        raw = raw.replace("</body>", f"<footer>{FOOTER_HTML}</footer></body>")

    return title, chosen_category, raw, None

def deploy(name, html):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "name": name,
        "files": [{"file": "index.html", "data": html}],
        "project": name,
        "target": "production",
        "projectSettings": {"framework": None}
    }
    res = requests.post("https://api.vercel.com/v13/deployments?skipAutoDetectionConfirmation=1",
                        headers=headers, json=payload)
    if res.status_code not in (200, 201):
        return None, f"Deploy failed: {res.status_code} - {res.text[:300]}"
    requests.patch(f"https://api.vercel.com/v9/projects/{name}", headers=headers,
                   json={"ssoProtection": None, "passwordProtection": None})
    time.sleep(2)
    proj = requests.get(f"https://api.vercel.com/v9/projects/{name}", headers=headers).json()
    aliases = proj.get("targets", {}).get("production", {}).get("alias", [])
    clean = next((a for a in aliases if a == f"{name}.vercel.app"), aliases[0] if aliases else f"{name}.vercel.app")
    return f"https://{clean}", None

def verify(url):
    try:
        r = requests.get(url, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        if "vercel.com/login" in r.url or "sso-api" in r.url:
            return False, "Redirected to Vercel login"
        if "Daily_Diff" not in r.text:
            return False, "Footer credit missing"
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    shipped = state.load("shipped_tools.json", [])
    print("[Edith] Generating a new tool idea...", file=sys.stderr)
    title, category, html, err = generate_tool_html(shipped)
    if err:
        print(f"BUILD FAILED at idea generation: {err}")
        sys.exit(1)

    name = slugify(title)
    print(f"[Edith] Deploying {name} ({title}, category={category})...", file=sys.stderr)
    url, err = deploy(name, html)
    if err:
        print(f"BUILD FAILED at deploy: {err}")
        sys.exit(1)

    print(f"[Edith] Verifying {url}...", file=sys.stderr)
    ok, err = verify(url)
    if not ok:
        time.sleep(4)
        ok, err = verify(url)
        if not ok:
            print(f"BUILD FAILED at verification ({url}): {err}")
            sys.exit(1)

    # — POST FORMAT (master prompt template) —
    # Template B: {Name} — {one-line what it is}
    #             {2-3 sentences: what it does, who it's for, key capability}
    #             🔗 Link
    caption = (f"{title} — a tiny, purely client-side {category.lower()} tool, runs entirely in the browser. "
               f"No backend, no install, no data leaves your machine. "
               f"Open source and free, shipped as part of the Daily Diff tool set.\n\n"
               f"🔗 {url}")[:900]
    print(f"[Edith] Posting to Mastodon...", file=sys.stderr)
    post_url, err = m_post(caption)
    if err:
        print(f"BUILD DEPLOYED BUT POST FAILED: {url} | {err}")
        sys.exit(1)

    shipped.append({"name": name, "title": title, "url": url, "category": category})
    state.save("shipped_tools.json", shipped)

    print(f"OK Tool: {title} ({name}) [{category}]")
    print(f"OK Live URL: {url}")
    print(f"OK Mastodon post: {post_url}")

if __name__ == "__main__":
    main()