# Find a Treg tool for a browser task

Use this on `treg.to` when a browser task needs data beyond the current page. Treg is OpenRouter for agent tools. Its catalog covers 4,200+ tools across search and SEO, company and people enrichment, social data, scraping, and image, video and voice generation. With a team connection, agents can also run shared APIs, CLIs and skills, or take actions such as publishing to a connected social account. A Browser Harness agent can search by task, compare providers and inspect the request and price before deciding whether to run a tool.

## Find a tool and quote the lookup

For a site-research task, suppose you have a company's domain and want to know what it would cost to look up its Domain Authority. This example uses the free public catalog and ends with the quote. Run this Python block inside `browser-harness`. To have the harness suggest the guide on visits to `treg.to`, place it in your agent workspace at `domain-skills/treg/catalog.md` and set `BH_DOMAIN_SKILLS=1`.

```python
import json
from urllib.parse import urlencode

base = "https://treg.to/catalog"
query = urlencode({"q": "domain authority"})
matches = json.loads(http_get(f"{base}/search?{query}"))["results"]
for item in matches:
    print(item["id"], item["provider_display"], item["name"])

# Read the Moz entry by its stable ID, even if the search order changes.
detail = json.loads(http_get(f"{base}/endpoints/moz.web.url.metrics"))
endpoint = detail["endpoint"]
print(endpoint["method"], endpoint["input"]["body"]["targets"])
print(endpoint["cost"]["usd"], endpoint["cost"]["unit"], endpoint["cost"]["note"])
print(endpoint["docs_url"])
```

Moz accepts an array of targets. Its entry quotes a quota row per target for the basic request and explains which options consume extra rows. Read the current cost note when quoting a batch. The detail response also has an `example_response` that shows the output shape. A live score for the company requires a separate authenticated call.

For other tasks, change the query first, then choose an ID from those results. Queries tested in the harness included `company enrichment`, `social profiles` and `generate images`. Each returns a different set of providers. Use the selected endpoint's own input and cost fields.

## Cross-check what the user sees

For Moz, open the provider page and expand the group containing the exact endpoint ID. The visible entry pairs a plain-language title with its billing terms. The endpoint ID is rendered as text in a `code` element.

```python
new_tab("https://treg.to/tools/moz")
assert wait_for_element("#tools details > summary")
row = js("""(() => {
  const code = [...document.querySelectorAll('#tools li code')]
    .find(node => node.textContent.trim() === 'moz.web.url.metrics');
  if (!code) return null;
  code.closest('details').open = true;
  return code.closest('li').innerText.trim();
})()""")
close_tab()
if row is None:
    raise RuntimeError("The Moz endpoint is missing from the provider page")
print(row)
```

For live execution, use the chosen endpoint’s HTTP method at `https://treg.to/call/{endpoint_id}` and send the team token in `X-Treg-Token` from the host process. Keep credentials out of page JavaScript. Treg supplies the provider credential server-side. Account actions require a connection with the appropriate permissions. Calls using Treg’s provider accounts can spend the team’s prepaid balance. [Treg API reference](https://treg.to/docs).

Field-tested while logged out on November 24, 2026 with Browser Harness 0.1.13 and local Chrome.
