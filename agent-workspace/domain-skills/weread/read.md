# WeRead — Auto Reading

Field-tested against weread.qq.com on 2026-05-06.
Requires WeChat login for reading features.

---

## Core Flow

```
Step 1: Check login status
    ├── Not logged in → Prompt user to scan QR code → Wait for login completion
    └── Logged in → Proceed to Step 2

Step 2: Check reading progress
    ├── No progress or finished → Pick first book from New Book ranking → Record status → Proceed to Step 3
    └── Unfinished book → Resume reading → Proceed to Step 3

Step 3: Auto reading (1 minute per session)
    ├── Every 3-5s scroll down 100px
    ├── See "Next Chapter" → Click, continue reading
    ├── See "Book Complete" + "Mark as Finished" → Click mark as finished → Record status as finished
    └── Time's up → Save progress, wait for next session
```

---

## URL Patterns

| Page | URL |
|------|-----|
| Home | `https://weread.qq.com/` |
| Rising | `https://weread.qq.com/web/category/rising` |
| Hot Search | `https://weread.qq.com/web/category/hot_search` |
| New Book | `https://weread.qq.com/web/category/newbook` |
| Book Detail | `https://weread.qq.com/web/bookDetail/{BOOK_ID}` |
| Reader | `https://weread.qq.com/web/reader/{BOOK_ID}k{CHAPTER_HASH}` |

### Reader URL Pattern

```
https://weread.qq.com/web/reader/{BOOK_ID}k{CHAPTER_HASH}
```

- `BOOK_ID` — unique book identifier (e.g., `ee0320b053b925ee0519857`)
- `CHAPTER_HASH` — chapter hash value (e.g., `08432c902c4084b6fbb18c9`)
- Directly accessing the URL jumps to the specified chapter

---

## Step 1: Login Flow

### Login Detection

```python
# Check if login is needed
login_needed = js("""
    const loginBtn = document.querySelector('[class*=login], [class*=Login]');
    const qrCode = document.querySelector('[class*=qrcode], [class*=QRCode]');
    return !!(loginBtn || qrCode);
""")
```

### Login Process

1. Navigate to `https://weread.qq.com/`
2. Page shows a QR code login prompt
3. User scans the QR code with the WeChat mobile app
4. Page auto-redirects to the home page after successful scan
5. Login state is persisted — no need to re-login

### Wait For Login Completion

```python
# Wait for login to complete
import time

def wait_for_login(timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        # Check if still on login page
        on_login = js("""
            const loginBtn = document.querySelector('[class*=login], [class*=Login]');
            return !!loginBtn;
        """)
        if not on_login:
            return True
        time.sleep(2)
    return False
```

---

## Step 2: Reading Progress Management

### progress.json Structure

```json
{
  "book": {
    "title": "book title",
    "author": "author",
    "url": "current chapter URL"
  },
  "progress": {
    "status": "reading | finished",
    "currentChapter": "chapter name",
    "completedChapters": ["list of chapters"],
    "lastReadTime": "2026-05-06"
  }
}
```

### Load Progress

```python
import json
import os

PROGRESS_FILE = "progress.json"

def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return None
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
```

### Save Progress

```python
def save_progress(book_title, author, url, chapter, completed_chapters, status="reading"):
    progress = {
        "book": {
            "title": book_title,
            "author": author,
            "url": url
        },
        "progress": {
            "status": status,
            "currentChapter": chapter,
            "completedChapters": completed_chapters,
            "lastReadTime": time.strftime("%Y-%m-%d")
        }
    }
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
```

### Check Reading Status

```python
def should_pick_new_book():
    progress = load_progress()
    if progress is None:
        return True  # never read before
    if progress["progress"]["status"] == "finished":
        return True  # already finished
    return False  # has an unfinished book
```

### Pick Book From New Book Ranking

```python
def pick_book_from_new_ranking():
    # Navigate to New Book ranking
    new_tab("https://weread.qq.com/web/category/newbook")
    wait_for_load()
    time.sleep(2)

    # Scroll to top
    js("window.scrollTo(0, 0)")
    time.sleep(1)

    # Click the first book
    first_book = js("""
        const allElements = document.querySelectorAll("[class*=title]");
        for (const el of allElements) {
            const text = el.textContent.trim();
            if (text.length > 3 && text.length < 50 && !text.includes("榜")) {
                const rect = el.getBoundingClientRect();
                return {
                    title: text,
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2
                };
            }
        }
        return null;
    """)

    if first_book:
        click_at_xy(first_book["x"], first_book["y"])
        wait_for_load()
        time.sleep(1)

    return first_book["title"] if first_book else None
```

---

## Step 3: Auto Reading

### Scroll Reading

```python
import random

def scroll_reading(duration=360):
    start_time = time.time()
    chapters_read = []

    while time.time() - start_time < duration:
        # Scroll down 100px
        js("window.scrollBy(0, 100)")

        # Random wait 3-5 seconds
        wait_time = random.uniform(3, 5)
        time.sleep(wait_time)

        # Check if "Next Chapter" button is visible
        next_chapter = find_next_chapter_button()
        if next_chapter and next_chapter["visible"]:
            # Record current chapter
            current = get_current_chapter()
            chapters_read.append(current)
            # Click next chapter
            click_at_xy(next_chapter["x"], next_chapter["y"])
            wait_for_load()
            time.sleep(1)
            continue

        # Check if "Book Complete" and "Mark as Finished"
        finished = check_book_finished()
        if finished:
            click_mark_finished()
            return chapters_read, True  # True = book finished

    return chapters_read, False  # False = time's up, book not finished
```

### Find Next Chapter Button

```python
def find_next_chapter_button():
    buttons = js("""
        const items = [];
        const elements = document.querySelectorAll("button, a, [role=button], [class*=next], [class*=Next]");
        elements.forEach(el => {
            const text = el.textContent.trim();
            if (text.includes("下一章")) {
                const rect = el.getBoundingClientRect();
                items.push({
                    text: text,
                    x: rect.x + rect.width/2,
                    y: rect.y + rect.height/2,
                    visible: rect.top < window.innerHeight && rect.bottom > 0
                });
            }
        });
        return items;
    """)
    return buttons[0] if buttons else None
```

### Get Current Chapter

```python
def get_current_chapter():
    return js("""
        const title = document.title;
        const parts = title.split(" - ");
        return parts.length > 1 ? parts[1] : "未知章节";
    """)
```

### Check Book Finished

```python
def check_book_finished():
    return js("""
        const elements = document.querySelectorAll("[class*=finish], [class*=complete], [class*=end]");
        for (const el of elements) {
            const text = el.textContent.trim();
            if (text.includes("全书完") || text.includes("已读完")) {
                return true;
            }
        }
        return false;
    """)
```

### Click Mark As Finished

```python
def click_mark_finished():
    button = js("""
        const elements = document.querySelectorAll("button, [role=button]");
        for (const el of elements) {
            const text = el.textContent.trim();
            if (text.includes("标记读完") || text.includes("标记已读")) {
                const rect = el.getBoundingClientRect();
                return {x: rect.x + rect.width/2, y: rect.y + rect.height/2};
            }
        }
        return null;
    """)
    if button:
        click_at_xy(button["x"], button["y"])
        wait_for_load()
        time.sleep(1)
```

---

## Gotchas

- **Persistent login** — No need to re-login after first scan, unless browser data is cleared.
- **"Next Chapter" button position** — The button is at the bottom of the page; scroll it into the viewport before clicking.
- **Scroll interval** — 3-5s random interval simulates real reading; scrolling too fast may trigger detection.
- **Chapter URL changes** — Each chapter has a unique URL hash; saving the full URL allows precise position restoration.
- **Book finished detection** — Some books may lack a "Book Complete" prompt; adjust detection logic as needed.
- **New Book ranking first pick** — Ranking order may change; always fetch the first book in real time.