// Package video turns a recording into a short explainer video: init writes a
// summary, the agent writes edit-brief.json, review compiles and screenshots
// it, export records an MP4 through video-template.html.
package video

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"

	"github.com/browser-use/browser-harness/go/internal/assets"
)

var (
	sensitive   = regexp.MustCompile(`(?i)@|onmicrosoft\.com|(?:tenant|user|object)[_-]?id|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b`)
	routeUnsafe = regexp.MustCompile(`(?i)@|[?#]|://|onmicrosoft|(?:tenant|user|object)[_-]?id|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b`)
	opaqueHex   = regexp.MustCompile(`(?i)^#[0-9a-f]{6}$`)
)

type Point struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
}
type Box struct {
	X float64 `json:"x"`
	Y float64 `json:"y"`
	W float64 `json:"w"`
	H float64 `json:"h"`
}
type Size struct {
	W float64 `json:"w"`
	H float64 `json:"h"`
}

// Event is one captured frame in recording-summary.json.
type Event struct {
	Frame      string   `json:"frame"`
	SourceLine int      `json:"sourceLine"`
	Helper     string   `json:"helper"`
	TS         *float64 `json:"ts"`
	Tab        string   `json:"tab,omitempty"`
	Viewport   Size     `json:"viewport"`
	Cursor     *Point   `json:"cursor"`
	Box        *Box     `json:"box"`
	Text       *string  `json:"text"`
	TextLength int      `json:"textLength"`
	Password   bool     `json:"password"`
}

type Summary struct {
	Recording string  `json:"recording"`
	Title     string  `json:"title,omitempty"`
	Events    []Event `json:"events"`
}

// Brief is edit-brief.json, written by the agent. Unknown fields are rejected.
type Brief struct {
	Task           string        `json:"task"`
	Summary        string        `json:"summary"`
	Plan           []string      `json:"plan"`
	Actions        []Action      `json:"actions"`
	Explanations   []Explanation `json:"explanations"`
	OutcomeTitle   string        `json:"outcomeTitle"`
	OutcomeSummary string        `json:"outcomeSummary"`
	Outcomes       []string      `json:"outcomes"`
	Privacy        *Privacy      `json:"privacy"`
}

type Action struct {
	Event      int    `json:"event"`
	FrameEvent int    `json:"frameEvent"`
	AfterEvent int    `json:"afterEvent"`
	Chapter    *int   `json:"chapter"`
	Route      string `json:"route"`
	AfterRoute string `json:"afterRoute"`
	Narration  string `json:"narration"`
	Label      string `json:"label"`
	Detour     bool   `json:"detour"`
	Error      bool   `json:"error"`
	Context    bool   `json:"context"`
	ShowTyping bool   `json:"showTyping"`
}

type Explanation struct {
	AfterAction int    `json:"afterAction"`
	Title       string `json:"title"`
	Summary     string `json:"summary"`
	Observed    string `json:"observed"`
	Mistake     string `json:"mistake"`
	Correction  string `json:"correction"`
}

type Privacy struct {
	ReviewedFrames []string          `json:"reviewedFrames"`
	Redact         map[string][]Rect `json:"redact"`
}

// Rect is a privacy mask in viewport pixels; Fill and Stroke are hex or false.
type Rect struct {
	X      *float64 `json:"x"`
	Y      *float64 `json:"y"`
	W      *float64 `json:"w"`
	H      *float64 `json:"h"`
	Fill   any      `json:"fill,omitempty"`
	Stroke any      `json:"stroke,omitempty"`
	Radius *float64 `json:"radius,omitempty"`
	Pad    *float64 `json:"pad,omitempty"`
}

type Typing struct {
	Box    Box    `json:"box"`
	Text   string `json:"text"`
	Redact bool   `json:"redact,omitempty"`
}

type Label struct {
	Label string `json:"label"`
	Text  string `json:"text"`
}

// Beat is one card or action in the composition the template plays.
type Beat struct {
	Card         bool     `json:"card,omitempty"`
	Kind         string   `json:"kind,omitempty"`
	Title        string   `json:"title,omitempty"`
	Sub          string   `json:"sub,omitempty"`
	Points       []Label  `json:"points,omitempty"`
	Outcomes     []string `json:"outcomes,omitempty"`
	Frame        string   `json:"frame,omitempty"`
	Route        string   `json:"route,omitempty"`
	Chapter      *int     `json:"chapter,omitempty"`
	After        string   `json:"after,omitempty"`
	AfterRoute   string   `json:"afterRoute,omitempty"`
	Narration    string   `json:"narration,omitempty"`
	Label        string   `json:"label,omitempty"`
	Detour       bool     `json:"detour,omitempty"`
	Error        bool     `json:"error,omitempty"`
	Cursor       *Point   `json:"cursor,omitempty"`
	Click        bool     `json:"click,omitempty"`
	Type         *Typing  `json:"type,omitempty"`
	Wide         bool     `json:"wide,omitempty"`
	CameraCut    bool     `json:"cameraCut,omitempty"`
	T            *float64 `json:"t,omitempty"`
	Dur          float64  `json:"dur"`
	EndStateHold float64  `json:"endStateHold,omitempty"`
}

type Pacing struct {
	CaptionBaseSeconds      float64 `json:"captionBaseSeconds"`
	CaptionSecondsPerWord   float64 `json:"captionSecondsPerWord"`
	RawToCardHoldSeconds    float64 `json:"rawToCardHoldSeconds"`
	BaseDurationBudget      float64 `json:"baseDurationBudget"`
	ExtraActionSeconds      float64 `json:"extraActionSeconds"`
	ExtraExplanationSeconds float64 `json:"extraExplanationSeconds"`
	MaximumDurationBudget   float64 `json:"maximumDurationBudget"`
}

type Mask struct {
	Fill   string  `json:"fill"`
	Stroke bool    `json:"stroke"`
	Radius float64 `json:"radius"`
}

type Composition struct {
	SchemaVersion  int               `json:"schemaVersion"`
	Viewport       Size              `json:"viewport"`
	CursorStart    Point             `json:"cursorStart"`
	FrameStyle     string            `json:"frameStyle"`
	ReadingWpm     float64           `json:"readingWpm"`
	Pacing         Pacing            `json:"pacing"`
	DurationBudget float64           `json:"durationBudget"`
	Bg             []string          `json:"bg"`
	Plan           []string          `json:"plan"`
	Motion         map[string]any    `json:"motion"`
	Privacy        CompPrivacy       `json:"privacy"`
	Redact         map[string][]Rect `json:"redact"`
	Beats          []Beat            `json:"beats"`
}

type CompPrivacy struct {
	ReviewedFrames []string `json:"reviewedFrames"`
	Pad            float64  `json:"pad"`
	Mask           Mask     `json:"mask"`
}

// House style.
const readingWpm = 380

var (
	pacing = Pacing{0.35, 0.2, 0.55, 22, 1.25, 3, 32}
	motion = map[string]any{"autoFollow": true, "autoZoom": 1.7, "cursorDuration": 0.48, "zoomDuration": 0.42,
		"panDuration": 0.55, "wideScale": 0.78, "reactionLag": 0.025, "reactionFade": 0.04}
)

var typeHelpers = map[string]bool{"type_text": true, "fill": true, "fill_input": true}

func round3(x float64) float64 { return math.Round(x*1000) / 1000 }
func words(s string) int       { return len(strings.Fields(s)) }

func cardDuration(kind string, parts ...string) float64 {
	base := 4.0
	if kind != "explanation" {
		base = 4.5
	}
	return round3(math.Max(base, 0.4+float64(words(strings.Join(parts, " ")))*60/readingWpm))
}

func text(s, where string) (string, error) {
	if s = strings.TrimSpace(s); s == "" {
		return "", fmt.Errorf("%s must be non-empty text", where)
	}
	return s, nil
}

func textList(list []string, where string, low, high int) error {
	if len(list) < low || len(list) > high {
		return fmt.Errorf("%s must contain %d–%d items", where, low, high)
	}
	for i, s := range list {
		if strings.TrimSpace(s) == "" {
			return fmt.Errorf("%s[%d] must be non-empty text", where, i)
		}
	}
	return nil
}

func eventAt(events []Event, n int, where string) (Event, error) {
	if n < 1 || n > len(events) {
		return Event{}, fmt.Errorf("%s must be a one-based index into recording-summary.json", where)
	}
	if events[n-1].Frame == "" {
		return Event{}, fmt.Errorf("%s has no captured frame", where)
	}
	if events[n-1].Viewport.W <= 0 || events[n-1].Viewport.H <= 0 {
		return Event{}, fmt.Errorf("%s has no valid viewport", where)
	}
	return events[n-1], nil
}

func (e Event) target() *Point {
	if e.Cursor != nil {
		return e.Cursor
	}
	if e.Box != nil {
		return &Point{e.Box.X + e.Box.W*0.3, e.Box.Y + e.Box.H/2}
	}
	return nil
}

func actionDuration(b Beat) float64 {
	d := 0.7
	if b.Click {
		d = 1.15
	}
	if b.After != "" {
		d = math.Max(d, 1.4)
	}
	if b.Type != nil {
		d = math.Max(d, 0.6+float64(len([]rune(b.Type.Text)))*0.035)
	}
	if b.Narration != "" {
		d = math.Max(d, pacing.CaptionBaseSeconds+pacing.CaptionSecondsPerWord*float64(words(b.Narration)))
	}
	return round3(d)
}

// compile validates the brief against the recording and builds the composition.
func compile(sum Summary, br Brief, revealed map[int]string) (*Composition, error) {
	task, err := text(br.Task, "task")
	if err != nil {
		return nil, err
	}
	if err := textList(br.Plan, "plan", 2, 5); err != nil {
		return nil, err
	}
	if err := textList(br.Outcomes, "outcomes", 1, 5); err != nil {
		return nil, err
	}
	if len(br.Actions) == 0 {
		return nil, errors.New("actions must contain at least one action")
	}
	if len(sum.Events) == 0 {
		return nil, errors.New("recording-summary.json has no events")
	}
	if br.Privacy == nil {
		return nil, errors.New("privacy must be an object")
	}
	first := br.Actions[0].FrameEvent
	if first == 0 {
		first = br.Actions[0].Event
	}
	vpEvent, err := eventAt(sum.Events, first, "actions[0].event")
	if err != nil {
		return nil, err
	}
	vp := vpEvent.Viewport
	firstTS := 0.0
	for _, e := range sum.Events {
		if e.TS != nil {
			firstTS = *e.TS
			break
		}
	}

	byAction := map[int][]Beat{}
	for i, ex := range br.Explanations {
		where := fmt.Sprintf("explanations[%d]", i)
		if ex.AfterAction < 1 || ex.AfterAction > len(br.Actions) {
			return nil, fmt.Errorf("%s.afterAction must index actions", where)
		}
		card := Beat{Card: true, Kind: "explanation", Sub: strings.TrimSpace(ex.Summary)}
		parts := []string{}
		for _, f := range []struct{ label, value, key string }{
			{"", ex.Title, "title"}, {"Observed", ex.Observed, "observed"},
			{"Mistake", ex.Mistake, "mistake"}, {"Correction", ex.Correction, "correction"}} {
			v, err := text(f.value, where+"."+f.key)
			if err != nil {
				return nil, err
			}
			if f.label == "" {
				card.Title = v
				parts = append(parts, v, card.Sub)
				continue
			}
			card.Points = append(card.Points, Label{f.label, v})
			parts = append(parts, f.label, v)
		}
		card.Dur = cardDuration("explanation", parts...)
		byAction[ex.AfterAction] = append(byAction[ex.AfterAction], card)
	}

	summary := strings.TrimSpace(br.Summary)
	beats := []Beat{{Card: true, Kind: "intro", Title: task, Sub: summary,
		Dur: cardDuration("intro", append([]string{task, summary}, br.Plan...)...)}}
	var prev *Point
	for i, a := range br.Actions {
		b, target, err := compileAction(a, fmt.Sprintf("actions[%d]", i), sum.Events, len(br.Plan), firstTS, prev, vp, revealed)
		if err != nil {
			return nil, err
		}
		if target != nil {
			prev = target
		}
		beats = append(beats, b)
		beats = append(beats, byAction[i+1]...)
	}
	outcome := strings.TrimSpace(br.OutcomeTitle)
	if outcome == "" {
		outcome = "Task complete"
	}
	outSub := strings.TrimSpace(br.OutcomeSummary)
	beats = append(beats, Beat{Card: true, Kind: "outcome", Title: outcome, Sub: outSub, Outcomes: br.Outcomes,
		Dur: cardDuration("outcome", append([]string{outcome, outSub}, br.Outcomes...)...)})

	if err := checkNarrationCadence(beats); err != nil {
		return nil, err
	}
	holds := 0
	for i := 0; i+1 < len(beats); i++ {
		if !beats[i].Card && beats[i+1].Card {
			beats[i].EndStateHold = pacing.RawToCardHoldSeconds
			beats[i].Dur = round3(beats[i].Dur + pacing.RawToCardHoldSeconds)
			holds++
		}
	}
	budget := pacing.BaseDurationBudget + float64(max(0, len(br.Actions)-5))*pacing.ExtraActionSeconds +
		float64(max(0, len(br.Explanations)-1))*pacing.ExtraExplanationSeconds + float64(holds)*pacing.RawToCardHoldSeconds
	budget = round3(math.Min(budget, pacing.MaximumDurationBudget))
	if total := duration(beats); total > budget+0.001 {
		return nil, fmt.Errorf("compiled video is %.1fs; house-style budget is %.1fs. Shorten card copy, remove "+
			"redundant actions, or set narration only when the thought changes; viewers can pause for detail", total, budget)
	}
	c := &Composition{
		SchemaVersion: 1, Viewport: vp, CursorStart: Point{700, 280}, FrameStyle: "native", ReadingWpm: readingWpm,
		Pacing: pacing, DurationBudget: budget, Bg: []string{"#efece4", "#dce7e7"}, Plan: br.Plan, Motion: motion,
		Privacy: CompPrivacy{br.Privacy.ReviewedFrames, 10, Mask{Fill: "#ffffff"}},
		Redact:  br.Privacy.Redact, Beats: beats,
	}
	if c.Redact == nil {
		c.Redact = map[string][]Rect{}
	}
	return c, checkPrivacy(c)
}

func compileAction(a Action, where string, events []Event, chapters int, firstTS float64, prev *Point, vp Size,
	revealed map[int]string) (Beat, *Point, error) {
	ev, err := eventAt(events, a.Event, where+".event")
	if err != nil {
		return Beat{}, nil, err
	}
	frame := ev
	if a.FrameEvent != 0 {
		if frame, err = eventAt(events, a.FrameEvent, where+".frameEvent"); err != nil {
			return Beat{}, nil, err
		}
	}
	for _, e := range []Event{ev, frame} {
		if math.Abs(e.Viewport.W-vp.W) > 2 || math.Abs(e.Viewport.H-vp.H) > 2 {
			return Beat{}, nil, fmt.Errorf("%s uses a different viewport; split or normalize the recording first", where)
		}
	}
	if a.Chapter == nil || *a.Chapter < 0 || *a.Chapter >= chapters {
		return Beat{}, nil, fmt.Errorf("%s.chapter must index plan", where)
	}
	b := Beat{Frame: frame.Frame, Chapter: a.Chapter, Label: strings.TrimSpace(a.Label), Detour: a.Detour, Error: a.Error}
	if b.Route, err = text(a.Route, where+".route"); err != nil {
		return Beat{}, nil, err
	}
	if routeUnsafe.MatchString(b.Route) || routeUnsafe.MatchString(a.AfterRoute) {
		return Beat{}, nil, fmt.Errorf("%s routes must be semantic, not a raw URL or identity", where)
	}
	if a.AfterEvent != 0 {
		after, err := eventAt(events, a.AfterEvent, where+".afterEvent")
		if err != nil {
			return Beat{}, nil, err
		}
		b.After, b.AfterRoute = after.Frame, strings.TrimSpace(a.AfterRoute)
	}
	if words(a.Narration) > 7 {
		return Beat{}, nil, fmt.Errorf("%s.narration exceeds seven words", where)
	}
	b.Narration = strings.TrimSpace(a.Narration)

	switch {
	case ev.Helper == "click_at_xy":
		if ev.Cursor == nil {
			return Beat{}, nil, fmt.Errorf("%s identifies a click without captured coordinates", where)
		}
		b.Cursor, b.Click = ev.Cursor, true
	case typeHelpers[ev.Helper]:
		if ev.Box == nil {
			return Beat{}, nil, fmt.Errorf("%s identifies typing without a captured box", where)
		}
		b.Type = &Typing{Box: *ev.Box, Text: "••••••", Redact: true}
		if a.ShowTyping {
			t, ok := revealed[ev.SourceLine]
			if ev.Password || !ok {
				return Beat{}, nil, fmt.Errorf("%s.showTyping can only reveal non-password typed text", where)
			}
			b.Type = &Typing{Box: *ev.Box, Text: t}
		}
	case a.ShowTyping:
		return Beat{}, nil, fmt.Errorf("%s.showTyping requires a typing event", where)
	}

	target := ev.target()
	if a.Context && !b.Click && b.Type == nil {
		b.Wide = true
	} else if target != nil && prev != nil &&
		math.Hypot(target.X-prev.X, target.Y-prev.Y) > math.Hypot(vp.W, vp.H)*0.58 {
		b.CameraCut = true
	}
	if ev.TS != nil {
		t := round3(math.Max(0, *ev.TS-firstTS))
		b.T = &t
	}
	b.Dur = actionDuration(b)
	return b, target, nil
}

// checkNarrationCadence keeps narration sticky instead of mirroring every frame.
func checkNarrationCadence(beats []Beat) error {
	cues, segment, consecutive := 0, 0, 0
	flush := func() error {
		if segment >= 3 && cues > (segment+1)/2 {
			return errors.New("narration is sticky: set it only when the thought changes, then omit it while 2–3 screenshots advance underneath")
		}
		segment, cues = 0, 0
		return nil
	}
	for _, b := range beats {
		if b.Card {
			if err := flush(); err != nil {
				return err
			}
			consecutive = 0
			continue
		}
		segment++
		if b.Narration != "" {
			cues++
			consecutive++
		} else {
			consecutive = 0
		}
		if consecutive >= 3 {
			return errors.New("three consecutive actions change narration; omit narration on intervening actions so text and screenshots use different pacing")
		}
	}
	return flush()
}

func duration(beats []Beat) float64 {
	t := 0.0
	for _, b := range beats {
		t += b.Dur
	}
	return round3(t)
}

func usedFrames(beats []Beat) []string {
	var out []string
	seen := map[string]bool{}
	for _, b := range beats {
		for _, f := range []string{b.Frame, b.After} {
			if f != "" && !seen[f] {
				seen[f] = true
				out = append(out, f)
			}
		}
	}
	return out
}

func checkPrivacy(c *Composition) error {
	frames := usedFrames(c.Beats)
	reviewed := map[string]bool{}
	for _, f := range c.Privacy.ReviewedFrames {
		if reviewed[f] {
			return errors.New("privacy.reviewedFrames contains duplicates")
		}
		reviewed[f] = true
	}
	var missing []string
	for _, f := range frames {
		if !reviewed[f] {
			missing = append(missing, f)
		}
	}
	if len(missing) > 0 {
		return errors.New("privacy review missing: " + strings.Join(missing, ", "))
	}
	for frame, rects := range c.Redact {
		if !slices.Contains(frames, frame) {
			return fmt.Errorf("privacy.redact lists unused frame %s", frame)
		}
		for i, r := range rects {
			where := fmt.Sprintf("privacy.redact.%s[%d]", frame, i)
			if r.X == nil || r.Y == nil || r.W == nil || r.H == nil || *r.W <= 0 || *r.H <= 0 {
				return fmt.Errorf("%s needs x, y and a positive w and h", where)
			}
			for _, v := range []any{r.Fill, r.Stroke} {
				if s, ok := v.(string); v != nil && v != false && (!ok || !opaqueHex.MatchString(s)) {
					return fmt.Errorf("%s fill and stroke must be false or opaque six-digit hex", where)
				}
			}
		}
	}
	return nil
}

// --- files ---

func readJSON(path string, v any) error {
	raw, err := os.ReadFile(path) //nolint:gosec // Read a file from the selected local recording.
	if err != nil {
		return err
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if err := d.Decode(v); err != nil {
		return fmt.Errorf("%s: %w", filepath.Base(path), err)
	}
	return nil
}

func writeJSON(path string, v any) error {
	raw, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

func renderComposition(c *Composition) []byte {
	raw, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return nil
	}
	return []byte("window.COMPOSITION = " + string(raw) + ";\n")
}

func fileHash(path string) (string, error) {
	raw, err := os.ReadFile(path) //nolint:gosec // Hash a file from the selected local recording.
	if err != nil {
		return "", err
	}
	return sha(raw), nil
}

func sha(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// sourceHashes covers everything the brief was written against.
func sourceHashes(rec string) (map[string]string, error) {
	names := []string{"events.jsonl", "meta.json", "recording-summary.json"}
	frames, _ := filepath.Glob(filepath.Join(rec, "[0-9]*.jpg"))
	for _, f := range frames {
		names = append(names, filepath.Base(f))
	}
	return hashes(rec, names, true)
}

// hashes is the SHA-256 of each named file in rec; a missing file is an error unless optional.
func hashes(rec string, names []string, optional bool) (map[string]string, error) {
	out := map[string]string{}
	for _, n := range names {
		h, err := fileHash(filepath.Join(rec, n))
		if optional && errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			return nil, err
		}
		out[n] = h
	}
	return out, nil
}

func verifySources(rec string) error {
	var want map[string]string
	if err := readJSON(filepath.Join(rec, "video-source.json"), &want); err != nil {
		return err
	}
	got, err := sourceHashes(rec)
	if err != nil {
		return err
	}
	if len(got) != len(want) {
		return errors.New("recording source files changed after init")
	}
	for n, h := range got {
		if want[n] != h {
			return fmt.Errorf("recording source changed after init: %s", n)
		}
	}
	return nil
}

type rawEvent struct {
	Helper string   `json:"helper"`
	TS     *float64 `json:"ts"`
	Title  string   `json:"title"`
	W      float64  `json:"w"`
	H      float64  `json:"h"`
	X      *float64 `json:"x"`
	Y      *float64 `json:"y"`
	Box    *Box     `json:"box"`
	Text   *string  `json:"text"`
	Input  string   `json:"input"`
	Frame  string   `json:"frame"`
}

func readEvents(rec string) ([]rawEvent, error) {
	f, err := os.Open(filepath.Join(rec, "events.jsonl")) //nolint:gosec // Read events from the selected local recording.
	if err != nil {
		return nil, err
	}
	defer func() { _ = f.Close() }()
	var out []rawEvent
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<24)
	for sc.Scan() {
		var e rawEvent
		if line := strings.TrimSpace(sc.Text()); line != "" {
			if err := json.Unmarshal([]byte(line), &e); err != nil {
				return nil, fmt.Errorf("events.jsonl line %d: %w", len(out)+1, err)
			}
		}
		out = append(out, e)
	}
	return out, sc.Err()
}

// revealedText maps events.jsonl line numbers to typed non-password text.
func revealedText(rec string) (map[int]string, error) {
	events, err := readEvents(rec)
	out := map[int]string{}
	for i, e := range events {
		if typeHelpers[e.Helper] && e.Input != "password" && e.Text != nil {
			out[i+1] = *e.Text
		}
	}
	return out, err
}

func safe(s string) string {
	if sensitive.MatchString(s) {
		return "<sensitive>"
	}
	return cut(s, 120)
}

func cut(s string, n int) string {
	if r := []rune(s); len(r) > n {
		return string(r[:n])
	}
	return s
}

func initRecording(rec string, requireExplicit bool) error {
	var meta struct {
		Title string `json:"title"`
		Auto  bool   `json:"auto"`
	}
	metaErr := readJSONLoose(filepath.Join(rec, "meta.json"), &meta)
	if requireExplicit && (metaErr != nil || meta.Auto) {
		return errors.New("not an explicit recording; use the exact path returned by start_recording()")
	}
	raw, err := readEvents(rec)
	if err != nil {
		return err
	}
	sum := Summary{Recording: filepath.Base(rec), Title: safe(meta.Title), Events: []Event{}}
	for i, r := range raw {
		if r.Frame == "" {
			continue
		}
		e := Event{Frame: r.Frame, SourceLine: i + 1, Helper: r.Helper, TS: r.TS, Tab: safe(r.Title),
			Viewport: Size{r.W, r.H}, Box: r.Box, Password: r.Input == "password"}
		if r.X != nil && r.Y != nil {
			e.Cursor = &Point{*r.X, *r.Y}
		}
		if r.Text != nil {
			e.TextLength = len([]rune(*r.Text))
			t := "<typed text hidden>"
			if !typeHelpers[r.Helper] {
				t = safe(*r.Text)
			}
			e.Text = &t
		}
		sum.Events = append(sum.Events, e)
	}
	if err := os.WriteFile(filepath.Join(rec, "video.html"), assets.VideoTemplate, 0o644); err != nil {
		return err
	}
	out := filepath.Join(rec, "recording-summary.json")
	if err := writeJSON(out, sum); err != nil {
		return err
	}
	hashes, err := sourceHashes(rec)
	if err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(rec, "video-source.json"), hashes); err != nil {
		return err
	}
	fmt.Printf("summary: %s\nnext: write %s, then run browser-harness video review\n", out, filepath.Join(rec, "edit-brief.json"))
	return nil
}

func readJSONLoose(path string, v any) error {
	raw, err := os.ReadFile(path) //nolint:gosec // Read a file from the selected local recording.
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, v)
}

// compileRecording compiles edit-brief.json and returns the composition file bytes.
func compileRecording(rec string) (*Composition, []byte, error) {
	if err := verifySources(rec); err != nil {
		return nil, nil, err
	}
	var sum Summary
	if err := readJSONLoose(filepath.Join(rec, "recording-summary.json"), &sum); err != nil {
		return nil, nil, err
	}
	var br Brief
	if err := readJSON(filepath.Join(rec, "edit-brief.json"), &br); err != nil {
		return nil, nil, err
	}
	revealed, err := revealedText(rec)
	if err != nil {
		return nil, nil, err
	}
	c, err := compile(sum, br, revealed)
	if err != nil {
		return nil, nil, err
	}
	return c, renderComposition(c), nil
}
