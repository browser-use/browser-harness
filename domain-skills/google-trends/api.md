# Google Trends — private JSON API from page context

Use the Trends private API instead of scraping the charts. Open any
`trends.google.com/trends/explore?...` tab first, then call `fetch()` from that
tab with `js(..., target_id=...)`. The page cookies (NID) make the requests
work. The same URLs fetched with `http_get` outside the browser usually return 429.

## Flow

1. `GET /trends/api/explore?hl=<lang>&tz=-60&req=<json>`, where
   `req = {"comparisonItem":[{"keyword":k,"geo":"SI","time":"today 5-y"}, ...],"category":0,"property":""}`.
   You can compare up to 5 keywords in one request.
2. The response has `widgets[]`. Each widget has `id`, `request` and `token`:
   - `TIMESERIES` → `GET /trends/api/widgetdata/multiline?hl=..&tz=-60&req=<widget.request>&token=<widget.token>`
     → `default.timelineData[] {time, formattedAxisTime, value[]}`. There is one value per keyword, scaled 0–100 to the maximum across all compared keywords.
   - `RELATED_QUERIES*` → `/trends/api/widgetdata/relatedsearches?...` → `default.rankedList[0]` is the top list and `[1]` is rising. Each item is `rankedKeyword[] {query, value, formattedValue}`, and `formattedValue` can be `"Breakout"`.
   - `GEO_MAP*` and `RELATED_TOPICS*` work the same way, through `comparedgeo` and `relatedsearches`.
3. Every response starts with an XSSI prefix (`)]}',`). Parse with `JSON.parse(t.slice(t.indexOf('{')))`.

```python
JS = r"""(async()=>{
 const req={comparisonItem:%s.map(k=>({keyword:k,geo:'SI',time:'today 5-y'})),category:0,property:''};
 const F=u=>fetch(u,{signal:AbortSignal.timeout(20000)}), P=t=>JSON.parse(t.slice(t.indexOf('{')));
 const ex=P(await (await F('/trends/api/explore?hl=sl&tz=-60&req='+encodeURIComponent(JSON.stringify(req)))).text());
 const w=ex.widgets.find(w=>w.id==='TIMESERIES');
 const d=P(await (await F('/trends/api/widgetdata/multiline?hl=sl&tz=-60&req='+encodeURIComponent(JSON.stringify(w.request))+'&token='+w.token)).text());
 return d.default.timelineData.map(p=>[p.formattedAxisTime,p.value]);
})()"""
tid = [t["targetId"] for t in list_tabs() if "trends.google.com" in t["url"]][0]
rows = js(JS % json.dumps(["dedovanje", "regres"]), target_id=tid)
```

## Comparing many terms

Values are relative within one request. To rank more than 5 terms, put the
same anchor term in every request (anchor plus 4 terms). Then divide each
term's mean by the anchor's mean in that request. Low-volume terms round to 0,
so ratios below about 0.02× the anchor are noise.

## Traps

- **Pin the tab.** Pass `target_id=` explicitly. If another job runs on the same
  daemon and switches tabs, `fetch` runs on the wrong origin and fails.
- **Timeouts.** `explore` sometimes hangs and causes `Runtime.evaluate timed out`.
  Wrap fetches in `AbortSignal.timeout(20000)` and retry with backoff (30 s, 60 s, …).
- **Rate.** 12–20 s between explore calls ran for 100+ requests without a 429.
  At faster rates you get 429s; slow down rather than rotating anything.
- **Two jobs at once.** Running a Google Search loop and a Trends loop on one
  daemon slowed both and caused timeouts. Run them one after the other.
