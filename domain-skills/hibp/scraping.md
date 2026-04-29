# Have I Been Pwned — Scraping & Data Extraction

`https://haveibeenpwned.com` / `https://api.pwnedpasswords.com` — public data breach database and password exposure checker. **Never use the browser.** All useful data is available via `http_get`. The Pwned Passwords API is completely free, no auth. The breach account-lookup endpoints require a paid API key.

## Do this first

**Use the Pwned Passwords range API for password checking — free, no auth, privacy-preserving k-anonymity.**

```python
import hashlib, json
from helpers import http_get

def check_password_pwned(password: str) -> int:
    """Returns how many times this password has appeared in known breaches. 0 = not found."""
    sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    body = http_get(f'https://api.pwnedpasswords.com/range/{prefix}')
    for line in body.splitlines():
        h, count = line.split(':')
        if h == suffix:
            return int(count)
    return 0

print(check_password_pwned('password'))               # 52256179
print(check_password_pwned('correct horse battery staple'))  # 387
print(check_password_pwned('very_unique_str_xyz9283'))       # 0
```

Use `http_get` on `https://haveibeenpwned.com/api/v3/breaches` for the full breach list — one call, fully parsed JSON, no auth.

**Never use the browser.** All pages are just wrappers around the same API data.

## The k-anonymity model (Pwned Passwords)

You never send the full password or its hash to the API. The flow:

1. SHA1-hash the password (or NTLM-hash for Windows credential checking)
2. Send only the **first 5 hex characters** to `api.pwnedpasswords.com/range/{prefix}`
3. The API returns ~1900 matching hash suffixes + counts (all hashes in the database sharing that prefix)
4. Search the response locally for your **remaining 35 characters** — no plaintext ever leaves your machine

```python
import hashlib

password = 'password'
sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
# SHA1 = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
prefix = sha1[:5]   # '5BAA6'   — sent to API
suffix = sha1[5:]   # '1E4C9B93F3F0682250B6CF8331B7EE68FD8'  — matched locally

# API response lines look like:
# 1E4C9B93F3F0682250B6CF8331B7EE68FD8:52256179
# (suffix:count)
```

The response is plain text, `\r\n` line endings, ~1,900–2,000 lines per prefix, ~75 KB. CDN-cached for up to 31 days per prefix.

## Common workflows

### Check a single password

```python
import hashlib
from helpers import http_get

def check_password_pwned(password: str) -> int:
    sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    body = http_get(f'https://api.pwnedpasswords.com/range/{prefix}')
    for line in body.splitlines():
        h, count = line.split(':')
        if h == suffix:
            return int(count)
    return 0

count = check_password_pwned('letmein')
if count > 0:
    print(f'Compromised! Seen {count:,} times in breaches.')
else:
    print('Not found in known breaches.')
# Confirmed output: Compromised! Seen 1,406,394 times in breaches.
```

### Check multiple passwords in parallel

```python
import hashlib
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

def check_password_pwned(password: str) -> dict:
    sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    body = http_get(f'https://api.pwnedpasswords.com/range/{prefix}')
    for line in body.splitlines():
        h, count = line.split(':')
        if h == suffix:
            return {'password': password, 'count': int(count)}
    return {'password': password, 'count': 0}

passwords = ['password', 'letmein', 'correct horse battery staple', 'hunter2']
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(check_password_pwned, passwords))

for r in results:
    status = f"seen {r['count']:,}x" if r['count'] else "not found"
    print(f"{r['password']!r}: {status}")
# Confirmed working; safe to use max_workers=5–10 — endpoint is CDN-cached, not rate-limited
```

### All breaches (full list)

```python
import json
from helpers import http_get

breaches = json.loads(http_get('https://haveibeenpwned.com/api/v3/breaches'))
print(f'Total breaches: {len(breaches)}')   # 974 (confirmed 2026-04-18)

# Key fields per breach object:
# Name, Title, Domain, BreachDate, AddedDate, ModifiedDate,
# PwnCount, Description (HTML), LogoPath, DataClasses (list),
# IsVerified, IsFabricated, IsSensitive, IsRetired, IsSpamList,
# IsMalware, IsSubscriptionFree, IsStealerLog, Attribution, DisclosureUrl

# Find largest breaches
top5 = sorted(breaches, key=lambda b: b['PwnCount'], reverse=True)[:5]
for b in top5:
    print(f"{b['Name']}: {b['PwnCount']:,} accounts ({b['BreachDate']})")
# SynthientCredentialStuffingThreatData: 1,957,476,021 accounts
# Collection1: 772,904,991 accounts
# VerificationsIO: 763,117,241 accounts
# OnlinerSpambot: 711,477,622 accounts
# PDL: 622,161,052 accounts
```

### Filter breaches by domain

```python
import json
from helpers import http_get

result = json.loads(http_get('https://haveibeenpwned.com/api/v3/breaches?domain=adobe.com'))
for b in result:
    print(b['Name'], b['PwnCount'])
# Adobe 152445165
```

### Single breach by name

```python
import json
from helpers import http_get

adobe = json.loads(http_get('https://haveibeenpwned.com/api/v3/breach/Adobe'))
print(adobe['Name'], adobe['PwnCount'], adobe['BreachDate'])
print(adobe['DataClasses'])
# Adobe 152445165 2013-10-04
# ['Email addresses', 'Password hints', 'Passwords', 'Usernames']

# 404 for unknown breach — raises HTTPError, not a JSON error
try:
    http_get('https://haveibeenpwned.com/api/v3/breach/NonExistentXYZ')
except Exception as e:
    print(e)   # HTTP Error 404: Not Found
    # curl returns plain text "Not found" body (application/json content-type despite being plain text)
```

### Latest breach added

```python
import json
from helpers import http_get

latest = json.loads(http_get('https://haveibeenpwned.com/api/v3/latestbreach'))
print(latest['Name'], latest['BreachDate'])
# Amtrak 2026-04-03  (confirmed 2026-04-18)
```

### All data classes (taxonomy of what was leaked)

```python
import json
from helpers import http_get

dcs = json.loads(http_get('https://haveibeenpwned.com/api/v3/dataclasses'))
print(f'Total categories: {len(dcs)}')   # 157
print(dcs[:5])
# ['Account balances', 'Address book contacts', 'Age groups', 'Ages', 'AI prompts']
```

### Parallel fetch of specific breaches

```python
import json
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

names = ['Adobe', 'LinkedIn', 'Yahoo', 'Dropbox', 'MySpace']

def fetch_breach(name):
    data = json.loads(http_get(f'https://haveibeenpwned.com/api/v3/breach/{name}'))
    return {'name': data['Name'], 'pwn_count': data['PwnCount'], 'date': data['BreachDate']}

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_breach, names))

for r in results:
    print(f"{r['name']}: {r['pwn_count']:,} ({r['date']})")
# Adobe: 152,445,165 (2013-10-04)
# LinkedIn: 164,611,595 (2012-05-05)
# Yahoo: 453,427 (2012-07-11)
# Dropbox: 68,648,009 (2012-07-01)
# MySpace: 359,420,698 (2008-07-01)
# Time: 0.26s (all 5 in parallel)
```

### Account breach lookup (requires paid API key)

This endpoint is **not freely available** — requires a purchased API key from `haveibeenpwned.com/API/Key`.

```python
import json
from helpers import http_get

API_KEY = 'your-hibp-api-key'

# All breaches for an email address
breaches = json.loads(http_get(
    'https://haveibeenpwned.com/api/v3/breachedaccount/user@example.com',
    headers={'hibp-api-key': API_KEY}
))
# Returns list of breach objects (same structure as /breaches, but truncated)
# If no breaches found: raises HTTPError 404 (not an empty list — actual 404)

# Pastes (also requires API key)
pastes = json.loads(http_get(
    'https://haveibeenpwned.com/api/v3/pasteaccount/user@example.com',
    headers={'hibp-api-key': API_KEY}
))
# Each paste: Source, Id, Title, Date, EmailCount
```

Without a key: HTTP 401 `{ "statusCode": 401, "message": "Access denied due to improperly formed hibp-api-key." }`

## API reference

### Pwned Passwords

| Endpoint | Auth | Notes |
|---|---|---|
| `GET api.pwnedpasswords.com/range/{prefix}` | None | prefix = first 5 chars of SHA1 (uppercase hex) |
| `GET api.pwnedpasswords.com/range/{prefix}?mode=ntlm` | None | NTLM mode for Windows credential hashes; 27-char suffixes instead of 35 |

Response format: plain text, one line per matching hash, `SUFFIX:COUNT\r\n`. ~1,900 lines per prefix.

Cache: CDN-cached up to 31 days (`cache-control: public, max-age=2678400`). Repeated calls for the same prefix are free and instant.

### HIBP REST API v3 (base: `https://haveibeenpwned.com/api/v3`)

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /breaches` | None | All 974 breaches |
| `GET /breaches?domain={domain}` | None | Filter by domain |
| `GET /breach/{name}` | None | Single breach by Name field |
| `GET /latestbreach` | None | Most recently added breach |
| `GET /dataclasses` | None | 157 data category strings |
| `GET /breachedaccount/{email}` | API key | Paid only |
| `GET /pasteaccount/{email}` | API key | Paid only |

API key header: `hibp-api-key: {key}`. No version header required; v3 is the current and only active version.

### Breach object fields

| Field | Type | Notes |
|---|---|---|
| `Name` | string | Unique ID used in URLs (e.g., `"Adobe"`) |
| `Title` | string | Display name |
| `Domain` | string | Primary domain (may be empty string) |
| `BreachDate` | string | `YYYY-MM-DD` |
| `AddedDate` | string | ISO 8601 datetime |
| `ModifiedDate` | string | ISO 8601 datetime |
| `PwnCount` | int | Total accounts exposed |
| `Description` | string | HTML — contains `<a>` tags, `<em>`, etc. |
| `LogoPath` | string | `https://logos.haveibeenpwned.com/{Name}.png` |
| `DataClasses` | list[str] | Types of data exposed |
| `IsVerified` | bool | Confirmed authentic breach |
| `IsFabricated` | bool | Known to be fake/fabricated |
| `IsSensitive` | bool | Contains sensitive info (adult sites, etc.) |
| `IsRetired` | bool | No longer actively indexed |
| `IsSpamList` | bool | Email spam list rather than a breach |
| `IsMalware` | bool | Sourced from malware/info-stealer |
| `IsStealerLog` | bool | Credential stealer logs specifically |
| `IsSubscriptionFree` | bool | Whether free subscribers can see it |
| `Attribution` | string\|null | Source attribution if credited |
| `DisclosureUrl` | string\|null | URL of original disclosure |

## Gotchas

- **Never use the browser.** The website is entirely API-driven. `http_get` is sufficient for all public data.

- **Pwned Passwords response has `\r\n` line endings.** Use `.splitlines()` (not `.split('\n')`) to parse — `splitlines()` handles both `\r\n` and `\n` transparently. If you split on `\n`, each suffix will have a trailing `\r` and the comparison `h == suffix` will always be False.

- **Password and hash must be uppercased.** `hashlib.sha1(...).hexdigest()` returns lowercase. Call `.upper()` before splitting into prefix/suffix. The API returns uppercase suffixes.

- **404 for missing breach is a raised HTTPError, not a JSON error body.** `http_get` will raise `urllib.error.HTTPError` on 404. The response body is the string `"Not found"` with `content-type: application/json` — misleadingly labeled but not valid JSON.

- **404 for missing `breachedaccount` means no breaches found, not an error.** When an email has never appeared in a breach, the API returns HTTP 404, not an empty list `[]`. When it has breaches, it returns HTTP 200 with the list. This is the opposite of what you'd expect.

- **`Description` field contains raw HTML.** Strip tags with `re.sub(r'<[^>]+>', '', b['Description'])` if you need plain text.

- **Pwned Passwords is CDN-cached for 31 days** (`cache-control: public, max-age=2678400`, `age` can be over 1.5 million seconds). This is intentional — password hash prefixes don't change often. Parallel requests for different prefixes are fast and safe; there's no meaningful rate limit on this endpoint.

- **HIBP breach endpoints cache for 5 minutes** (`cache-control: public, max-age=300`). Rapid sequential calls to `/breach/Adobe` 10× all returned HTTP 200 without throttling. No rate limit headers observed. Still, add `time.sleep(1)` between bulk breach-name lookups to be a good citizen.

- **NTLM mode suffix length differs.** `?mode=ntlm` returns 27-char suffixes (NTLM is 32 hex chars; 32−5=27) vs. 35-char for SHA1 (40−5=35). NTLM mode is only relevant for checking Windows NTLM credential hashes directly.

- **`CORS: access-control-allow-origin: *`** on all endpoints — can be called from browser JS too, no proxy needed for client-side apps.

- **`logoPath` URLs are reliable.** `https://logos.haveibeenpwned.com/{Name}.png` — these are stable CDN URLs, not the web page logo paths.

- **The `domain` filter in `/breaches?domain=` is exact-match.** `adobe.com` matches Adobe's breach; `adobe` alone returns nothing.
