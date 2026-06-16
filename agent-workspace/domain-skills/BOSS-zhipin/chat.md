# BOSS直聘 — Chat & Messaging

Field-tested against zhipin.com on 2026-05-01.
Login required. Messages are loaded via WebSocket + REST API.

**IMPORTANT**: Never send messages without the user's explicit permission. This skill documents the read/retrieval mechanics only.

---

## Architecture

BOSS直聘 uses a hybrid messaging architecture:

- **Conversation list** — loaded via WebSocket (`ws6.zhipin.com`) on page load, NOT via REST
- **Message history** — REST API `/wapi/zpchat/geek/historyMsg`
- **Real-time messages** — WebSocket push from `ws6.zhipin.com`

---

## Chat Page (`/web/geek/chat`)

### Page Structure

```
Left panel:
  .chat-user.v2                  — filter bar + search input
    .label-list > ul
      li.selected                — active filter tab
      li                         — "未读(N)" shows count badge in <i>
      li > .ui-dropmenu          — "更多" dropdown (仅沟通/有交换/有面试/不感兴趣)
      li.filter-item             — "AI筛选" dropdown with natural language input
    .boss-search-input           — contact search (placeholder: "搜索30天内的联系人")
  .user-list
    .user-list-content
      .friend-content-warp
        .friend-content           — conversation item (click to open)
          .friend-content.friend-top  — pinned/top conversation

Right panel (visible after clicking a conversation):
  .chat-record                   — message history container
    .message-item.item-myself    — message sent by user
      .item-time > .time         — timestamp
      .message-content > .text   — message body
      .message-status.status-read — read receipt ("已读")
    .message-item.item-friend    — message from recruiter
      .item-time > .time
      .message-content > .text
```

### Filter Tabs

Top-level tabs (`.chat-user.v2 .label-list li`):

| Tab | Description | Class |
|-----|-------------|-------|
| 全部 | All conversations (default) | `li.selected` when active |
| 未读(N) | Unread conversations, badge shows count | `<i>` in label shows count |
| 新招呼 | New greetings from recruiters | Badge indicator via `<i class="badge">` |
| 更多 ▾ | Dropdown with extra filters | `.ui-dropmenu` |

"更多" dropdown (`.more-label li`):

| Option | Description |
|--------|-------------|
| 仅沟通 | Conversations with messages exchanged |
| 有交换 | Conversations with file/contact exchange |
| 有面试 | Conversations with interview invitations |
| 不感兴趣 | Conversations marked "not interested" |

"AI筛选" (`.filter-item > .ui-dropmenu`): Opens a panel with a `<textarea>` for natural language filter input (e.g. "后端开发 上海 高薪").

#### Clicking Filter Tabs

```python
def click_filter(label_text):
    """Click a filter tab by its text label."""
    js(f"""
    (function() {{
        var labels = document.querySelectorAll('.chat-user .label-list li .label-name');
        for (var i = 0; i < labels.length; i++) {{
            if (labels[i].textContent.trim().indexOf('{label_text}') === 0) {{
                labels[i].closest('li').click();
                return true;
            }}
        }}
        return false;
    }})()
    """)
    wait(1)

def click_more_filter(label_text):
    """Click an option inside the '更多' dropdown."""
    # First open the dropdown
    click_filter("更多")
    wait(0.5)
    js(f"""
    (function() {{
        var items = document.querySelectorAll('.more-label li span');
        for (var i = 0; i < items.length; i++) {{
            if (items[i].textContent.trim() === '{label_text}') {{
                items[i].closest('li').click();
                return true;
            }}
        }}
        return false;
    }})()
    """)
    wait(1)
```

### Conversation Item (DOM)

Each `.friend-content` contains:
- Timestamp (e.g. "04月13日", "昨天")
- Recruiter name (e.g. "刘女士")
- Company name (e.g. "Soul App")
- Recruiter title (e.g. "招聘专家")
- Last message preview
- Unread count badge (numeric)

### Read Conversation List (DOM)

```python
def get_conversations():
    raw = js("""
    (function() {
        var items = document.querySelectorAll('.friend-content');
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var text = el.textContent;
            var badge = el.querySelector('[class*="badge"], [class*="unread"], [class*="count"]');
            var unread = badge ? parseInt(badge.textContent) || 0 : 0;
            results.push({
                text: text.trim().substring(0, 150),
                is_top: el.classList.contains('friend-top'),
                unread: unread
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

### Open a Conversation

Click the `.friend-content` element:

```python
def open_conversation(index=0):
    js(f"document.querySelectorAll('.friend-content')[{index}].click()")
    wait(2)
```

---

## API: Message History

```
GET /wapi/zpchat/geek/historyMsg?bossId={bossId}&maxMsgId=0&c=20&page=1&src=0
```

### Parameters

| Param | Description |
|-------|-------------|
| `bossId` | Recruiter ID from conversation (format: `9c833990a839f1251Hx92du5GA~~`) |
| `maxMsgId` | Pagination cursor. `0` for first page, then use the smallest `mid` from previous page |
| `c` | Count per page (default 20) |
| `page` | Page number |
| `src` | Source (0 for web) |

The `bossId` can be found in performance entries after clicking a conversation, or extracted from the WebSocket connection data on page load.

### Response (`zpData.messages[]`)

Each message has:

```python
{
    "mid": 337069469603329,              # message ID (numeric, for pagination)
    "type": 3,                           # 3=regular message, 4=system message
    "received": true,                    # whether you received it
    "body": {
        "type": 1,                       # 1=text, 8=job card
        "text": "message text here...",  # present when body.type=1
        "jobDesc": { ... }               # present when body.type=8
    },
    "from": {
        "uid": 502838021,                # sender user ID
        "name": "张女士",
        "avatar": "https://img.bosszhipin.com/..."
    },
    "to": {
        "uid": 680839465                 # recipient user ID
    }
}
```

### Message Body Types

| `body.type` | Meaning | Fields |
|-------------|---------|--------|
| `1` | Plain text | `body.text` |
| `8` | Job description card | `body.jobDesc` (title, salary, company, boss, city, experience, education), `body.headTitle` |
| `16` | System notification | (file received, etc.) |

### Job Card Messages (`body.type=8`)

```python
{
    "body": {
        "type": 8,
        "headTitle": "您正在与Boss刘女士直接沟通如下职位",
        "jobDesc": {
            "title": "AI Agent工程师",
            "salary": "35-60K·16薪",         # REAL salary — not font-encoded
            "company": "Soul App",
            "city": "上海 浦东新区 金桥",
            "experience": "经验不限",
            "education": "硕士",
            "stage": "D轮及以上",
            "positionCategory": "算法工程师",
            "boss": {
                "uid": 3872648,
                "name": "刘女士",
                "avatar": "https://img.bosszhipin.com/..."
            },
            "bossTitle": "招聘专家",
            "jobId": 509933581
        }
    }
}
```

### Fetch Message History

```python
def fetch_messages(boss_id, page=1, count=20):
    raw = js(f"""
    (async function() {{
        var url = '/wapi/zpchat/geek/historyMsg?bossId={boss_id}&maxMsgId=0&c={count}&page={page}&src=0';
        var r = await fetch(url);
        var d = await r.json();
        if (d.code !== 0 || !d.zpData) {{
            return JSON.stringify({{code: d.code, hasMore: false, count: 0, messages: [], error: d.msg || 'API error'}});
        }}
        var msgs = d.zpData.messages || [];
        return JSON.stringify({{
            code: d.code,
            hasMore: d.zpData.hasMore,
            count: msgs.length,
            messages: msgs.map(function(m) {{
                var b = m.body || {{}};
                return {{
                    mid: m.mid,
                    type: m.type,
                    body_type: b.type,
                    text: b.text || null,
                    job: b.jobDesc ? {{
                        title: b.jobDesc.title,
                        salary: b.jobDesc.salary,
                        company: b.jobDesc.company,
                        city: b.jobDesc.city,
                        boss_name: (b.jobDesc.boss || {{}}).name,
                        job_id: b.jobDesc.jobId
                    }} : null,
                    from_name: (m.from || {{}}).name,
                    from_uid: (m.from || {{}}).uid,
                    received: m.received
                }};
            }})
        }});
    }})()
    """)
    return json.loads(raw)
```

### Pagination

Use `maxMsgId` (not `page`) for efficient pagination. Set `maxMsgId` to the smallest `mid` from the previous batch:

```python
def fetch_all_messages(boss_id):
    all_msgs = []
    max_msg_id = 0
    while True:
        raw = js(f"""
        (async function() {{
            var r = await fetch('/wapi/zpchat/geek/historyMsg?bossId={boss_id}&maxMsgId={max_msg_id}&c=20&page=1&src=0');
            var d = await r.json();
            if (d.code !== 0 || !d.zpData) {{
                return JSON.stringify({{messages: [], hasMore: false}});
            }}
            return JSON.stringify(d.zpData);
        }})()
        """)
        data = json.loads(raw)
        msgs = data.get("messages", [])
        if not msgs:
            break
        all_msgs.extend(msgs)
        if not data.get("hasMore"):
            break
        max_msg_id = msgs[-1]["mid"]  # smallest mid
        wait(0.5)
    return all_msgs
```

---

## Messages Read from DOM (after opening a conversation)

```python
def read_messages_dom():
    raw = js("""
    (function() {
        var items = document.querySelectorAll('.message-item');
        var results = [];
        for (var i = 0; i < items.length; i++) {
            var el = items[i];
            var timeEl = el.querySelector('.time');
            var textEl = el.querySelector('.text');
            var statusEl = el.querySelector('.message-status');
            results.push({
                from_me: el.classList.contains('item-myself'),
                time: timeEl ? timeEl.textContent.trim() : '',
                text: textEl ? textEl.textContent.trim().substring(0, 300) : '',
                status: statusEl ? statusEl.textContent.trim() : ''
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

---

## Extracting bossId from the Page

The `bossId` is embedded in WebSocket payloads and API calls. To discover it after clicking a conversation:

```python
def get_current_boss_id():
    return js("""
    (function() {
        var entries = performance.getEntriesByType('resource');
        for (var i = entries.length - 1; i >= 0; i--) {
            var url = entries[i].name;
            if (url.indexOf('/wapi/zpchat/geek/historyMsg') === -1) continue;
            var match = url.match(/bossId=([^&]+)/);
            if (match) return match[1];
        }
        return null;
    })()
    """)
```

---

## Navigating from Job Detail to Chat

Opening a job detail page and clicking "立即沟通" initiates a conversation with that job's recruiter. The API needed:

1. Navigate to `/job_detail/{JOB_ID}.html`
2. Find the chat button (`.btn-startchat`) element
3. The button's `href` or click handler contains the `bossId` and `securityId`

---

## Gotchas

- **Conversation list is WebSocket-loaded** — no REST API for the list. Use DOM extraction (`.friend-content`) or monitor WebSocket frames to get the initial conversation list.
- **Message history uses `bossId`, not `encryptBossId`** — the `bossId` format is `"9c833990a839f1251Hx92du5GA~~"` (trailing `~~`), different from the job list's `encryptBossId`.
- **`maxMsgId` pagination** — use the smallest `mid` from the current batch for the next page, not `page` parameter.
- **Job cards in messages have real salary** — `body.jobDesc.salary` returns `"35-60K·16薪"` unlike the DOM which uses font-encoded digits.
- **System messages (type=4)** — these include read receipts, file transfers ("对方已同意，您的附件简历已发送给对方"), and competitor analysis cards.
- **After clicking a conversation, `wait(2)`** — the message history needs time to render.
- **`item-myself` vs `item-friend`** — user messages have `item-myself` class, recruiter messages have `item-friend`.
- **Contact search input** — `.boss-search-input` searches within 30 days of contacts, not a general message compose box.
