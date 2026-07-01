# Meta Business Suite — Page Health & Content Moderation

Field-tested against business.facebook.com and facebook.com settings pages.
Covers: page recommendation suspensions, violating content deletion, and Instagram linking.

## URL patterns

```
# Dashboard for a specific Facebook Page
https://business.facebook.com/latest/home?asset_id=<ASSET_ID>

# Published content list (posts + reels)
https://business.facebook.com/latest/posts/published_posts/?asset_id=<ASSET_ID>

# Page quality / account status (facebook.com, not business.facebook.com)
https://www.facebook.com/settings/?tab=profile_quality

# Recommendations suspension detail
https://www.facebook.com/settings/?tab=profile_recommendations

# Instagram linking settings
https://business.facebook.com/latest/settings/instagram
```

## Finding the asset_id

The `asset_id` is the numeric page ID embedded in every Meta Business Suite URL.
Never guess it — navigate to the page in MBS first and read it from the URL:

```python
goto_url("https://business.facebook.com/latest/home")
wait_for_load()
wait(2)
url = page_info()["url"]
# url will contain ?asset_id=<15-digit-number>
import re
asset_id = re.search(r'asset_id=(\d+)', url).group(1)
```

Read carefully — misreading one digit silently loads a different page with no error.

## Checking page health

```python
goto_url("https://www.facebook.com/settings/?tab=profile_quality")
wait_for_load()
wait(2)
screenshot = capture_screenshot()
# Look for: recommendation status, Community Standards violations, account restrictions
```

Navigate directly to recommendation detail:
```python
goto_url("https://www.facebook.com/settings/?tab=profile_recommendations")
wait_for_load()
wait(2)
```

### Interpreting recommendation status

- **"Your recommendations are suspended"** — page is not being surfaced to new people
- **Step 1 / 2 / 3 indicator** — internal review stage. Step 3 = process exhausted; no appeal path; must fix content.
- **No Community Standards violations + Recommendations suspended** = Recommendations Guidelines violation (stricter than Community Standards)

Content that triggers Recommendations Guidelines (not Community Standards):
- Needle injection / medical procedure videos (Botox, fillers, etc.)
- Before/after cosmetic procedure content
- Health condition targeting
- Weight loss supplement claims

The suspension typically appears ~24h after the violating content is posted.

## Finding and deleting violating content

Navigate to the published content list for the page:
```python
goto_url(f"https://business.facebook.com/latest/posts/published_posts/?asset_id={asset_id}")
wait_for_load()
wait(3)  # React SPA needs extra time after readyState=complete
```

Sort/filter by date — look for posts 1-2 days before the suspension date.

### Deleting a post or reel (coordinate-click pattern)

Meta Business Suite uses heavy React with obfuscated class names. Stable selectors don't exist.
Use screenshot then coordinate click for all post-card interactions:

```python
# Step 1: Screenshot to find the "..." overflow button on the target post card
screenshot = capture_screenshot()

# Step 2: Click "..."
click_at_xy(x_dots, y_dots)
wait(0.5)

# Step 3: Screenshot the opened context menu — find "Manage post" or "Manage reel"
screenshot = capture_screenshot()
click_at_xy(x_manage, y_manage)
wait(0.5)

# Step 4: Screenshot the submenu — find "Delete post" / "Delete reel"
screenshot = capture_screenshot()
click_at_xy(x_delete, y_delete)
wait(0.5)

# Step 5: Screenshot the confirmation dialog — find "Delete" confirm button
screenshot = capture_screenshot()
click_at_xy(x_confirm, y_confirm)
wait(1)

# Step 6: Verify
screenshot = capture_screenshot()
# Success: "Post moved to trash" (Facebook) or "Your post has been deleted" (Instagram)
```

**Critical gotcha**: Never reuse element refs or coordinates between menu steps.
Each click re-renders the dropdown DOM. Always re-screenshot before the next click.

### Crossposted content

If content was published to both Facebook and Instagram, it appears twice in the list:
- Facebook post (earlier timestamp, e.g. 10:11am)
- Instagram reel (later timestamp, e.g. 10:56am, same title)

Delete both entries. Instagram deletion is immediate (no trash/recovery).

## Instagram linking

```python
goto_url(f"https://business.facebook.com/latest/settings/instagram?asset_id={asset_id}")
wait_for_load()
wait(2)
```

**Access requirement**: The logged-in Meta account must have "Full control" admin role on the Business Portfolio.
If it shows: "Additional access is required to connect — You can ask someone who already has full control to edit your assigned access."
Stop. The portfolio owner must grant full admin access or do the linking themselves.
There is no workaround for this permission check.

## Session and navigation gotchas

- **MBS is a React SPA** — wait_for_load() fires before content cards render. Always add wait(2)-wait(3) after navigation, then screenshot to confirm hydration.
- **Asset ID in wrong tab** — If an alert in Meta Business Suite opens a new facebook.com tab (e.g. "Fix your Page"), read the URL in that new tab. The asset_id stays in the MBS tab URL, not the settings tab.
- **Alert banners** — The "Your Page is no longer being recommended" banner links to facebook.com/settings/?tab=profile_quality or profile_recommendations via "See details". Follow it — the full suspension detail only appears there.
- **Content list pagination** — If the target post is not visible, scroll down or use date filters. Posts are sorted newest-first by default.
- **asset_id precision** — IDs are ~15 digits. A single transposition loads a different page silently. Zoom into the URL bar to read it accurately before embedding in a goto_url call.
