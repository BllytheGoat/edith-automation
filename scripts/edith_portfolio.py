#!/usr/bin/env python3
"""
Edith Portfolio Sync (GitHub Actions port) - fetches Vercel projects, generates gallery HTML, deploys.
No LLM needed. Reads state/shipped_tools.json for originals.
"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import state

VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
PORTFOLIO_NAME = "edith-portfolio"
OUTPUT_FILE = "/tmp/portfolio.html"

COLOR_BG = "#000000"
COLOR_ACCENT = "#BFFF00"

def get_all_vercel_projects():
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    try:
        res = requests.get("https://api.vercel.com/v13/projects", headers=headers, timeout=30)
        if res.status_code == 200:
            return res.json().get("projects", [])
    except Exception as e:
        print(f"Error fetching Vercel projects: {e}")
    return []

def get_originals():
    shipped = state.load("shipped_tools.json", [])
    return {t.get("name", "").lower() for t in shipped if t.get("name")}

def generate_html(projects, originals):
    from datetime import datetime as _dt
    rows = ""
    for i, p in enumerate(projects, 1):
        name = p['name']
        url = f"https://{p.get('defaultDomain', p.get('name') + '.vercel.app')}"
        is_original = name.lower() in originals
        idx = str(i).zfill(2)
        card_class = "card card-original" if is_original else "card"
        tag_label = "ORIGINAL" if is_original else "MAINTAINED"
        tag_class = "tag tag-original" if is_original else "tag tag-maintained"
        rows += f'''
        <a href="{url}" target="_blank" class="{card_class}">
            <div class="card-top">
                <span class="card-idx">{idx}</span>
                <span class="{tag_class}">{tag_label}</span>
            </div>
            <div class="card-name">{name}</div>
            <div class="card-cta">OPEN PROJECT <span class="arrow">➜</span></div>
        </a>'''

    updated = _dt.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EDITH // PROJECTS</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{ --paper: #EFEAE0; --ink: #111111; --hazard: #FFC700; --alert: #FF3B30; }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--paper); color: var(--ink); font-family: 'Space Mono', monospace; margin: 0; padding: 5vw 4vw 12vw; }}
  .wrap {{ max-width: 860px; margin: 0 auto; }}
  .stripes {{ height: 14px; background: repeating-linear-gradient(-45deg, var(--ink), var(--ink) 14px, var(--hazard) 14px, var(--hazard) 28px); border: 4px solid var(--ink); border-bottom: none; margin-bottom: -4px; }}
  .hero {{ background: var(--hazard); border: 4px solid var(--ink); box-shadow: 10px 10px 0 var(--ink); padding: 32px 28px; margin-bottom: 20px; }}
  .hero h1 {{ font-family: 'Archivo Black', sans-serif; color: var(--ink); font-size: clamp(2.6rem, 10vw, 5rem); line-height: 0.95; margin: 0 0 12px; letter-spacing: -0.01em; }}
  .hero p {{ font-family: 'Space Mono', monospace; color: var(--ink); font-weight: 700; font-size: 14px; max-width: 44ch; margin: 0; text-transform: uppercase; letter-spacing: 0.02em; }}
  .stat-strip {{ display: flex; gap: 14px; margin: 30px 0 36px; flex-wrap: wrap; }}
  .stat-box {{ background: var(--paper); border: 4px solid var(--ink); box-shadow: 6px 6px 0 var(--ink); color: var(--ink); padding: 10px 16px; font-weight: 700; font-size: 13px; font-family: 'Space Mono', monospace; text-transform: uppercase; }}
  .stat-box b {{ font-family: 'Archivo Black', sans-serif; font-size: 20px; display: block; }}
  .listing {{ display: flex; flex-direction: column; gap: 18px; }}
  .card {{ display: block; background: var(--paper); color: var(--ink); border: 4px solid var(--ink); box-shadow: 8px 8px 0 var(--ink); padding: 20px 22px; text-decoration: none; transition: transform 0.08s ease, box-shadow 0.08s ease; }}
  .card:hover {{ transform: translate(6px, 6px); box-shadow: 2px 2px 0 var(--ink); }}
  .card-original {{ background: var(--alert); color: var(--paper); }}
  .card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
  .card-idx {{ font-family: 'Archivo Black', sans-serif; font-size: 22px; }}
  .tag {{ font-size: 11px; font-weight: 700; padding: 4px 10px; border: 3px solid currentColor; text-transform: uppercase; }}
  .tag-original {{ background: var(--ink); color: var(--hazard); border-color: var(--ink); }}
  .tag-maintained {{ background: var(--paper); color: var(--ink); border-color: var(--ink); }}
  .card-name {{ font-family: 'Archivo Black', sans-serif; font-size: clamp(1.3rem, 4vw, 1.8rem); margin-bottom: 14px; word-break: break-word; }}
  .card-cta {{ font-size: 12px; font-weight: 700; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px; }}
  .arrow {{ display: inline-block; }}
  .card:hover .arrow {{ transform: translateX(4px); }}
  footer {{ margin-top: 60px; padding: 20px; background: var(--ink); color: var(--hazard); border: 4px solid var(--ink); box-shadow: 8px 8px 0 var(--alert); font-size: 12px; font-weight: 700; }}
  footer a {{ color: var(--hazard); text-decoration: underline; text-decoration-thickness: 2px; }}
  .meta {{ margin-top: 8px; opacity: 0.7; font-weight: 400; color: var(--paper); }}
  .footer-stripes {{ height: 10px; background: repeating-linear-gradient(-45deg, var(--hazard), var(--hazard) 10px, var(--ink) 10px, var(--ink) 20px); border: 4px solid var(--ink); border-top: none; margin-top: -4px; }}
  a:focus-visible {{ outline: 3px solid var(--alert); outline-offset: 2px; }}
  @media (prefers-reduced-motion: reduce) {{ .card {{ transition: none; }} }}
  @media (max-width: 520px) {{ .hero {{ padding: 24px 18px; }} .card {{ padding: 16px; }} }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="stripes"></div>
    <div class="hero">
      <h1>EDITH.</h1>
      <p>Solo builder. Security-leaning. Ships small, sharp tools instead of writing about them.</p>
    </div>
    <div class="stat-strip">
      <div class="stat-box">PROJECTS<b>{len(projects)}</b></div>
      <div class="stat-box">STATUS<b>LIVE</b></div>
      <div class="stat-box">MODE<b>SHIPPING</b></div>
    </div>
    <div class="listing">{rows}</div>
    <footer>
      MANAGED BY EDITH — <a href="https://t.me/Daily_Diff" target="_blank">MORE FREE TOOLS & DAILY REPO PICKS → T.ME/DAILY_DIFF</a>
      <div class="meta">last synced {updated}</div>
    </footer>
    <div class="footer-stripes"></div>
  </div>
</body>
</html>'''
    return html

def deploy_to_vercel(html_content):
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "name": PORTFOLIO_NAME,
        "files": [{"file": "index.html", "data": html_content}],
        "project": PORTFOLIO_NAME,
        "target": "production",
        "projectSettings": {"framework": None}
    }
    res = requests.post("https://api.vercel.com/v13/deployments?skipAutoDetectionConfirmation=1",
                        headers=headers, json=payload, timeout=30)
    if res.status_code in (200, 201):
        data = res.json()
        return data.get("alias", [data.get("url")])[0] if data.get("alias") else data.get("url")
    return f"Error: {res.status_code} - {res.text[:500]}"

def main():
    print("[Portfolio] Fetching all Vercel projects...")
    all_projects = get_all_vercel_projects()
    originals = get_originals()
    if not all_projects:
        print("No projects found on Vercel account.")
        return
    print(f"[Portfolio] Found {len(all_projects)} total projects. Generating Gallery...")
    html = generate_html(all_projects, originals)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(html)
    print("[Portfolio] Deploying Master Portfolio to Vercel...")
    url = deploy_to_vercel(html)
    print(f"OK Master Portfolio Live: {url}")
    print(f"OK Total Projects Attributed: {len(all_projects)}")

if __name__ == "__main__":
    main()