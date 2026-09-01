"""
Shared Mastodon request helper for Edith automation on GitHub Actions.
Token comes from MASTODON_TOKEN env (GitHub Secret), not hardcoded.
"""
import os, time, random, requests

MASTODON_BASE = "https://mastodon.social"
MAX_RETRIES = 4
BASE_DELAY = 2.0

def get_token():
    return os.environ.get("MASTODON_TOKEN", "")

def headers():
    return {"Authorization": "Bearer " + get_token()}

def mastodon_request(method, url, data=None, params=None, timeout=20):
    """Retry/backoff wrapper. Returns final requests.Response."""
    last_exc = None
    res = None
    for attempt in range(MAX_RETRIES):
        try:
            res = requests.request(method, url, headers=headers(), data=data,
                                   params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            time.sleep(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1))
            continue
        if res.status_code == 429:
            retry_after = res.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else BASE_DELAY * (2 ** attempt)
            time.sleep(delay + random.uniform(0, 1))
            continue
        if res.status_code >= 500:
            time.sleep(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1))
            continue
        return res
    if last_exc:
        raise last_exc
    return res

def post(text, visibility="public", language="en", reply_to=None):
    data = {"status": text[:500], "visibility": visibility, "language": language}
    if reply_to:
        data["in_reply_to_id"] = reply_to
    res = mastodon_request("POST", f"{MASTODON_BASE}/api/v1/statuses", data=data, timeout=20)
    if res.status_code != 200:
        return None, f"Post failed: {res.status_code} - {res.text[:200]}"
    posted = res.json()
    post_id = posted.get("id")
    check = mastodon_request("GET", f"{MASTODON_BASE}/api/v1/statuses/{post_id}", timeout=15)
    if check.status_code != 200:
        return None, "Post created but could not be re-fetched to confirm"
    if reply_to and check.json().get("in_reply_to_id") != reply_to:
        return None, "Post created but not correctly threaded"
    return check.json().get("url"), None

def me():
    return mastodon_request("GET", f"{MASTODON_BASE}/api/v1/accounts/verify_credentials", timeout=20).json()
