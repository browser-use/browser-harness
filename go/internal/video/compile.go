// Package video initializes, compiles, reviews and exports browser-harness
// recordings as short explainer videos rendered by video-template.html.
package video

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

type Obj = pyjson.Obj

const (
	sourceManifest    = "video-source.json"
	compositionPrefix = "window.COMPOSITION ="
	viewportTolerance = 2
	templateName      = "video-template.html"
)

var (
	sensitive = regexp.MustCompile(`(?i)@|onmicrosoft\.com|(?:tenant|user|object)[_-]?id|` +
		`\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b`)
	routeUnsafe = regexp.MustCompile(`(?i)@|[?#]|://|onmicrosoft|(?:tenant|user|object)[_-]?id|` +
		`\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b`)
	opaqueHex = regexp.MustCompile(`(?i)^#[0-9a-f]{6}$`)
	nonSpace  = regexp.MustCompile(`\S+`)
)

var houseStyle = Obj{
	{K: "version", V: 1},
	{K: "frameStyle", V: "native"},
	{K: "readingWpm", V: 380},
	{K: "background", V: []any{"#efece4", "#dce7e7"}},
	{K: "cursorStart", V: Obj{{K: "x", V: 700}, {K: "y", V: 280}}},
	{K: "pacing", V: Obj{
		{K: "captionBaseSeconds", V: 0.35},
		{K: "captionSecondsPerWord", V: 0.2},
		{K: "rawToCardHoldSeconds", V: 0.55},
		{K: "baseDurationBudget", V: 22},
		{K: "extraActionSeconds", V: 1.25},
		{K: "extraExplanationSeconds", V: 3},
		{K: "maximumDurationBudget", V: 32},
	}},
	{K: "motion", V: Obj{
		{K: "autoFollow", V: true},
		{K: "autoZoom", V: 1.7},
		{K: "cursorDuration", V: 0.48},
		{K: "zoomDuration", V: 0.42},
		{K: "panDuration", V: 0.55},
		{K: "wideScale", V: 0.78},
		{K: "reactionLag", V: 0.025},
		{K: "reactionFade", V: 0.04},
	}},
	{K: "privacy", V: Obj{{K: "pad", V: 10}, {K: "mask", V: Obj{{K: "fill", V: "#ffffff"}, {K: "stroke", V: false}, {K: "radius", V: 0}}}}},
}

var (
	actionKeys      = set("event", "frameEvent", "afterEvent", "chapter", "route", "afterRoute", "narration", "label", "detour", "error", "context", "showTyping")
	briefKeys       = set("task", "summary", "plan", "actions", "explanations", "outcomeTitle", "outcomeSummary", "outcomes", "privacy")
	privacyKeys     = set("reviewedFrames", "redact")
	explanationKeys = set("afterAction", "title", "summary", "observed", "mistake", "correction")
	typeHelpers     = set("type_text", "fill", "fill_input")
	clickHelpers    = set("click_at_xy")
	redactionKeys   = set("x", "y", "w", "h", "fill", "stroke", "radius", "pad")
)

func set(keys ...string) map[string]bool {
	m := map[string]bool{}
	for _, k := range keys {
		m[k] = true
	}
	return m
}

// BriefError means an edit brief violates the deliberately small authoring contract.
type BriefError struct{ msg string }

func (e *BriefError) Error() string { return e.msg }

func errf(format string, a ...any) error { return &BriefError{fmt.Sprintf(format, a...)} }

// --- Python value semantics over pyjson.Loads output ---

func asObj(v any) (Obj, bool) { o, ok := v.(Obj); return o, ok }
func asList(v any) ([]any, bool) {
	a, ok := v.([]any)
	return a, ok
}

func asInt(v any) (int, bool) {
	switch t := v.(type) {
	case int:
		return t, true
	case json.Number:
		if strings.ContainsAny(string(t), ".eE") {
			return 0, false
		}
		n, err := strconv.Atoi(string(t))
		return n, err == nil
	}
	return 0, false
}

// asNum is isinstance(v, (int, float)) without bool.
func asNum(v any) (float64, bool) {
	switch t := v.(type) {
	case int:
		return float64(t), true
	case float64:
		return t, true
	case json.Number:
		f, err := t.Float64()
		return f, err == nil
	}
	return 0, false
}

// toFloat is Python's float(v): numbers and numeric strings.
func toFloat(v any) (float64, bool) {
	if f, ok := asNum(v); ok {
		return f, true
	}
	if s, ok := v.(string); ok {
		f, err := strconv.ParseFloat(strings.TrimSpace(s), 64)
		return f, err == nil
	}
	return 0, false
}

func mustFloat(v any) float64 { f, _ := toFloat(v); return f }

func truthy(v any) bool {
	switch t := v.(type) {
	case nil:
		return false
	case bool:
		return t
	case string:
		return t != ""
	case Obj:
		return len(t) > 0
	case []any:
		return len(t) > 0
	}
	if f, ok := asNum(v); ok {
		return f != 0
	}
	return true
}

// pyStr is str(v).
func pyStr(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case nil:
		return "None"
	case bool:
		if t {
			return "True"
		}
		return "False"
	case json.Number:
		return string(t)
	case float64:
		return pyjson.Dumps(t, 0)
	case int:
		return strconv.Itoa(t)
	}
	return pyjson.DumpsUnicode(v)
}

func orEmpty(v any) string {
	if !truthy(v) {
		return ""
	}
	return pyStr(v)
}

func cut(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

// round is Python's round(x, 3).
func round(x float64) float64 {
	f, _ := strconv.ParseFloat(strconv.FormatFloat(x, 'f', 3, 64), 64)
	return f
}

// --- files ---

func loadJSON(path string) (Obj, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, errf("cannot read %s: %v", path, err)
	}
	v, err := pyjson.Loads(raw)
	if err != nil {
		return nil, errf("cannot read %s: %v", path, err)
	}
	o, ok := asObj(v)
	if !ok {
		return nil, errf("%s must contain a JSON object", path)
	}
	return o, nil
}

func fileHash(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

func writeText(path, text string) error { return os.WriteFile(path, []byte(text), 0o644) }

func loadComposition(path string) (any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, errf("cannot read %s: %v", path, err)
	}
	text := strings.TrimSpace(string(raw))
	if !strings.HasPrefix(text, compositionPrefix) || !strings.HasSuffix(text, ";") {
		return nil, errf("%s is not a generated composition", path)
	}
	var v any
	if err := json.Unmarshal([]byte(strings.TrimSpace(text[len(compositionPrefix):len(text)-1])), &v); err != nil {
		return nil, errf("cannot read %s: %v", path, err)
	}
	if _, ok := v.(map[string]any); !ok {
		return nil, errf("%s must set a JSON object", path)
	}
	return v, nil
}

// sameJSON compares like Python dict equality (1 == 1.0, key order ignored).
func sameJSON(a any, b Obj) bool {
	var bv any
	if json.Unmarshal([]byte(pyjson.Dumps(b, 0)), &bv) != nil {
		return false
	}
	return reflect.DeepEqual(a, bv)
}

func usedFrames(beats []any) []string {
	var frames []string
	for _, b := range beats {
		o, _ := asObj(b)
		for _, k := range []string{"frame", "after"} {
			if f := o.Get(k); truthy(f) {
				s := pyStr(f)
				if !containsStr(frames, s) {
					frames = append(frames, s)
				}
			}
		}
	}
	return frames
}

func containsStr(a []string, s string) bool {
	for _, x := range a {
		if x == s {
			return true
		}
	}
	return false
}

func sourceFiles(rec string) []string {
	var out []string
	for _, n := range []string{"events.jsonl", "meta.json", "recording-summary.json"} {
		if fi, err := os.Stat(filepath.Join(rec, n)); err == nil && fi.Mode().IsRegular() {
			out = append(out, n)
		}
	}
	matches, _ := filepath.Glob(filepath.Join(rec, "*.jpg"))
	var frames []string
	for _, m := range matches {
		stem := strings.TrimSuffix(filepath.Base(m), filepath.Ext(m))
		if stem != "" && strings.Trim(stem, "0123456789") == "" {
			frames = append(frames, filepath.Base(m))
		}
	}
	sort.Strings(frames)
	return append(out, frames...)
}

func loadMeta(rec string) (Obj, bool, error) {
	p := filepath.Join(rec, "meta.json")
	if fi, err := os.Stat(p); err != nil || !fi.Mode().IsRegular() {
		return Obj{}, false, nil
	}
	m, err := loadJSON(p)
	return m, true, err
}

func writeSourceManifest(rec string) error {
	meta, hasMeta, err := loadMeta(rec)
	if err != nil {
		return err
	}
	files := Obj{}
	for _, n := range sourceFiles(rec) {
		h, err := fileHash(filepath.Join(rec, n))
		if err != nil {
			return err
		}
		files = append(files, pyjson.KV{K: n, V: h})
	}
	m := Obj{
		{K: "recording", V: filepath.Base(rec)},
		{K: "started", V: meta.Get("started")},
		{K: "explicit", V: hasMeta && meta.Get("auto") != true},
		{K: "files", V: files},
	}
	return writeText(filepath.Join(rec, sourceManifest), pyjson.Dumps(m, 2)+"\n")
}

func verifySourceManifest(rec string) error {
	m, err := loadJSON(filepath.Join(rec, sourceManifest))
	if err != nil {
		return err
	}
	if m.Get("recording") != filepath.Base(rec) {
		return errf("recording directory does not match video-source.json")
	}
	expected, ok := asObj(m.Get("files"))
	if !ok {
		return errf("video-source.json has no source hashes")
	}
	names := sourceFiles(rec)
	want := map[string]bool{}
	for _, kv := range expected {
		want[kv.K] = true
	}
	if len(want) != len(names) {
		return errf("recording source files changed after initialization")
	}
	for _, n := range names {
		if !want[n] {
			return errf("recording source files changed after initialization")
		}
	}
	for _, n := range names {
		h, err := fileHash(filepath.Join(rec, n))
		if err != nil {
			return err
		}
		if expected.Get(n) != h {
			return errf("recording source changed after initialization: %s", n)
		}
	}
	return nil
}

// --- validation ---

func rejectUnknown(v Obj, allowed map[string]bool, where string) error {
	var unknown []string
	for _, kv := range v {
		if !allowed[kv.K] {
			unknown = append(unknown, kv.K)
		}
	}
	if len(unknown) > 0 {
		sort.Strings(unknown)
		return errf("%s has unsupported field(s): %s", where, strings.Join(unknown, ", "))
	}
	return nil
}

func requireText(v any, where string) (string, error) {
	s, ok := v.(string)
	if !ok || strings.TrimSpace(s) == "" {
		return "", errf("%s must be non-empty text", where)
	}
	return strings.TrimSpace(s), nil
}

func requireTextList(v any, where string, low, high int) ([]string, error) {
	a, ok := asList(v)
	if !ok || len(a) < low || len(a) > high {
		return nil, errf("%s must contain %d–%d items", where, low, high)
	}
	out := make([]string, len(a))
	for i, item := range a {
		s, err := requireText(item, fmt.Sprintf("%s[%d]", where, i))
		if err != nil {
			return nil, err
		}
		out[i] = s
	}
	return out, nil
}

func optionalText(v any, where string) (*string, error) {
	if v == nil {
		return nil, nil
	}
	s, err := requireText(v, where)
	return &s, err
}

func words(v any) int { return len(nonSpace.FindAllString(orEmpty(v), -1)) }

func cardDuration(title string, summary *string, details []string, kind string, wpm float64) float64 {
	parts := []string{}
	for _, p := range append(append([]string{title}, deref(summary)), details...) {
		if p != "" {
			parts = append(parts, p)
		}
	}
	base := 4.0
	if kind == "intro" || kind == "outcome" {
		base = 4.5
	}
	return round(math.Max(base, 0.4+float64(words(strings.Join(parts, " ")))*60/wpm))
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func validateNarration(v any, where string) (*string, error) {
	if v == nil {
		return nil, nil
	}
	s, ok := v.(string)
	if !ok {
		return nil, errf("%s must be text", where)
	}
	if words(s) > 7 {
		return nil, errf("%s exceeds seven words", where)
	}
	s = strings.TrimSpace(s)
	return &s, nil
}

func eventAt(events []any, number any, where string) (Obj, error) {
	n, ok := asInt(number)
	if !ok {
		return nil, errf("%s must be a one-based integer", where)
	}
	if n < 1 || n > len(events) {
		return nil, errf("%s is outside recording-summary.json", where)
	}
	ev, _ := asObj(events[n-1])
	if !truthy(ev.Get("frame")) {
		return nil, errf("%s has no captured frame", where)
	}
	return ev, nil
}

type point struct{ x, y float64 }

func hasAll(o Obj, keys ...string) bool {
	for _, k := range keys {
		if o.Get(k) == nil {
			return false
		}
	}
	return true
}

func eventTarget(ev Obj) *point {
	if c, ok := asObj(ev.Get("cursor")); ok && hasAll(c, "x", "y") {
		return &point{mustFloat(c.Get("x")), mustFloat(c.Get("y"))}
	}
	if b, ok := asObj(ev.Get("box")); ok && hasAll(b, "x", "y", "w", "h") {
		return &point{mustFloat(b.Get("x")) + mustFloat(b.Get("w"))*0.3, mustFloat(b.Get("y")) + mustFloat(b.Get("h"))/2}
	}
	return nil
}

func requireMatchingViewport(ev, viewport Obj, where string) error {
	c, _ := asObj(ev.Get("viewport"))
	cw, ok1 := toFloat(c.Get("w"))
	ch, ok2 := toFloat(c.Get("h"))
	vw, ok3 := toFloat(viewport.Get("w"))
	vh, ok4 := toFloat(viewport.Get("h"))
	if !ok1 || !ok2 || !ok3 || !ok4 {
		return errf("%s has no valid viewport", where)
	}
	if math.Abs(cw-vw) > viewportTolerance || math.Abs(ch-vh) > viewportTolerance {
		return errf("%s uses a different viewport; split or normalize the recording first", where)
	}
	return nil
}

func defaultActionDuration(beat, pacing Obj) float64 {
	base := 0.7
	if truthy(beat.Get("click")) {
		base = 1.15
	}
	if truthy(beat.Get("after")) {
		base = math.Max(base, 1.4)
	}
	if typing, ok := asObj(beat.Get("type")); ok && len(typing) > 0 {
		base = math.Max(base, 0.6+float64(len([]rune(orEmpty(typing.Get("text")))))*0.035)
	}
	if n := beat.Get("narration"); truthy(n) {
		base = math.Max(base, mustFloat(pacing.Get("captionBaseSeconds"))+mustFloat(pacing.Get("captionSecondsPerWord"))*float64(words(n)))
	}
	return round(base)
}

func durationBudget(actions, explanations, rawToCard int, pacing Obj) float64 {
	b := mustFloat(pacing.Get("baseDurationBudget"))
	b += float64(max(0, actions-5)) * mustFloat(pacing.Get("extraActionSeconds"))
	b += float64(max(0, explanations-1)) * mustFloat(pacing.Get("extraExplanationSeconds"))
	b += float64(rawToCard) * mustFloat(pacing.Get("rawToCardHoldSeconds"))
	return round(math.Min(b, mustFloat(pacing.Get("maximumDurationBudget"))))
}

func addRawToCardHolds(beats []Obj, pacing Obj) int {
	hold := mustFloat(pacing.Get("rawToCardHoldSeconds"))
	count := 0
	for i := 0; i+1 < len(beats); i++ {
		if truthy(beats[i].Get("card")) || !truthy(beats[i+1].Get("card")) {
			continue
		}
		beats[i] = beats[i].Set("endStateHold", hold)
		beats[i] = beats[i].Set("dur", round(mustFloat(beats[i].Get("dur"))+hold))
		count++
	}
	return count
}

// validateNarrationCadence keeps narration semantic and sticky instead of mirroring every frame.
func validateNarrationCadence(beats []Obj) error {
	var segments [][]Obj
	var cur []Obj
	for _, b := range beats {
		if truthy(b.Get("card")) {
			if len(cur) > 0 {
				segments = append(segments, cur)
				cur = nil
			}
		} else {
			cur = append(cur, b)
		}
	}
	if len(cur) > 0 {
		segments = append(segments, cur)
	}
	for _, seg := range segments {
		cues := 0
		for _, b := range seg {
			if truthy(b.Get("narration")) {
				cues++
			}
		}
		if len(seg) >= 3 && cues > int(math.Ceil(float64(len(seg))/2)) {
			return errf("narration is sticky: set it only when the thought changes, then " +
				"omit it while 2–3 screenshots advance underneath")
		}
		consecutive := 0
		for _, b := range seg {
			if truthy(b.Get("narration")) {
				consecutive++
			} else {
				consecutive = 0
			}
			if consecutive >= 3 {
				return errf("three consecutive actions change narration; omit narration on " +
					"intervening actions so text and screenshots use different pacing")
			}
		}
	}
	return nil
}

func compileAction(actionV any, index int, events []any, plan []string, firstTS float64, prev *point,
	viewport, pacing Obj, revealed map[int]string) (Obj, *point, error) {
	at := func(s string) string { return fmt.Sprintf("actions[%d]%s", index, s) }
	action, ok := asObj(actionV)
	if !ok {
		return nil, nil, errf("%s must be an object", at(""))
	}
	if err := rejectUnknown(action, actionKeys, at("")); err != nil {
		return nil, nil, err
	}
	if action.Has("showTyping") {
		if _, ok := action.Get("showTyping").(bool); !ok {
			return nil, nil, errf("%s must be true or false", at(".showTyping"))
		}
	}
	ev, err := eventAt(events, action.Get("event"), at(".event"))
	if err != nil {
		return nil, nil, err
	}
	if err := requireMatchingViewport(ev, viewport, at(".event")); err != nil {
		return nil, nil, err
	}
	frameEv := ev
	if action.Get("frameEvent") != nil {
		if frameEv, err = eventAt(events, action.Get("frameEvent"), at(".frameEvent")); err != nil {
			return nil, nil, err
		}
		if err := requireMatchingViewport(frameEv, viewport, at(".frameEvent")); err != nil {
			return nil, nil, err
		}
	}
	chapter, ok := asInt(action.Get("chapter"))
	if !ok || chapter < 0 || chapter >= len(plan) {
		return nil, nil, errf("%s must index plan", at(".chapter"))
	}
	route, err := requireText(action.Get("route"), at(".route"))
	if err != nil {
		return nil, nil, err
	}
	if routeUnsafe.MatchString(route) {
		return nil, nil, errf("%s must be semantic, not a raw URL or identity", at(".route"))
	}
	beat := Obj{{K: "frame", V: frameEv.Get("frame")}, {K: "route", V: route}, {K: "chapter", V: chapter}}
	if n := action.Get("afterEvent"); n != nil {
		after, err := eventAt(events, n, at(".afterEvent"))
		if err != nil {
			return nil, nil, err
		}
		if err := requireMatchingViewport(after, viewport, at(".afterEvent")); err != nil {
			return nil, nil, err
		}
		beat = beat.Set("after", after.Get("frame"))
		if r := action.Get("afterRoute"); r != nil {
			ar, err := requireText(r, at(".afterRoute"))
			if err != nil {
				return nil, nil, err
			}
			if routeUnsafe.MatchString(ar) {
				return nil, nil, errf("%s must be semantic", at(".afterRoute"))
			}
			beat = beat.Set("afterRoute", ar)
		}
	}
	narration, err := validateNarration(action.Get("narration"), at(".narration"))
	if err != nil {
		return nil, nil, err
	}
	if narration != nil {
		beat = beat.Set("narration", *narration)
	}
	if l := action.Get("label"); l != nil {
		label, err := requireText(l, at(".label"))
		if err != nil {
			return nil, nil, err
		}
		beat = beat.Set("label", label)
	}
	if action.Get("detour") == true {
		beat = beat.Set("detour", true)
	}
	if action.Get("error") == true {
		beat = beat.Set("error", true)
	}

	helper := orEmpty(ev.Get("helper"))
	switch {
	case clickHelpers[helper]:
		c, ok := asObj(ev.Get("cursor"))
		if !ok || !hasAll(c, "x", "y") {
			return nil, nil, errf("%s identifies a click without captured coordinates", at(""))
		}
		beat = beat.Set("cursor", Obj{{K: "x", V: c.Get("x")}, {K: "y", V: c.Get("y")}})
		beat = beat.Set("click", true)
	case typeHelpers[helper]:
		box, ok := asObj(ev.Get("box"))
		if !ok || !hasAll(box, "x", "y", "w", "h") {
			return nil, nil, errf("%s identifies typing without a captured box", at(""))
		}
		show := action.Get("showTyping") == true
		if show && truthy(ev.Get("password")) {
			return nil, nil, errf("%s cannot reveal a password field", at(".showTyping"))
		}
		line, isLine := asInt(ev.Get("sourceLine"))
		text, revealedOK := revealed[line]
		if show && (!isLine || !revealedOK) {
			return nil, nil, errf("%s requires the original typed event", at(".showTyping"))
		}
		typ := Obj{{K: "box", V: Obj{{K: "x", V: box.Get("x")}, {K: "y", V: box.Get("y")}, {K: "w", V: box.Get("w")}, {K: "h", V: box.Get("h")}}}}
		if show {
			typ = typ.Set("text", text)
		} else {
			typ = typ.Set("text", "••••••").Set("redact", true)
		}
		beat = beat.Set("type", typ)
	case action.Get("showTyping") != nil:
		return nil, nil, errf("%s requires a typing event", at(".showTyping"))
	}

	target := eventTarget(ev)
	if action.Get("context") == true && !(truthy(beat.Get("click")) || truthy(beat.Get("type"))) {
		beat = beat.Set("wide", true)
	} else if target != nil && prev != nil {
		distance := math.Hypot(target.x-prev.x, target.y-prev.y)
		diagonal := math.Hypot(mustFloat(viewport.Get("w")), mustFloat(viewport.Get("h")))
		if distance > diagonal*0.58 {
			beat = beat.Set("cameraCut", true)
		}
	}
	if ts, ok := asNum(ev.Get("ts")); ok {
		beat = beat.Set("t", round(math.Max(0, ts-firstTS)))
	}
	beat = beat.Set("dur", defaultActionDuration(beat, pacing))
	if target == nil {
		target = prev
	}
	return beat, target, nil
}

func validatePrivacy(reviewed []string, redact Obj, beats []any) error {
	frames := usedFrames(beats)
	all := append(append([]string{}, frames...), reviewed...)
	for _, kv := range redact {
		all = append(all, kv.K)
	}
	for _, f := range all {
		if filepath.Base(f) != f || f == "" || !strings.HasSuffix(strings.ToLower(f), ".jpg") {
			return errf("invalid frame name: %s", f)
		}
	}
	seen := map[string]bool{}
	for _, f := range reviewed {
		if seen[f] {
			return errf("privacy.reviewedFrames contains duplicates")
		}
		seen[f] = true
	}
	var missing []string
	for _, f := range frames {
		if !seen[f] {
			missing = append(missing, f)
		}
	}
	if len(missing) > 0 {
		return errf("privacy review missing: %s", strings.Join(missing, ", "))
	}
	var unknown []string
	for _, kv := range redact {
		if !containsStr(frames, kv.K) {
			unknown = append(unknown, kv.K)
		}
	}
	if len(unknown) > 0 {
		sort.Strings(unknown)
		return errf("privacy.redact lists unused frames: %s", strings.Join(unknown, ", "))
	}
	for _, kv := range redact {
		rects, ok := asList(kv.V)
		if !ok {
			return errf("privacy.redact.%s must be a list", kv.K)
		}
		for i, r := range rects {
			where := fmt.Sprintf("privacy.redact.%s[%d]", kv.K, i)
			rect, ok := asObj(r)
			if !ok {
				return errf("%s must be an object", where)
			}
			if err := rejectUnknown(rect, redactionKeys, where); err != nil {
				return err
			}
			for _, k := range []string{"x", "y", "w", "h"} {
				if f, ok := asNum(rect.Get(k)); !ok || math.IsInf(f, 0) || math.IsNaN(f) {
					return errf("%s.%s must be a finite number", where, k)
				}
			}
			if w, _ := asNum(rect.Get("w")); w <= 0 {
				return errf("%s must have positive width and height", where)
			}
			if h, _ := asNum(rect.Get("h")); h <= 0 {
				return errf("%s must have positive width and height", where)
			}
			for _, k := range []string{"fill", "stroke"} {
				v := rect.Get(k)
				if v == nil || v == false {
					continue
				}
				if s, ok := v.(string); !ok || !opaqueHex.MatchString(s) {
					return errf("%s.%s must be false or opaque six-digit hex", where, k)
				}
			}
		}
	}
	return nil
}

func strs(a []string) []any {
	out := make([]any, len(a))
	for i, s := range a {
		out[i] = s
	}
	return out
}

func withSub(o Obj, sub *string) Obj {
	if sub != nil {
		o = append(o, pyjson.KV{K: "sub", V: *sub})
	}
	return o
}

func compileBrief(summary, brief, style Obj, revealed map[int]string) (Obj, error) {
	if err := rejectUnknown(brief, briefKeys, "edit brief"); err != nil {
		return nil, err
	}
	task, err := requireText(brief.Get("task"), "task")
	if err != nil {
		return nil, err
	}
	summaryText, err := optionalText(brief.Get("summary"), "summary")
	if err != nil {
		return nil, err
	}
	plan, err := requireTextList(brief.Get("plan"), "plan", 2, 5)
	if err != nil {
		return nil, err
	}
	outcomes, err := requireTextList(brief.Get("outcomes"), "outcomes", 1, 5)
	if err != nil {
		return nil, err
	}
	actions, ok := asList(brief.Get("actions"))
	if !ok || len(actions) == 0 {
		return nil, errf("actions must contain at least one action")
	}
	events, ok := asList(summary.Get("events"))
	if !ok || len(events) == 0 {
		return nil, errf("recording-summary.json has no events")
	}
	first, ok := asObj(actions[0])
	if !ok {
		return nil, errf("actions[0] must be an object")
	}
	num, where := first.Get("event"), "actions[0].event"
	if first.Has("frameEvent") {
		num, where = first.Get("frameEvent"), "actions[0].frameEvent"
	}
	vpEvent, err := eventAt(events, num, where)
	if err != nil {
		return nil, err
	}
	viewport, _ := asObj(vpEvent.Get("viewport"))
	if !truthy(viewport.Get("w")) || !truthy(viewport.Get("h")) {
		return nil, errf("recording-summary.json has no viewport")
	}
	firstTS := 0.0
	for _, e := range events {
		o, _ := asObj(e)
		if ts, ok := asNum(o.Get("ts")); ok {
			firstTS = ts
			break
		}
	}

	privacy, ok := asObj(brief.Get("privacy"))
	if !ok {
		return nil, errf("privacy must be an object")
	}
	if err := rejectUnknown(privacy, privacyKeys, "privacy"); err != nil {
		return nil, err
	}
	reviewedRaw, ok := asList(privacy.Get("reviewedFrames"))
	var reviewed []string
	for _, f := range reviewedRaw {
		s, isStr := f.(string)
		ok = ok && isStr
		reviewed = append(reviewed, s)
	}
	if !ok {
		return nil, errf("privacy.reviewedFrames must be a list of frame names")
	}
	redact := Obj{}
	if r := privacy.Get("redact"); truthy(r) {
		if redact, ok = asObj(r); !ok {
			return nil, errf("privacy.redact must be an object")
		}
	}

	var explanations []any
	if e := brief.Get("explanations"); truthy(e) {
		if explanations, ok = asList(e); !ok {
			return nil, errf("explanations must be a list")
		}
	}
	pacing, _ := asObj(style.Get("pacing"))
	wpm := mustFloat(style.Get("readingWpm"))
	byAction := map[int][]Obj{}
	for i, eV := range explanations {
		at := func(s string) string { return fmt.Sprintf("explanations[%d]%s", i, s) }
		e, ok := asObj(eV)
		if !ok {
			return nil, errf("%s must be an object", at(""))
		}
		if err := rejectUnknown(e, explanationKeys, at("")); err != nil {
			return nil, err
		}
		after, ok := asInt(e.Get("afterAction"))
		if !ok || after < 1 || after > len(actions) {
			return nil, errf("%s must index actions", at(".afterAction"))
		}
		title, err := requireText(e.Get("title"), at(".title"))
		if err != nil {
			return nil, err
		}
		sub, err := optionalText(e.Get("summary"), at(".summary"))
		if err != nil {
			return nil, err
		}
		var points []any
		var details []string
		for _, p := range [][2]string{{"Observed", "observed"}, {"Mistake", "mistake"}, {"Correction", "correction"}} {
			text, err := requireText(e.Get(p[1]), at("."+p[1]))
			if err != nil {
				return nil, err
			}
			points = append(points, Obj{{K: "label", V: p[0]}, {K: "text", V: text}})
			details = append(details, p[0], text)
		}
		card := withSub(Obj{{K: "card", V: true}, {K: "kind", V: "explanation"}, {K: "title", V: title}}, sub)
		card = append(card, pyjson.KV{K: "points", V: points}, pyjson.KV{K: "dur", V: cardDuration(title, sub, details, "explanation", wpm)})
		byAction[after] = append(byAction[after], card)
	}

	intro := withSub(Obj{{K: "card", V: true}, {K: "kind", V: "intro"}, {K: "title", V: task}}, summaryText)
	intro = append(intro, pyjson.KV{K: "dur", V: cardDuration(task, summaryText, plan, "intro", wpm)})
	beats := []Obj{intro}
	var prev *point
	for i, a := range actions {
		var beat Obj
		if beat, prev, err = compileAction(a, i, events, plan, firstTS, prev, viewport, pacing, revealed); err != nil {
			return nil, err
		}
		beats = append(beats, beat)
		beats = append(beats, byAction[i+1]...)
	}

	ot := brief.Get("outcomeTitle")
	if !truthy(ot) {
		ot = "Task complete"
	}
	outcomeTitle, err := requireText(ot, "outcomeTitle")
	if err != nil {
		return nil, err
	}
	outcomeSummary, err := optionalText(brief.Get("outcomeSummary"), "outcomeSummary")
	if err != nil {
		return nil, err
	}
	outcome := withSub(Obj{{K: "card", V: true}, {K: "kind", V: "outcome"}, {K: "title", V: outcomeTitle}}, outcomeSummary)
	outcome = append(outcome, pyjson.KV{K: "outcomes", V: strs(outcomes)}, pyjson.KV{K: "dur", V: cardDuration(outcomeTitle, outcomeSummary, outcomes, "outcome", wpm)})
	beats = append(beats, outcome)

	if err := validateNarrationCadence(beats); err != nil {
		return nil, err
	}
	raw := addRawToCardHolds(beats, pacing)
	budget := durationBudget(len(actions), len(explanations), raw, pacing)
	total := 0.0
	beatList := make([]any, len(beats))
	for i, b := range beats {
		total += mustFloat(b.Get("dur"))
		beatList[i] = b
	}
	if total = round(total); total > budget+0.001 {
		return nil, errf("compiled video is %.1fs; house-style budget is %.1fs. Shorten card copy, "+
			"remove redundant actions, or set narration only when the thought changes; viewers can pause for detail", total, budget)
	}

	hp, _ := asObj(style.Get("privacy"))
	comp := Obj{
		{K: "schemaVersion", V: style.Get("version")},
		{K: "viewport", V: Obj{{K: "w", V: viewport.Get("w")}, {K: "h", V: viewport.Get("h")}}},
		{K: "cursorStart", V: style.Get("cursorStart")},
		{K: "frameStyle", V: style.Get("frameStyle")},
		{K: "readingWpm", V: style.Get("readingWpm")},
		{K: "pacing", V: pacing},
		{K: "durationBudget", V: budget},
		{K: "bg", V: style.Get("background")},
		{K: "plan", V: strs(plan)},
		{K: "motion", V: style.Get("motion")},
		{K: "privacy", V: Obj{{K: "reviewedFrames", V: strs(reviewed)}, {K: "pad", V: hp.Get("pad")}, {K: "mask", V: hp.Get("mask")}}},
		{K: "redact", V: redact},
		{K: "beats", V: beatList},
	}
	if err := validatePrivacy(reviewed, redact, beatList); err != nil {
		return nil, err
	}
	return comp, nil
}

func writeComposition(path string, comp Obj) error {
	return writeText(path, "window.COMPOSITION = "+pyjson.DumpsUnicodeIndent(comp, 2)+";\n")
}

func readLines(path string) ([]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, errf("cannot read %s: %v", path, err)
	}
	s := strings.ReplaceAll(strings.ReplaceAll(string(raw), "\r\n", "\n"), "\r", "\n")
	s = strings.TrimSuffix(s, "\n")
	if s == "" {
		return nil, nil
	}
	return strings.Split(s, "\n"), nil
}

func loadRevealedText(path string) (map[int]string, error) {
	lines, err := readLines(path)
	if err != nil {
		return nil, err
	}
	out := map[int]string{}
	for i, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		v, err := pyjson.Loads([]byte(line))
		if err != nil {
			return nil, errf("cannot read %s: %v", path, err)
		}
		ev, _ := asObj(v)
		helper, _ := ev.Get("helper").(string)
		if typeHelpers[helper] && ev.Get("input") != "password" {
			if t := ev.Get("text"); t != nil {
				out[i+1] = pyStr(t)
			}
		}
	}
	return out, nil
}

func safeText(ev Obj) any {
	v := ev.Get("text")
	if v == nil {
		return nil
	}
	if h, _ := ev.Get("helper").(string); typeHelpers[h] {
		return "<typed text hidden>"
	}
	s := pyStr(v)
	if ev.Get("input") == "password" || sensitive.MatchString(s) {
		return "<sensitive>"
	}
	return cut(s, 120)
}

func safeLabel(v any) any {
	if v == nil {
		return nil
	}
	s := pyStr(v)
	if sensitive.MatchString(s) {
		return "<sensitive>"
	}
	return cut(s, 120)
}

func copyFile(src, dst string) error {
	raw, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, raw, 0o644)
}

func initRecording(rec string, requireExplicit bool) error {
	eventsPath := filepath.Join(rec, "events.jsonl")
	if fi, err := os.Stat(eventsPath); err != nil || !fi.Mode().IsRegular() {
		return errf("missing %s", eventsPath)
	}
	meta, hasMeta, err := loadMeta(rec)
	if err != nil {
		return err
	}
	if requireExplicit && (!hasMeta || meta.Get("auto") == true) {
		return errf("not an explicit recording; use the exact path returned by start_recording()")
	}
	if err := copyFile(templatePath(), filepath.Join(rec, "video.html")); err != nil {
		return err
	}
	lines, err := readLines(eventsPath)
	if err != nil {
		return err
	}
	events := []any{}
	for i, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		v, err := pyjson.Loads([]byte(line))
		if err != nil {
			return errf("cannot read %s: %v", eventsPath, err)
		}
		raw, ok := asObj(v)
		if !ok {
			return errf("cannot read %s: line %d is not an object", eventsPath, i+1)
		}
		if !truthy(raw.Get("frame")) {
			continue
		}
		var cursor any
		if raw.Get("x") != nil && raw.Get("y") != nil {
			cursor = Obj{{K: "x", V: raw.Get("x")}, {K: "y", V: raw.Get("y")}}
		}
		events = append(events, Obj{
			{K: "frame", V: raw.Get("frame")},
			{K: "sourceLine", V: i + 1},
			{K: "helper", V: raw.Get("helper")},
			{K: "ts", V: raw.Get("ts")},
			{K: "route", V: "Browser"},
			{K: "tab", V: safeLabel(raw.Get("title"))},
			{K: "viewport", V: Obj{{K: "w", V: raw.Get("w")}, {K: "h", V: raw.Get("h")}}},
			{K: "cursor", V: cursor},
			{K: "box", V: raw.Get("box")},
			{K: "text", V: safeText(raw)},
			{K: "textLength", V: len([]rune(orEmpty(raw.Get("text"))))},
			{K: "password", V: raw.Get("input") == "password"},
		})
	}
	summary := Obj{
		{K: "recording", V: filepath.Base(rec)},
		{K: "title", V: safeLabel(meta.Get("title"))},
		{K: "eventCount", V: len(events)},
		{K: "events", V: events},
	}
	out := filepath.Join(rec, "recording-summary.json")
	if err := writeText(out, pyjson.Dumps(summary, 2)+"\n"); err != nil {
		return err
	}
	if err := writeSourceManifest(rec); err != nil {
		return err
	}
	fmt.Printf("summary: %s\n", out)
	fmt.Printf("next: write %s, then run browser-harness video review\n", filepath.Join(rec, "edit-brief.json"))
	return nil
}

// templatePath is the renderer shipped in the Python package.
func templatePath() string {
	return filepath.Join(os.Getenv("BH_PACKAGE_DIR"), templateName)
}
