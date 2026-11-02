// Package daemon is the CDP websocket holder and IPC relay. One daemon per BU_NAME.
package daemon

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/browser-use/browser-harness/go/internal/auth"
	"github.com/browser-use/browser-harness/go/internal/browser"
	"github.com/browser-use/browser-harness/go/internal/cdp"
	"github.com/browser-use/browser-harness/go/internal/ipc"
	"github.com/browser-use/browser-harness/go/internal/paths"
)

const (
	bufSize         = 500
	recoveryDrain   = 2 * time.Second
	tabMarkerJS     = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"
	sessionNotFound = "Session with given id not found"
	maxReplacements = 32
)

// BUAPI is the Browser Use Cloud API base.
var BUAPI = "https://api.browser-use.com/api/v3"

var internalPrefixes = []string{"chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:"}

func hasAnyPrefix(s string, prefixes ...string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}

// Target is the subset of Target.TargetInfo the daemon reads.
type Target struct {
	TargetID string `json:"targetId"`
	Type     string `json:"type"`
	URL      string `json:"url"`
	Title    string `json:"title"`
}

func isRealPage(t Target) bool { return t.Type == "page" && !hasAnyPrefix(t.URL, internalPrefixes...) }
func isReusableBlank(t Target) bool {
	return t.Type == "page" && (t.URL == "about:blank" || strings.HasPrefix(t.URL, "about:blank#")) &&
		!strings.HasPrefix(t.Title, "Starting agent ")
}
func isInspectTab(t Target) bool {
	return t.Type == "page" && strings.HasPrefix(t.URL, "chrome://inspect")
}
func isReusableNewTab(t Target) bool {
	return t.Type == "page" && hasAnyPrefix(t.URL, "chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")
}

func harnessOpenedInspect() bool {
	_, err := os.Stat(paths.InspectMarker())
	return err == nil
}

// TabMarkerEnabled gates the cosmetic controlled-tab title marker.
func TabMarkerEnabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("BH_TAB_MARKER"))) {
	case "0", "false", "no", "off":
		return false
	}
	return true
}

// Config is the per-process daemon identity, read from the environment.
type Config struct {
	Name     string
	RemoteID string
	Kind     string // cloud | cdp | local
}

func ConfigFromEnv() Config {
	c := Config{Name: os.Getenv("BU_NAME"), RemoteID: os.Getenv("BU_BROWSER_ID")}
	if c.Name == "" {
		c.Name = "default"
	}
	switch {
	case c.RemoteID != "":
		c.Kind = "cloud"
	case os.Getenv("BU_CDP_WS") != "" || os.Getenv("BU_CDP_URL") != "":
		c.Kind = "cdp"
	default:
		c.Kind = "local"
	}
	return c
}

type event struct {
	Method    string          `json:"method"`
	Params    json.RawMessage `json:"params"`
	SessionID *string         `json:"session_id"`
}

type Daemon struct {
	cfg  Config
	logf func(string)
	cdp  *cdp.Client

	mu         sync.Mutex // guards the plain fields below
	session    string
	targetID   string
	dedicated  string
	tabs       map[string]string // targetId -> cached flat session
	tabTargets map[string]string // session -> targetId
	tabNames   map[string]string // agent-chosen name -> targetId
	netOff     map[string]bool   // sessions whose Network domain set_session disabled
	claimed    map[string]bool   // blank tabs new_tab already reused; each goes to one caller
	attachMu   sync.Mutex        // one attach per tab at a time, so the cache never holds two sessions
	events     []event
	dialog     json.RawMessage
	shutting   bool
	replaces   map[string]string
	replOrder  []string
	recoveries map[*recovery]struct{}
	recoveryWG sync.WaitGroup
	stopOnce   sync.Once
	stop       chan struct{}

	sessionState  chan struct{} // held across CDP calls
	dedicatedLock chan struct{}
	remoteStopped bool
}

type recovery struct{ cancel context.CancelFunc }

func newLock() chan struct{} { return make(chan struct{}, 1) }
func lock(l chan struct{})   { l <- struct{}{} }
func unlock(l chan struct{}) { <-l }

func New(cfg Config, logf func(string)) *Daemon {
	return &Daemon{
		cfg: cfg, logf: logf, replaces: map[string]string{}, recoveries: map[*recovery]struct{}{},
		tabs: map[string]string{}, tabTargets: map[string]string{}, tabNames: map[string]string{}, netOff: map[string]bool{}, claimed: map[string]bool{},
		stop: make(chan struct{}), sessionState: newLock(), dedicatedLock: newLock(),
	}
}

func (d *Daemon) send(ctx context.Context, method string, params any, sid string) (json.RawMessage, error) {
	return d.cdp.Send(ctx, method, params, sid)
}

func (d *Daemon) targets(ctx context.Context) ([]Target, error) {
	raw, err := d.send(ctx, "Target.getTargets", nil, "")
	if err != nil {
		return nil, err
	}
	var r struct {
		TargetInfos []Target `json:"targetInfos"`
	}
	return r.TargetInfos, json.Unmarshal(raw, &r)
}

func (d *Daemon) createBlank(ctx context.Context) (string, error) {
	raw, err := d.send(ctx, "Target.createTarget", map[string]any{"url": "about:blank", "background": true}, "")
	if err != nil {
		return "", err
	}
	var r struct {
		TargetID string `json:"targetId"`
	}
	return r.TargetID, json.Unmarshal(raw, &r)
}

func (d *Daemon) attach(ctx context.Context, tid string) (string, error) {
	raw, err := d.send(ctx, "Target.attachToTarget", map[string]any{"targetId": tid, "flatten": true}, "")
	if err != nil {
		return "", err
	}
	var r struct {
		SessionID string `json:"sessionId"`
	}
	if err := json.Unmarshal(raw, &r); err != nil {
		return "", err
	}
	d.mu.Lock()
	if old := d.tabs[tid]; old != "" {
		delete(d.tabTargets, old)
	}
	d.tabs[tid], d.tabTargets[r.SessionID] = r.SessionID, tid
	d.mu.Unlock()
	return r.SessionID, nil
}

// attachTab returns the cached session for a tab, attaching once. Reusing the
// session keeps per-session state such as device emulation across tab switches.
func (d *Daemon) attachTab(ctx context.Context, tid string) (string, error) {
	d.attachMu.Lock()
	defer d.attachMu.Unlock()
	d.mu.Lock()
	sid := d.tabs[tid]
	off := sid != "" && d.netOff[sid]
	delete(d.netOff, sid)
	d.mu.Unlock()
	if off { // pinned calls need Network events again, e.g. wait_for_network_idle
		c, cancel := context.WithTimeout(ctx, 2*time.Second)
		_, _ = d.send(c, "Network.enable", nil, sid)
		cancel()
	}
	if sid != "" {
		return sid, nil
	}
	sid, err := d.attach(ctx, tid)
	if err == nil {
		d.enableDefaultDomains(ctx, sid)
	}
	return sid, err
}

func trunc(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

// attachFirstPage attaches to a real page (or any usable page) and sets the session.
func (d *Daemon) attachFirstPage(ctx context.Context, replaces string, enableDomains bool) (*Target, error) {
	targets, err := d.targets(ctx)
	if err != nil {
		return nil, err
	}
	// Named daemons share one browser with other daemons; give each its own tab
	// so parallel navigations don't clobber each other. Cloud browsers are exclusive.
	if d.cfg.Name != "default" && d.cfg.RemoteID == "" {
		if d.cfg.Kind == "local" {
			d.closeInspectTabs(ctx, targets)
		}
		page := d.findOwnPage(targets)
		if page == nil {
			lock(d.dedicatedLock)
			refreshed, err := d.targets(ctx)
			if err == nil {
				page = d.findOwnPage(refreshed)
			}
			if err == nil && page == nil {
				tid, cerr := d.createBlank(ctx)
				if cerr != nil {
					err = cerr
				} else {
					d.mu.Lock()
					d.dedicated = tid
					d.mu.Unlock()
					d.logf(fmt.Sprintf("named daemon %s: created dedicated tab (%s)", d.cfg.Name, tid))
					page = &Target{TargetID: tid, URL: "about:blank", Type: "page"}
				}
			}
			unlock(d.dedicatedLock)
			if err != nil {
				return nil, err
			}
		}
		sid, err := d.attach(ctx, page.TargetID)
		if err != nil {
			return nil, err
		}
		d.mu.Lock()
		d.session, d.targetID = sid, page.TargetID
		d.recordReplacement(replaces, sid)
		d.mu.Unlock()
		d.logf(fmt.Sprintf("attached %s (%s) session=%s", page.TargetID, trunc(page.URL, 80), sid))
		if enableDomains {
			d.enableDefaultDomains(ctx, sid)
		}
		return page, nil
	}

	var pages []Target
	// Recovering on local Chrome: the user's other tabs are not ours to take.
	recoverLocal := replaces != "" && d.cfg.Kind == "local"
	pick := func(f func(Target) bool) {
		if len(pages) > 0 || recoverLocal {
			return
		}
		for _, t := range targets {
			if f(t) {
				pages = append(pages, t)
			}
		}
	}
	pick(isRealPage)
	pick(isReusableBlank) // fresh browsers (e.g. Browser Use cloud) start on about:blank
	pick(isReusableNewTab)
	takeOver := ""
	if len(pages) == 0 && !recoverLocal && harnessOpenedInspect() {
		// After permissions are granted the only tab is often chrome://inspect.
		for _, t := range targets {
			if isInspectTab(t) {
				pages, takeOver = []Target{t}, t.TargetID
				break
			}
		}
	}
	if len(pages) == 0 {
		tid, err := d.createBlank(ctx)
		if err != nil {
			return nil, err
		}
		d.logf(fmt.Sprintf("no real pages found, created about:blank (%s)", tid))
		pages = []Target{{TargetID: tid, URL: "about:blank", Type: "page"}}
	}
	page := pages[0]
	sid, err := d.attach(ctx, page.TargetID)
	if err != nil {
		return nil, err
	}
	d.mu.Lock()
	d.session, d.targetID = sid, page.TargetID
	d.recordReplacement(replaces, sid)
	d.mu.Unlock()
	d.logf(fmt.Sprintf("attached %s (%s) session=%s", page.TargetID, trunc(page.URL, 80), sid))
	if takeOver != "" {
		if _, err := d.send(ctx, "Page.navigate", map[string]any{"url": "about:blank"}, sid); err != nil {
			d.logf(fmt.Sprintf("take over inspect tab %s: %v", takeOver, err))
		} else {
			d.logf(fmt.Sprintf("took over inspect tab %s -> about:blank", takeOver))
		}
	}
	if d.cfg.Kind == "local" {
		d.closeInspectTabs(ctx, targets)
	}
	if enableDomains {
		d.enableDefaultDomains(ctx, sid)
	}
	return &page, nil
}

func (d *Daemon) findOwnPage(targets []Target) *Target {
	d.mu.Lock()
	tid, ded := d.targetID, d.dedicated
	d.mu.Unlock()
	for _, want := range []string{tid, ded} {
		if want == "" {
			continue
		}
		for _, t := range targets {
			if t.Type == "page" && t.TargetID == want {
				t := t
				return &t
			}
		}
	}
	return nil
}

func (d *Daemon) closeInspectTabs(ctx context.Context, targets []Target) {
	if !harnessOpenedInspect() {
		return
	}
	d.mu.Lock()
	own := d.targetID
	d.mu.Unlock()
	for _, t := range targets {
		if t.TargetID != own && isInspectTab(t) {
			if _, err := d.send(ctx, "Target.closeTarget", map[string]any{"targetId": t.TargetID}, ""); err != nil {
				d.logf(fmt.Sprintf("close inspect tab %s: %v", t.TargetID, err))
			} else {
				d.logf("closed leftover chrome://inspect tab " + t.TargetID)
			}
		}
	}
	_ = os.Remove(paths.InspectMarker())
}

// enableDefaultDomains enables Page/DOM/Runtime/Network in parallel so a tab
// switch costs one round trip, inside the helper's 5 s IPC budget.
func (d *Daemon) enableDefaultDomains(ctx context.Context, sid string) {
	var wg sync.WaitGroup
	for _, dom := range []string{"Page", "DOM", "Runtime", "Network"} {
		wg.Add(1)
		go func(dom string) {
			defer wg.Done()
			c, cancel := context.WithTimeout(ctx, 4*time.Second)
			defer cancel()
			if _, err := d.send(c, dom+".enable", nil, sid); err != nil {
				d.logf(fmt.Sprintf("enable %s on %s: %v", dom, sid, errText(err)))
			}
		}(dom)
	}
	wg.Wait()
}

// recordReplacement keeps chains so a request delayed across several recoveries
// still lands on its original tab. Caller holds d.mu.
func (d *Daemon) recordReplacement(stale, repl string) {
	if stale == "" || repl == "" || stale == repl {
		return
	}
	for src, r := range d.replaces {
		if r == stale {
			d.replaces[src] = repl
		}
	}
	if _, ok := d.replaces[stale]; !ok {
		d.replOrder = append(d.replOrder, stale)
	}
	d.replaces[stale] = repl
	for len(d.replaces) > maxReplacements {
		oldest := d.replOrder[0]
		d.replOrder = d.replOrder[1:]
		delete(d.replaces, oldest)
	}
}

func (d *Daemon) scheduleTabMarker(sid string) {
	if !TabMarkerEnabled() || sid == "" {
		return
	}
	go func() {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_, _ = d.send(ctx, "Runtime.evaluate", map[string]any{"expression": tabMarkerJS}, sid)
	}()
}

func (d *Daemon) recordEvent(method string, params json.RawMessage, sid string) {
	var sp *string
	if sid != "" {
		sp = &sid
	}
	if len(params) == 0 {
		params = json.RawMessage("{}")
	}
	d.mu.Lock()
	d.events = append(d.events, event{Method: method, Params: params, SessionID: sp})
	if len(d.events) > bufSize {
		d.events = d.events[len(d.events)-bufSize:]
	}
	var markSession string
	switch method {
	case "Target.detachedFromTarget":
		var v struct {
			SessionID string `json:"sessionId"`
		}
		if json.Unmarshal(params, &v) == nil && v.SessionID != "" {
			if tid := d.tabTargets[v.SessionID]; tid != "" && d.tabs[tid] == v.SessionID {
				delete(d.tabs, tid)
			}
			delete(d.tabTargets, v.SessionID)
		}
	case "Page.javascriptDialogOpening":
		d.dialog = params
	case "Page.javascriptDialogClosed":
		d.dialog = nil
	case "Page.loadEventFired", "Page.domContentEventFired":
		markSession = d.session
	}
	d.mu.Unlock()
	if markSession != "" {
		d.scheduleTabMarker(markSession)
	}
}

// Start resolves the browser endpoint, connects and attaches.
func (d *Daemon) Start(ctx context.Context) error {
	wsURL, err := browser.WSURL()
	if err != nil {
		return err
	}
	d.logf("connecting to " + SafeConnectionLabel(wsURL))
	var timeout time.Duration = 10 * time.Second
	if d.cfg.Kind == "local" {
		// Chrome 144+ keeps the handshake open while its Allow sheet is shown; no deadline.
		timeout = 0
		d.logf("handshake-wait: if Chrome shows an 'Allow remote debugging?' popup, click Allow")
	}
	c, err := cdp.Dial(ctx, wsURL, timeout, d.recordEvent)
	if err != nil {
		low := strings.ToLower(err.Error())
		if os.Getenv("BU_CDP_WS") != "" {
			return fmt.Errorf("CDP WS handshake failed: %v -- remote browser WebSocket connection failed. "+
				"This can happen when network policy blocks the connection, the WS URL is wrong or expired, or the remote endpoint is down. "+
				"If you use Browser Use cloud, verify auth and get a fresh URL via start_remote_daemon().", err)
		}
		if v := browser.RemoteDebuggingUserEnabled(); d.cfg.Kind == "local" && (strings.Contains(low, "timed out") || strings.Contains(low, "403")) && v != nil && *v {
			return errors.New("permission-blocked: Chrome did not approve the remote debugging connection; browser-harness did not retry or create another connection")
		}
		return fmt.Errorf("CDP WS handshake failed: %v -- click Allow in Chrome if prompted, then retry", err)
	}
	d.cdp = c
	_, err = d.attachFirstPage(ctx, "", true)
	return err
}

// SafeConnectionLabel logs only endpoint topology, never credentials or session paths.
func SafeConnectionLabel(raw string) string {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme == "" || u.Hostname() == "" {
		return "<redacted-cdp-endpoint>"
	}
	host := u.Hostname()
	if strings.Contains(host, ":") {
		host = "[" + host + "]"
	}
	if p := u.Port(); p != "" {
		host += ":" + p
	}
	return u.Scheme + "://" + host
}

// StopRemote PATCHes the cloud browser to stop; strict callers get the last error.
func (d *Daemon) StopRemote(strict bool) error {
	if d.cfg.RemoteID == "" {
		return nil
	}
	d.mu.Lock()
	done := d.remoteStopped
	d.mu.Unlock()
	if done {
		return nil
	}
	var last error
	for attempt := 0; attempt < 3; attempt++ {
		last = StopCloudBrowser(d.cfg.RemoteID)
		if last == nil {
			d.mu.Lock()
			d.remoteStopped = true
			d.mu.Unlock()
			d.logf("stopped remote browser " + d.cfg.RemoteID)
			return nil
		}
		d.logf(fmt.Sprintf("stop_remote attempt %d/3 failed (%s): %v", attempt+1, d.cfg.RemoteID, last))
		if attempt < 2 {
			time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
		}
	}
	if strict {
		return fmt.Errorf("failed to stop remote browser %s: %v", d.cfg.RemoteID, last)
	}
	return nil
}

// StopCloudBrowser sends one PATCH /browsers/{id} {"action":"stop"}.
func StopCloudBrowser(id string) error {
	key, err := auth.APIKey()
	if err != nil {
		return err
	}
	req, _ := http.NewRequest("PATCH", BUAPI+"/browsers/"+id, bytes.NewReader([]byte(`{"action": "stop"}`)))
	req.Header.Set("X-Browser-Use-API-Key", key)
	req.Header.Set("Content-Type", "application/json")
	resp, err := (&http.Client{Timeout: 15 * time.Second}).Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP Error %d", resp.StatusCode)
	}
	return nil
}

func errText(err error) string { return err.Error() }

func (d *Daemon) targetInfo(ctx context.Context, tid string) (*Target, error) {
	raw, err := d.send(ctx, "Target.getTargetInfo", map[string]any{"targetId": tid}, "")
	if err != nil {
		return nil, err
	}
	var r struct {
		TargetInfo Target `json:"targetInfo"`
	}
	return &r.TargetInfo, json.Unmarshal(raw, &r)
}

func (d *Daemon) beginRecovery(cancel context.CancelFunc) *recovery {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.shutting {
		return nil
	}
	r := &recovery{cancel: cancel}
	d.recoveries[r] = struct{}{}
	d.recoveryWG.Add(1)
	return r
}

func (d *Daemon) finishRecovery(r *recovery) {
	d.mu.Lock()
	delete(d.recoveries, r)
	d.mu.Unlock()
	d.recoveryWG.Done()
}

// cancelAndDrain cancels in-flight stale-session handlers and waits a bounded time.
func (d *Daemon) cancelAndDrain() bool {
	d.mu.Lock()
	for r := range d.recoveries {
		r.cancel()
	}
	d.mu.Unlock()
	done := make(chan struct{})
	go func() { d.recoveryWG.Wait(); close(done) }()
	select {
	case <-done:
		return true
	case <-time.After(recoveryDrain):
		return false
	}
}

// Handle answers one IPC request. token is the Windows TCP token ("" on POSIX).
func (d *Daemon) Handle(ctx context.Context, req map[string]any, token string) any {
	if token != "" && req["token"] != token {
		return map[string]any{"error": "unauthorized"}
	}
	meta, _ := req["meta"].(string)
	switch meta {
	case "ping":
		return map[string]any{"pong": true, "pid": os.Getpid(), "browser_kind": d.cfg.Kind}
	case "drain_events":
		d.mu.Lock()
		out := d.events
		d.events = nil
		d.mu.Unlock()
		if out == nil {
			out = []event{}
		}
		return map[string]any{"events": out}
	case "session":
		d.mu.Lock()
		defer d.mu.Unlock()
		return map[string]any{"session_id": nullable(d.session)}
	case "current_tab", "connection_status":
		d.mu.Lock()
		tid, sid := d.targetID, d.session
		d.mu.Unlock()
		if tid == "" {
			return map[string]any{"error": "not_attached"}
		}
		info, err := d.targetInfo(ctx, tid)
		if err != nil {
			return map[string]any{"error": "cdp_disconnected"}
		}
		if meta == "current_tab" {
			return map[string]any{"targetId": info.TargetID, "url": info.URL, "title": info.Title}
		}
		var page any
		if isRealPage(*info) {
			title := info.Title
			if title == "" {
				title = "(untitled)"
			}
			page = map[string]any{"targetId": info.TargetID, "title": title, "url": info.URL}
		}
		return map[string]any{"target_id": tid, "session_id": nullable(sid), "page": page}
	case "set_session":
		lock(d.sessionState)
		d.mu.Lock()
		old := d.session
		d.session, _ = req["session_id"].(string)
		if t, _ := req["target_id"].(string); t != "" {
			d.targetID = t
		}
		newSID := d.session
		d.mu.Unlock()
		unlock(d.sessionState)
		// Disable Network on the old session (keeps background-tab traffic out of
		// the event buffer) in parallel with enabling the new one.
		var wg sync.WaitGroup
		if old != "" && old != newSID {
			wg.Add(1)
			go func() {
				defer wg.Done()
				c, cancel := context.WithTimeout(ctx, 2*time.Second)
				defer cancel()
				if _, err := d.send(c, "Network.disable", nil, old); err == nil {
					d.mu.Lock()
					d.netOff[old] = true
					d.mu.Unlock()
				}
			}()
		}
		d.enableDefaultDomains(ctx, newSID)
		wg.Wait()
		d.scheduleTabMarker(newSID)
		return map[string]any{"session_id": nullable(newSID)}
	case "attach":
		tid, _ := req["target_id"].(string)
		if tid == "" {
			return map[string]any{"error": "'target_id'"}
		}
		sid, err := d.attachTab(ctx, tid)
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		return map[string]any{"session_id": sid}
	case "claim_tab":
		tid, _ := req["target_id"].(string)
		d.mu.Lock()
		ok := tid != "" && !d.claimed[tid]
		d.claimed[tid] = true
		d.mu.Unlock()
		return map[string]any{"ok": ok}
	case "name_tab":
		name, _ := req["name"].(string)
		tid, _ := req["target_id"].(string)
		if name == "" || tid == "" {
			return map[string]any{"error": "name_tab needs a name and a tab"}
		}
		d.mu.Lock()
		for n, t := range d.tabNames { // one name per tab
			if t == tid {
				delete(d.tabNames, n)
			}
		}
		d.tabNames[name] = tid
		d.mu.Unlock()
		return map[string]any{"ok": true}
	case "tab_names":
		// Drop names of closed tabs, then return name -> targetId.
		targets, err := d.targets(ctx)
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		open := map[string]bool{}
		for _, t := range targets {
			open[t.TargetID] = true
		}
		d.mu.Lock()
		names := map[string]any{}
		for n, t := range d.tabNames {
			if open[t] {
				names[n] = t
			} else {
				delete(d.tabNames, n)
			}
		}
		d.mu.Unlock()
		return map[string]any{"names": names}
	case "pending_dialog":
		d.mu.Lock()
		defer d.mu.Unlock()
		if d.dialog == nil {
			return map[string]any{"dialog": nil}
		}
		return map[string]any{"dialog": d.dialog}
	case "shutdown":
		return d.shutdown()
	case "record_observe", "record_start", "record_stop", "record_dir":
		return d.handleRecord(ctx, meta, req)
	}
	return d.relay(ctx, req)
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func (d *Daemon) shutdown() map[string]any {
	d.mu.Lock()
	if d.shutting {
		d.mu.Unlock()
		return map[string]any{"error": "shutdown already in progress"}
	}
	d.shutting = true
	d.mu.Unlock()
	if !d.cancelAndDrain() {
		// Stay a retryable cleanup authority; the strict caller keeps the endpoint.
		d.mu.Lock()
		d.shutting = false
		d.mu.Unlock()
		return map[string]any{"error": "stale-session recovery did not stop"}
	}
	if err := d.StopRemote(true); err != nil {
		// A failed cloud stop keeps the daemon alive so a later shutdown can retry.
		lock(d.sessionState)
		d.mu.Lock()
		d.shutting = false
		d.mu.Unlock()
		unlock(d.sessionState)
		return map[string]any{"error": err.Error()}
	}
	d.stopOnce.Do(func() { close(d.stop) })
	return map[string]any{"ok": true}
}

// foreground activates the attached tab before a screenshot or wheel event:
// headless Chrome renders a hidden tab only when it changes, so both can wait
// forever for a frame. Never on discovered local Chrome: that would move the user's tabs.
func (d *Daemon) foreground(ctx context.Context, sid string) {
	d.mu.Lock()
	tid := d.tabTargets[sid]
	if sid == d.session {
		tid = d.targetID
	}
	d.mu.Unlock()
	if d.cfg.Kind == "local" || tid == "" {
		return
	}
	actx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	_, _ = d.send(actx, "Target.activateTarget", map[string]any{"targetId": tid}, "")
}

func (d *Daemon) relay(ctx context.Context, req map[string]any) map[string]any {
	method, _ := req["method"].(string)
	if method == "" {
		return map[string]any{"error": "'method'"}
	}
	params := req["params"]
	if params == nil {
		params = map[string]any{}
	}
	explicit, _ := req["session_id"].(string)
	d.mu.Lock()
	cur := d.session
	d.mu.Unlock()
	// Browser-level Target.* calls must not carry a session.
	sid := ""
	if !strings.HasPrefix(method, "Target.") {
		sid = explicit
		if sid == "" {
			sid = cur
		}
	}
	// Both wait for a compositor frame, which a hidden headless tab never produces.
	if p, _ := params.(map[string]any); method == "Page.captureScreenshot" || method == "Input.dispatchMouseEvent" && p["type"] == "mouseWheel" {
		d.foreground(ctx, sid)
	}
	res, err := d.send(ctx, method, params, sid)
	if err == nil {
		return map[string]any{"result": res}
	}
	msg := err.Error()
	if !strings.Contains(msg, sessionNotFound) || sid == "" || explicit != "" {
		// Explicit-session callers asked for that exact tab; never redirect them.
		return map[string]any{"error": msg}
	}
	rctx, cancel := context.WithCancel(ctx)
	defer cancel()
	r := d.beginRecovery(cancel)
	if r == nil {
		return map[string]any{"error": "daemon is shutting down"}
	}
	defer d.finishRecovery(r)
	lock(d.sessionState)
	d.mu.Lock()
	shutting := d.shutting
	repl := d.replaces[sid]
	current := d.session
	d.mu.Unlock()
	recoveredHere := false
	if shutting {
		unlock(d.sessionState)
		return map[string]any{"error": "daemon is shutting down"}
	}
	if repl == "" && sid == current {
		d.logf(fmt.Sprintf("stale session %s, re-attaching", sid))
		page, aerr := d.attachFirstPage(rctx, sid, false)
		if aerr != nil || page == nil {
			unlock(d.sessionState)
			if aerr != nil && rctx.Err() == nil {
				return map[string]any{"error": aerr.Error()}
			}
			return map[string]any{"error": msg}
		}
		d.mu.Lock()
		repl = d.replaces[sid]
		d.mu.Unlock()
		recoveredHere = repl != ""
	}
	unlock(d.sessionState)
	if recoveredHere {
		d.enableDefaultDomains(rctx, repl)
	}
	// Retry only on a session known to replace this exact stale one; the user
	// may have switched tabs deliberately while this request waited.
	if repl != "" {
		res, rerr := d.send(rctx, method, params, repl)
		if rerr != nil {
			return map[string]any{"error": rerr.Error()}
		}
		return map[string]any{"result": res}
	}
	return map[string]any{"error": msg}
}

// Serve accepts IPC connections until shutdown, then closes owned resources.
func (d *Daemon) Serve(ctx context.Context) error {
	l, token, err := ipc.Listen(d.cfg.Name)
	if err != nil {
		return err
	}
	d.logf(fmt.Sprintf("listening on %s (name=%s, remote=%s)", ipc.SockAddr(d.cfg.Name), d.cfg.Name, orLocal(d.cfg.RemoteID)))
	reqCtx, cancelReqs := context.WithCancel(ctx)
	defer cancelReqs()
	go func() {
		select {
		case <-d.stop:
		case <-ctx.Done():
		case <-d.cdp.Done():
			d.logf("cdp websocket closed")
		}
		l.Close()
	}()
	var conns sync.WaitGroup
	for {
		conn, err := l.Accept()
		if err != nil {
			break
		}
		conns.Add(1)
		go func() {
			defer conns.Done()
			d.serveConn(reqCtx, conn, token)
		}()
	}
	// A crash or cancellation skips meta=shutdown; set the same barrier here.
	d.mu.Lock()
	d.shutting = true
	d.mu.Unlock()
	drained := d.cancelAndDrain()
	if drained {
		lock(d.sessionState)
		lock(d.dedicatedLock)
		d.mu.Lock()
		ded := d.dedicated
		d.mu.Unlock()
		if ded != "" {
			c, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			if _, err := d.send(c, "Target.closeTarget", map[string]any{"targetId": ded}, ""); err != nil {
				d.logf(fmt.Sprintf("close dedicated tab on shutdown: %v", err))
			} else {
				d.mu.Lock()
				d.dedicated = ""
				d.mu.Unlock()
			}
			cancel()
		}
		unlock(d.dedicatedLock)
		unlock(d.sessionState)
	} else {
		d.logf("skip dedicated-tab cleanup: stale-session recovery did not stop")
	}
	ipc.CleanupEndpoint(d.cfg.Name)
	return nil
}

func orLocal(s string) string {
	if s == "" {
		return "local"
	}
	return s
}

func (d *Daemon) serveConn(ctx context.Context, conn net.Conn, token string) {
	defer conn.Close()
	line, err := bufio.NewReaderSize(conn, 1<<16).ReadBytes('\n')
	if len(line) == 0 {
		return
	}
	var resp any
	var req map[string]any
	// UseNumber keeps request numbers verbatim, both for CDP params and recorded helper args.
	dec := json.NewDecoder(bytes.NewReader(line))
	dec.UseNumber()
	if jerr := dec.Decode(&req); jerr != nil {
		d.logf(fmt.Sprintf("conn: %v", jerr))
		resp = map[string]any{"error": jerr.Error()}
	} else {
		// Clients send one line and wait without half-closing; a read returning means they hung up.
		cctx, cancel := context.WithCancel(ctx)
		defer cancel()
		go func() { _, _ = conn.Read(make([]byte, 1)); cancel() }()
		resp = d.Handle(cctx, req, token)
	}
	_ = err
	b, merr := json.Marshal(resp)
	if merr != nil {
		b, _ = json.Marshal(map[string]any{"error": merr.Error()})
	}
	_, _ = conn.Write(append(b, '\n'))
}
