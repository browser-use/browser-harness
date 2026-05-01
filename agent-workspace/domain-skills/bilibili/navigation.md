# Bilibili — Site Navigation & Structure

Field-tested against bilibili.com on 2026-05-01.
Requires login for personal-space features; public pages are accessible without auth.

---

## URL Patterns

### Core pages

| Page | URL |
|------|-----|
| Home (recommended feed) | `https://www.bilibili.com/` |
| Dynamics (following feed) | `https://t.bilibili.com/` |
| Personal space | `https://space.bilibili.com/{UID}` |
| Watch history | `https://www.bilibili.com/account/history` |
| Watch later | `https://www.bilibili.com/watchlater/#/list` |
| Messages | `https://message.bilibili.com/` |
| Search | `https://search.bilibili.com/all?keyword={QUERY}` |

### Personal space sub-pages

| Page | URL |
|------|-----|
| Home (videos + favorites) | `https://space.bilibili.com/{UID}` |
| Dynamics (user activity) | `https://space.bilibili.com/{UID}/dynamic` |
| Uploads | `https://space.bilibili.com/{UID}/upload` |
| Collections & series | `https://space.bilibili.com/{UID}/lists` |
| Favorites | `https://space.bilibili.com/{UID}/favlist` |
| Bangumi tracking | `https://space.bilibili.com/{UID}/bangumi` |
| Settings | `https://space.bilibili.com/{UID}/settings` |

### Discovery

| Page | URL |
|------|-----|
| Popular / Hot | `https://www.bilibili.com/v/popular/all` |
| Weekly must-watch | `https://www.bilibili.com/v/popular/weekly?num={ISSUE}` |
| All-time classics | `https://www.bilibili.com/v/popular/all` (入站必刷 tab) |
| Ranking (all) | `https://www.bilibili.com/v/popular/rank/all` |
| Topics | `https://www.bilibili.com/v/topic/` |

### Video page

| Aspect | Pattern |
|--------|---------|
| Watch URL | `https://www.bilibili.com/video/{BV_ID}` |
| BV format | `BV` prefix + 10 alphanumeric chars, e.g. `BV1HeRKBdEoX` |
| AV format (legacy) | `av` + digits, e.g. `av170001` (still resolves) |

### Content platforms

| Page | URL |
|------|-----|
| Anime | `https://www.bilibili.com/anime/` |
| Movie | `https://www.bilibili.com/movie/` |
| TV series | `https://www.bilibili.com/tv/` |
| Documentary | `https://www.bilibili.com/documentary/` |
| Variety show | `https://www.bilibili.com/variety/` |
| Chinese animation | `https://www.bilibili.com/guochuang/` |
| Read (articles/blogs) | `https://www.bilibili.com/read/home` |
| Audio / Music | `https://www.bilibili.com/audio/home` |
| Courses (课堂) | `https://www.bilibili.com/cheese/` |
| Live | `https://live.bilibili.com/` |
| Game center | `https://game.bilibili.com/platform` |
| Manga (漫画) | `https://manga.bilibili.com/` |
| Mall (会员购) | `https://show.bilibili.com/platform/home.html` |
| Esports / Matches | `https://www.bilibili.com/match/home/` |

### Creator

| Page | URL |
|------|-----|
| Creator center | `https://member.bilibili.com/platform/home` |
| Upload video | `https://member.bilibili.com/platform/upload/video/frame` |

### Other

| Page | URL |
|------|-----|
| Premium (大会员) | `https://account.bilibili.com/big` |
| Blackroom (bans) | `https://www.bilibili.com/blackroom/ban` |

---

## Top Navigation Bar

Horizontal nav across the top of `bilibili.com`:

```
首页 | 番剧 | 直播 | 游戏中心 | 会员购 | 漫画 | 赛事
```

These are always visible regardless of login state.

### Left sidebar channels (分区)

On the homepage, the left sidebar lists 30 content channels. Each maps to `bilibili.com/c/{SLUG}` or a top-level path:

```
动态  热门  番剧  电影  国创  电视剧  综艺  纪录片
动画  游戏  鬼畜  音乐  舞蹈  影视  娱乐  知识
科技数码  资讯  美食  小剧场  汽车  时尚美妆
体育运动  动物  vlog  绘画  人工智能  家装房产
户外潮流  健身
```

Channel URLs:
- `bilibili.com/c/{slug}` — e.g. `/c/douga` (动画), `/c/game`, `/c/music`, `/c/ai`
- Some use full words: `/c/knowledge`, `/c/information`, `/c/food`, `/c/fashion`, `/c/sports`, `/c/animal`, `/c/painting`, `/c/home`, `/c/outdoors`, `/c/gym`
- Others use abbreviations: `/c/kichiku` (鬼畜), `/c/ent`, `/c/tech`
- Short play: `/c/shortplay`
- Car: `/c/car` (no trailing slash in source)

---

## User Menu (right side of top bar, login required)

Dropdown accessible via avatar in top-right corner:

| Entry | URL | Notes |
|-------|-----|-------|
| 大会员 | `account.bilibili.com/big` | Premium status |
| 消息 | `message.bilibili.com` | Sub-items: 回复我的, @我的, 收到的赞, 系统消息, 我的消息 |
| 动态 | `t.bilibili.com` | Following feed — most important for daily use |
| 收藏 | `space.bilibili.com/{UID}/favlist` | Favorite folders |
| 历史 | `https://www.bilibili.com/account/history` | Watch history |
| 创作中心 | `member.bilibili.com/platform/home` | Creator dashboard |
| 投稿 | `member.bilibili.com/platform/upload/video/frame` | Upload |

---

## Personal Space Tabs (`space.bilibili.com/{UID}`)

Sub-navigation within the personal space:

```
主页 | 动态 | 投稿 | 合集和系列 | 收藏 | 追番追剧 | 设置
```

- **主页** — video grid + favorite folders + stats
- **动态** — this user's activity feed (distinct from `t.bilibili.com` which is the *following* feed)
- **投稿** — published videos, sortable by: 最新发布 / 最多播放 / 最多收藏
- **合集和系列** — curated video collections
- **收藏** — favorite folders (public or private)
- **追番追剧** — tracked anime/drama
- **设置** — space configuration

### User Stats (visible on personal space)

Selector: `.nav-statistics` contains `.nav-statistics__item` children.

| Stat | Class |
|------|-------|
| 关注数 (following) | `.nav-statistics__item.jumpable` (first) |
| 粉丝数 (followers) | `.nav-statistics__item.jumpable` (second) |
| 获赞数 (likes) | `.nav-statistics__item` (third) |
| 播放数 (views) | `.nav-statistics__item` (fourth) |

Values are in `.nav-statistics__item-num`.

---

## Video Page — Interaction Features

When on a watch page (`bilibili.com/video/{BV_ID}`), the toolbar below the player offers:

| Action | Selector / Class | Notes |
|--------|------------------|-------|
| Like (赞) | `.video-like` | Count in `.video-like-info` |
| Coin (投币) | `.video-coin` | Each user can donate up to 2 coins per video |
| Collect (收藏) | `.video-collect` | Add to a favorite folder |
| Share (分享) | `.video-share-wrap` | Opens share panel with link/copy/QR |
| Triple-tap (三连) | Long-press like button | Triggers like + coin + collect in one action |

**三连 (triple-tap)** is Bilibili's signature interaction — long-pressing the like button sends a like, donates 1 coin, and adds to favorites simultaneously.

### Coins (硬币)

- Users receive coins daily by logging in
- Coins are spent by "投币" on videos (1 or 2 per video)
- Coin count appears in the header user area
- Separate from B币 (B-Coins) which are purchased with real money

### Danmaku (弹幕)

Real-time comments that scroll across the video. Toggle with the danmaku button in the player controls. Danmaku data is loaded via XHR after the video player initializes.

### Charging (充电)

Monthly subscription / tipping to support creators. Accessible from the creator's space page or below the video player.

---

## Favorites (`/favlist`)

Each favorite folder displays: name, video count, visibility (公开/仅自己可见).

Two sections on the page:
- **我创建的收藏夹** — user's own folders
- **我追的合集/收藏夹** — followed collections from other users

Actions:
- Create new folder: click "新建收藏夹"
- Set visibility: per-folder setting (公开 / 仅自己可见)
- Default folder is created automatically and holds all quick-favorited videos

---

## Watch History (`/account/history`)

Features:
- **Pause/resume** recording — "暂停记录历史" / "继续记录历史"
- **Clear all** — "清空历史"
- **Date filters** — 今天 / 昨天 / 近1周 / 1周前 / 1个月前
- Each entry shows: title, progress (看到 XX:XX), uploader name, category tag

History items are in `.history-record` elements.

### Watch Later (稍后再看)

Located at `bilibili.com/watchlater/#/list`. Also appears as a default folder in the favorites section on the personal space homepage.

---

## Search (`search.bilibili.com`)

Search results are tabbed:

```
综合 | 视频 | 番剧 | 影视 | 直播 | 专栏 | 用户
```

Each tab shows a count badge (e.g., "视频99+"). Query param: `?keyword={QUERY}`.

Autocomplete suggestions appear when typing in the search input.

---

## Popular / Hot Page (`/v/popular/all`)

Tab bar:

```
综合热门 | 每周必看 | 入站必刷 | 排行榜 | 全站音乐榜
```

- **综合热门** — trending right now
- **每周必看** — weekly curated picks, URL: `/v/popular/weekly?num={ISSUE}`
- **入站必刷** — all-time classic videos
- **排行榜** — redirects to `/v/popular/rank/all`
- **全站音乐榜** — music-specific chart

### Ranking (`/v/popular/rank/all`)

24 category tabs: 全部, 番剧, 国创, 纪录片, 电影, 电视剧, 综艺, 动画, 游戏, 鬼畜, 音乐, 舞蹈, 影视, 娱乐, 知识, 科技, 数码, 美食, 汽车, 时尚, 美妆, 体育, 运动, 动物

Each entry shows: rank number, title, creator, view count, interaction count.

---

## Detecting Login State

```python
# Logged in: avatar element exists
avatar = js("document.querySelector('.header-entry-avatar')?.src || 'not logged in'")

# Logged out: login button visible
login_btn = js("document.querySelector('.header-login-entry')?.textContent?.trim() || 'no login btn'")
```

Extract the current user's UID:

```python
uid = js("document.querySelector('.header-entry-avatar')?.closest('a')?.href?.match(/space\\.bilibili\\.com\\/(\\d+)/)?.[1]")
```

---

## Gotchas

- **动态 has two meanings** — `t.bilibili.com` is the *following* feed (content from people you follow), while `space.bilibili.com/{UID}/dynamic` is a specific *user's* activity. They are different pages.
- **Favorites URL redirects** — navigating to `/favlist` may redirect to `/favlist?fid={DEFAULT_FOLDER_ID}&ftype=create`, which opens the first folder automatically.
- **History can be paused** — if the history page says "历史功能暂停中", recording was paused by the user. Click "继续记录历史" to resume.
- **UID is numeric** — Bilibili user IDs are all-numeric, unlike YouTube handles. The UID appears in the space URL and is stable.
- **BV vs AV IDs** — modern video IDs use the BV format (e.g. `BV1HeRKBdEoX`). Legacy AV format (e.g. `av170001`) still resolves but all new content uses BV.
- **Video URL gets `?vd_source=` appended** — when navigating from an authenticated session, bilibili appends a `vd_source` tracking parameter. This can be stripped.
- **Watch later is separate from history** — `/watchlater/#/list` is a single-page app path, not a sub-page of `/account/history`.
- **Coins are not B-Coins** — 硬币 (coins) are earned daily for free. B币 (B-Coins) are purchased with real money and used for tipping/charging/premium.
- **Some channel URL slugs use abbreviations** — 鬼畜 is `/c/kichiku`, 娱乐 is `/c/ent`, 科技 is `/c/tech`. Not all are pinyin or translated.
- **`wait_for_load()` is not enough on video pages** — like YouTube, the video player and its toolbar components hydrate after the load event. Add a `wait(3)` before querying video toolbar selectors.
