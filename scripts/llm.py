"""
Shared LLM helper for Edith automation on GitHub Actions.
Direct call to Agnes API (OpenAI-compatible) - replaces `hermes chat -q`.
"""
import json, os, urllib.request, urllib.error

AGNES_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-2.5-flash"

def chat(prompt, max_tokens=1024, thinking=False, temperature=0.7):
    """Return (text, error). thinking=False disables reasoning for short outputs."""
    key = os.environ.get("AGNES_API_KEY", "")
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if not thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(AGNES_URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return None, f"LLM HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return None, str(e)
    try:
        msg = data["choices"][0]["message"]
        text = (msg.get("content") or "").strip()
        if not text:
            text = (msg.get("reasoning_content") or "").strip()
        return text, None
    except Exception as e:
        return None, f"Bad LLM response: {e}"
