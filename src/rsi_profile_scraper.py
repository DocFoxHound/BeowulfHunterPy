import re
import time
from urllib.parse import quote

import requests

# Regex patterns to find the first <img src="..."> after the titled sections
PROFILE_RE = re.compile(
    r'<span class="title">\s*Profile\s*</span>.*?<img\s+src="([^"]+)"',
    re.IGNORECASE | re.DOTALL
)
ORG_RE = re.compile(
    r'<span class="title">\s*Main\s+organization\s*</span>.*?<img\s+src="([^"]+)"',
    re.IGNORECASE | re.DOTALL
)


def _abs_url(u: str) -> str | None:
    if not u:
        return None
    return ("https://robertsspaceindustries.com" + u) if u.startswith("/") else u


def scrape_profile_images(handle: str, retry: int = 1, timeout: int = 7) -> tuple[None | str, None | str]:
    """Fetch the user's profile page and return (org_picture_url, victim_avatar_url).

    No caching or persistence. Optionally retries once on transient server errors.
    """
    h = (handle or "").strip()
    if not h:
        return (None, None)
    url = f"https://robertsspaceindustries.com/en/citizens/{quote(h, safe='')}"
    headers = {
        "User-Agent": "BeowulfHunter/1.0 (lightweight)",
        "Accept": "text/html,application/xhtml+xml",
    }

    def _try_once():
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
        except requests.RequestException:
            return (None, None, None)
        if resp.status_code == 404:
            return (404, None, None)
        if resp.status_code in (429, 500, 502, 503, 504):
            return (resp.status_code, None, None)
        if resp.status_code != 200:
            return (resp.status_code, None, None)
        html = resp.text or ""
        m1 = PROFILE_RE.search(html)
        m2 = ORG_RE.search(html)
        avatar = m1.group(1) if m1 else None
        orgimg = m2.group(1) if m2 else None
        return (200, _abs_url(orgimg), _abs_url(avatar))

    status, orgimg, avatar = _try_once()
    if status in (429, 500, 502, 503, 504) and retry > 0:
        try:
            time.sleep(0.4)
        except Exception:
            pass
        status, orgimg, avatar = _try_once()
    # For 404 or any failure, return None values; caller decides to proceed
    return (orgimg, avatar)
