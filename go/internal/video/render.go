package video

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/jpeg"
	_ "image/png"
	"math"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"golang.org/x/image/draw"
	"golang.org/x/image/font"
	"golang.org/x/image/font/basicfont"
	"golang.org/x/image/math/fixed"

	"github.com/browser-use/browser-harness/go/internal/admin"
	"github.com/browser-use/browser-harness/go/internal/pyjson"
)

const marker = "__BH_VIDEO_RESULT__="

var reviewArtifacts = []string{"composition.js", "edit-brief.json", "recording-summary.json", sourceManifest, "video.html"}

var obsoleteReviewFiles = []string{
	"privacy-contact-sheet.jpg", "renderer-normal-contact-sheet.jpg", "renderer-reduced-contact-sheet.jpg",
	"renderer-click-contact-sheet.jpg", "video-audit.json",
}

func compileRecording(rec string, write bool) (Obj, error) {
	if err := verifySourceManifest(rec); err != nil {
		return nil, err
	}
	summary, err := loadJSON(filepath.Join(rec, "recording-summary.json"))
	if err != nil {
		return nil, err
	}
	brief, err := loadJSON(filepath.Join(rec, "edit-brief.json"))
	if err != nil {
		return nil, err
	}
	revealed, err := loadRevealedText(filepath.Join(rec, "events.jsonl"))
	if err != nil {
		return nil, err
	}
	comp, err := compileBrief(summary, brief, houseStyle, revealed)
	if err != nil {
		return nil, err
	}
	if write {
		err = writeComposition(filepath.Join(rec, "composition.js"), comp)
	}
	return comp, err
}

func beatsOf(comp Obj) []any { b, _ := asList(comp.Get("beats")); return b }

func totalDuration(comp Obj) float64 {
	t := 0.0
	for _, b := range beatsOf(comp) {
		o, _ := asObj(b)
		t += mustFloat(o.Get("dur"))
	}
	return t
}

// reviewSamples picks one stable state per beat, plus every explanation reveal.
func reviewSamples(comp Obj) []any {
	samples := []any{}
	start := 0.0
	for i, bv := range beatsOf(comp) {
		beat, _ := asObj(bv)
		dur := mustFloat(beat.Get("dur"))
		points, _ := asList(beat.Get("points"))
		if beat.Get("kind") == "explanation" && len(points) > 0 {
			first, finalHold := 1.1, 3.0
			span := math.Max(0, dur-first-finalHold)
			gap := span / float64(max(1, len(points)-1))
			for pi, pv := range points {
				p, _ := asObj(pv)
				local := math.Min(math.Max(0.05, dur-0.05), first+float64(pi)*gap+0.2)
				label := pyStr(p.Get("label"))
				if !truthy(p.Get("label")) {
					label = strconv.Itoa(pi + 1)
				}
				samples = append(samples, Obj{{K: "time", V: round(start + local)}, {K: "label", V: fmt.Sprintf("beat %d · %s", i+1, label)}})
			}
		} else {
			want := math.Max(0.12, math.Min(0.5, dur/2))
			if truthy(beat.Get("card")) {
				want = 1.0
			}
			local := math.Min(math.Max(0.05, dur-0.05), want)
			samples = append(samples, Obj{{K: "time", V: round(start + local)}, {K: "label", V: fmt.Sprintf("beat %d", i+1)}})
		}
		start += dur
	}
	return samples
}

// serve exposes the recording on a loopback port for the renderer page.
func serve(rec string) (string, func(), error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	srv := &http.Server{Handler: http.FileServer(http.Dir(rec))}
	go func() { _ = srv.Serve(l) }()
	url := fmt.Sprintf("http://127.0.0.1:%d/video.html", l.Addr().(*net.TCPAddr).Port)
	return url, func() { _ = srv.Close() }, nil
}

// runHarness runs a snippet against the daemon and returns its marker line; a seam for tests.
var runHarness = func(code string, timeout time.Duration) (Obj, error) {
	if err := admin.EnsureDaemon(-1, "", nil); err != nil {
		return nil, fmt.Errorf("browser review failed: %v", err)
	}
	py := os.Getenv("BH_PYTHON")
	if py == "" {
		py = "python3"
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, py, "-m", "browser_harness.runner")
	cmd.Stdin = strings.NewReader(code)
	cmd.Env = append(os.Environ(), "BH_RECORD=0")
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = strings.TrimSpace(stdout.String())
		}
		if detail == "" {
			detail = err.Error()
		}
		return nil, fmt.Errorf("browser review failed: %s", detail)
	}
	lines := strings.Split(stdout.String(), "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		if rest, ok := strings.CutPrefix(strings.TrimRight(lines[i], "\r"), marker); ok {
			v, err := pyjson.Loads([]byte(rest))
			if err != nil {
				return nil, err
			}
			o, _ := asObj(v)
			return o, nil
		}
	}
	out := stdout.String()
	if len(out) > 1000 {
		out = out[len(out)-1000:]
	}
	return nil, fmt.Errorf("browser review returned no result: %s", out)
}

// pyLiteral embeds v as json.loads("<json>") source.
func pyLiteral(v any) string {
	inner, _ := json.Marshal(v)
	outer, _ := json.Marshal(string(inner))
	return "json.loads(" + string(outer) + ")"
}

const reviewSnippet = `
import json, os, time
cfg = %s
os.makedirs(cfg['reviewDir'], exist_ok=True)

def ready():
    for _ in range(100):
        if js('window.videoReady && window.videoReady()'):
            return
        time.sleep(0.05)
    raise RuntimeError('video assets did not become ready')

def inspect_mode(name, reduced):
    features = [{'name':'prefers-reduced-motion','value':'reduce'}] if reduced else []
    cdp('Emulation.setEmulatedMedia', media='', features=features)
    cdp('Page.reload', ignoreCache=True)
    wait_for_load()
    ready()
    preflight = js('window.videoPreflight()')
    clicks = js('window.clickVisibility()')
    captures = []
    for index, sample in enumerate(cfg['samples'], 1):
        js(f"window.seek({sample['time']})")
        path = f"{cfg['reviewDir']}/{name}-beat-{index:02d}.png"
        capture_screenshot(path)
        captures.append({'path': path, 'time': sample['time'], 'label': sample['label']})
    click_captures = []
    for index, click in enumerate(clicks, 1):
        for state, key in (('click', 'time'), ('result', 'resultTime')):
            js(f"window.seek({click[key]})")
            path = f"{cfg['reviewDir']}/{name}-click-{index:02d}-{state}.png"
            capture_screenshot(path)
            click_captures.append({
                'path': path, 'time': click[key],
                'label': f"beat {click['beat']} · {state}",
            })
    return {'preflight': preflight, 'clicks': clicks, 'captures': captures,
            'clickCaptures': click_captures}

try:
    previous = current_tab()['targetId']
except Exception:
    previous = None
target = None
try:
    target = new_tab()
    goto_url(cfg['url'])
    wait_for_load()
    ready()
    normal = inspect_mode('normal', False)
    reduced = inspect_mode('reduced', True)
    print(cfg['marker'] + json.dumps({'normal': normal, 'reduced': reduced}))
finally:
    try:
        cdp('Emulation.setEmulatedMedia', media='', features=[])
    except Exception:
        pass
    try:
        switch_tab(previous) if previous else new_tab()
    except Exception:
        try:
            new_tab()
        except Exception:
            pass
    if target is not None:
        try:
            close_tab(target)
        except Exception:
            pass
`

func reviewBrowser(rec, url string, samples []any) (Obj, error) {
	cfg := Obj{{K: "url", V: url}, {K: "samples", V: samples}, {K: "reviewDir", V: filepath.Join(rec, ".renderer-review")}, {K: "marker", V: marker}}
	code := fmt.Sprintf(reviewSnippet, pyLiteral(json.RawMessage(pyjson.Dumps(cfg, 0))))
	return runHarness(code, time.Duration(max(60, len(samples)*3))*time.Second)
}

func hexColor(s string) color.RGBA {
	v, _ := strconv.ParseUint(strings.TrimPrefix(s, "#"), 16, 32)
	return color.RGBA{uint8(v >> 16), uint8(v >> 8), uint8(v), 255}
}

func loadRGB(path string) (*image.RGBA, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	src, _, err := image.Decode(f)
	if err != nil {
		return nil, fmt.Errorf("%s: %v", path, err)
	}
	dst := image.NewRGBA(image.Rect(0, 0, src.Bounds().Dx(), src.Bounds().Dy()))
	draw.Draw(dst, dst.Bounds(), src, src.Bounds().Min, draw.Src)
	return dst, nil
}

func saveJPEG(path string, img image.Image, quality int) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	if err := jpeg.Encode(f, img, &jpeg.Options{Quality: quality}); err != nil {
		f.Close()
		return err
	}
	return f.Close()
}

func drawText(img *image.RGBA, x, y int, text string, c color.Color) {
	d := font.Drawer{Dst: img, Src: image.NewUniform(c), Face: basicfont.Face7x13,
		Dot: fixed.P(x, y+basicfont.Face7x13.Ascent)}
	d.DrawString(text)
}

type capture struct {
	Path  string
	Time  float64
	Label string
}

func contactSheet(caps []capture, output, title string) error {
	const cols, tileW, tileH, labelH, gap, banner = 4, 400, 225, 34, 8, 42
	rows := max(1, (len(caps)+cols-1)/cols)
	sheet := image.NewRGBA(image.Rect(0, 0, cols*tileW+(cols+1)*gap, banner+rows*(tileH+labelH+gap)+gap))
	draw.Draw(sheet, sheet.Bounds(), image.NewUniform(hexColor("#171a20")), image.Point{}, draw.Src)
	drawText(sheet, gap, 15, title, color.White)
	for i, c := range caps {
		img, err := loadRGB(c.Path)
		if err != nil {
			return err
		}
		scale := math.Min(float64(tileW)/float64(img.Bounds().Dx()), float64(tileH)/float64(img.Bounds().Dy()))
		w, h := int(math.Round(float64(img.Bounds().Dx())*scale)), int(math.Round(float64(img.Bounds().Dy())*scale))
		col, row := i%cols, i/cols
		x, y := gap+col*(tileW+gap), banner+gap+row*(tileH+labelH+gap)
		px := x + (tileW-w)/2
		draw.CatmullRom.Scale(sheet, image.Rect(px, y, px+w, y+h), img, img.Bounds(), draw.Src, nil)
		drawText(sheet, x, y+tileH+9, fmt.Sprintf("%s  %.2fs", c.Label, c.Time), hexColor("#d7dbe3"))
	}
	return saveJPEG(output, sheet, 91)
}

// insideRounded reports whether pixel centre (px, py) lies in the rounded rectangle.
func insideRounded(px, py, x0, y0, x1, y1, r float64) bool {
	if px < x0 || px > x1 || py < y0 || py > y1 {
		return false
	}
	r = math.Min(r, math.Min((x1-x0)/2, (y1-y0)/2))
	cx := math.Max(x0+r, math.Min(px, x1-r))
	cy := math.Max(y0+r, math.Min(py, y1-r))
	return math.Hypot(px-cx, py-cy) <= r
}

func maskedFrame(rec string, comp Obj, frame string) (*image.RGBA, error) {
	vp, _ := asObj(comp.Get("viewport"))
	vw, vh := mustFloat(vp.Get("w")), mustFloat(vp.Get("h"))
	redactions, _ := asObj(comp.Get("redact"))
	privacy, _ := asObj(comp.Get("privacy"))
	mask, _ := asObj(privacy.Get("mask"))
	pad := 8.0
	if truthy(privacy.Get("pad")) {
		pad = mustFloat(privacy.Get("pad"))
	}
	img, err := loadRGB(filepath.Join(rec, frame))
	if err != nil {
		return nil, err
	}
	W, H := float64(img.Bounds().Dx()), float64(img.Bounds().Dy())
	sx, sy := W/vw, H/vh
	pick := func(r Obj, k string, def any) any {
		if r.Has(k) {
			return r.Get(k)
		}
		if mask.Has(k) {
			return mask.Get(k)
		}
		return def
	}
	rects, _ := asList(redactions.Get(frame))
	for _, rv := range rects {
		r, _ := asObj(rv)
		p := pad
		if r.Has("pad") {
			p = mustFloat(r.Get("pad"))
		}
		x0 := math.Max(0, (mustFloat(r.Get("x"))-p)*sx)
		y0 := math.Max(0, (mustFloat(r.Get("y"))-p)*sy)
		x1 := math.Min(W, (mustFloat(r.Get("x"))+mustFloat(r.Get("w"))+p)*sx)
		y1 := math.Min(H, (mustFloat(r.Get("y"))+mustFloat(r.Get("h"))+p)*sy)
		radius := mustFloat(pick(r, "radius", 7)) * math.Min(sx, sy)
		width := math.Max(1, math.Round(math.Min(sx, sy)))
		fill, hasFill := pick(r, "fill", "#f2f4f7").(string)
		stroke, hasStroke := pick(r, "stroke", "#e2e7ec").(string)
		for py := int(y0); py <= int(math.Ceil(y1)) && py < img.Bounds().Dy(); py++ {
			for px := int(x0); px <= int(math.Ceil(x1)) && px < img.Bounds().Dx(); px++ {
				fx, fy := float64(px)+0.5, float64(py)+0.5
				if !insideRounded(fx, fy, x0, y0, x1, y1, radius) {
					continue
				}
				edge := !insideRounded(fx, fy, x0+width, y0+width, x1-width, y1-width, math.Max(0, radius-width))
				switch {
				case edge && hasStroke:
					img.SetRGBA(px, py, hexColor(stroke))
				case hasFill:
					img.SetRGBA(px, py, hexColor(fill))
				}
			}
		}
	}
	return img, nil
}

func privacyReview(rec string, comp Obj) (string, []capture, error) {
	dir := filepath.Join(rec, ".privacy-review")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", nil, err
	}
	stale, _ := filepath.Glob(filepath.Join(dir, "*.jpg"))
	for _, s := range stale {
		_ = os.Remove(s)
	}
	redactions, _ := asObj(comp.Get("redact"))
	var caps []capture
	for _, frame := range usedFrames(beatsOf(comp)) {
		if fi, err := os.Stat(filepath.Join(rec, frame)); err != nil || !fi.Mode().IsRegular() {
			return "", nil, fmt.Errorf("missing frame: %s", frame)
		}
		img, err := maskedFrame(rec, comp, frame)
		if err != nil {
			return "", nil, err
		}
		out := filepath.Join(dir, frame)
		if err := saveJPEG(out, img, 94); err != nil {
			return "", nil, err
		}
		rects, _ := asList(redactions.Get(frame))
		caps = append(caps, capture{out, 0, fmt.Sprintf("privacy · %s · masks:%d", frame, len(rects))})
	}
	return dir, caps, nil
}

func capturesOf(mode Obj, key, prefix string) []capture {
	var out []capture
	list, _ := asList(mode.Get(key))
	for _, cv := range list {
		c, _ := asObj(cv)
		out = append(out, capture{pyStr(c.Get("path")), mustFloat(c.Get("time")), prefix + " · " + pyStr(c.Get("label"))})
	}
	return out
}

func artifactHashes(rec string) (Obj, error) {
	names := append([]string{}, reviewArtifacts...)
	sort.Strings(names)
	out := Obj{}
	for _, n := range names {
		h, err := fileHash(filepath.Join(rec, n))
		if err != nil {
			return nil, err
		}
		out = append(out, pyjson.KV{K: n, V: h})
	}
	return out, nil
}

func review(rec string) (int, error) {
	started := time.Now()
	for _, n := range obsoleteReviewFiles {
		_ = os.Remove(filepath.Join(rec, n))
	}
	comp, err := compileRecording(rec, true)
	if err != nil {
		return 0, err
	}
	if err := copyFile(templatePath(), filepath.Join(rec, "video.html")); err != nil {
		return 0, err
	}
	privacyDir, caps, err := privacyReview(rec, comp)
	if err != nil {
		return 0, err
	}
	samples := reviewSamples(comp)
	reviewDir := filepath.Join(rec, ".renderer-review")
	if err := os.MkdirAll(reviewDir, 0o755); err != nil {
		return 0, err
	}
	stale, _ := filepath.Glob(filepath.Join(reviewDir, "*.png"))
	for _, s := range stale {
		_ = os.Remove(s)
	}
	url, stop, err := serve(rec)
	if err != nil {
		return 0, err
	}
	result, err := reviewBrowser(rec, url, samples)
	stop()
	if err != nil {
		return 0, err
	}

	errs, warnings := []any{}, []any{}
	for _, mode := range []string{"normal", "reduced"} {
		m, _ := asObj(result.Get(mode))
		pre, _ := asObj(m.Get("preflight"))
		el, _ := asList(pre.Get("errors"))
		for _, e := range el {
			errs = append(errs, mode+": "+pyStr(e))
		}
		wl, _ := asList(pre.Get("warnings"))
		for _, w := range wl {
			warnings = append(warnings, mode+": "+pyStr(w))
		}
		clicks, _ := asList(m.Get("clicks"))
		for _, cv := range clicks {
			c, _ := asObj(cv)
			if !truthy(c.Get("visible")) {
				errs = append(errs, fmt.Sprintf("%s: beat %s click is outside the safe viewport", mode, pyStr(c.Get("beat"))))
			}
		}
		caps = append(caps, capturesOf(m, "captures", mode)...)
		caps = append(caps, capturesOf(m, "clickCaptures", mode)...)
	}
	sheet := filepath.Join(rec, "video-review-contact-sheet.jpg")
	if err := contactSheet(caps, sheet, "PRIVACY · EVERY BEAT · EXACT CLICK + RESULT"); err != nil {
		return 0, err
	}
	hashes, err := artifactHashes(rec)
	if err != nil {
		return 0, err
	}
	elapsed := round(time.Since(started).Seconds())
	report := Obj{
		{K: "errors", V: errs},
		{K: "warnings", V: warnings},
		{K: "duration", V: round(totalDuration(comp))},
		{K: "artifactHashes", V: hashes},
		{K: "normal", V: result.Get("normal")},
		{K: "reduced", V: result.Get("reduced")},
		{K: "contactSheet", V: sheet},
		{K: "privacyReviewDir", V: privacyDir},
		{K: "elapsedSeconds", V: elapsed},
	}
	if err := writeText(filepath.Join(rec, "renderer-review.json"), pyjson.Dumps(report, 2)+"\n"); err != nil {
		return 0, err
	}
	fmt.Printf("review sheet: %s\n", sheet)
	fmt.Printf("full-resolution privacy review: %s\n", privacyDir)
	fmt.Printf("renderer review: %d error(s) in %.1fs\n", len(errs), elapsed)
	if len(errs) > 0 {
		return 1, nil
	}
	return 0, nil
}

const exportSnippet = `
import json, time
cfg = %s
try:
    previous = current_tab()['targetId']
except Exception:
    previous = None
target = new_tab()
goto_url(cfg['url'])
wait_for_load()
for _ in range(100):
    if js('window.videoReady && window.videoReady()'):
        break
    time.sleep(0.05)
else:
    raise RuntimeError('video assets did not become ready')
preflight = js('window.videoPreflight()')
clicks = js('window.clickVisibility()')
cdp('Browser.setDownloadBehavior', behavior='allow', downloadPath=cfg['downloadPath'], eventsEnabled=True)
cdp('Page.bringToFront')
started = js('''(() => {
  window.__exported = null; window.__exportError = null;
  window.exportVideo(%s)
    .catch(error => window.__exportError = String(error));
  return true;
})()''')
print(cfg['marker'] + json.dumps({'target': target, 'previous': previous, 'preflight': preflight, 'clicks': clicks, 'started': started}))
`

func startExport(url, webm string) (Obj, error) {
	dir, err := filepath.Abs(filepath.Dir(webm))
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	cfg := Obj{{K: "url", V: url}, {K: "downloadPath", V: dir}, {K: "filename", V: filepath.Base(webm)}, {K: "marker", V: marker}}
	code := fmt.Sprintf(exportSnippet, pyLiteral(json.RawMessage(pyjson.Dumps(cfg, 0))), pyjson.Dumps(filepath.Base(webm), 0))
	return runHarness(code, 30*time.Second)
}

const closeSnippet = `
import json
cfg = %s
downloads_reset = True
try:
    cdp('Browser.setDownloadBehavior', behavior='default', eventsEnabled=False)
except Exception:
    downloads_reset = False
targets = [tab for tab in list_tabs() if tab.get('url') == cfg['url']]
try:
    switch_tab(cfg['previous']) if cfg.get('previous') else new_tab()
except Exception:
    new_tab()
for tab in targets:
    try:
        close_tab(tab)
    except Exception:
        pass
print(cfg['marker'] + json.dumps({'closed': True, 'downloadsReset': downloads_reset}))
`

func closeEditor(url string, previous any) bool {
	cfg := Obj{{K: "url", V: url}, {K: "previous", V: previous}, {K: "marker", V: marker}}
	r, err := runHarness(fmt.Sprintf(closeSnippet, pyLiteral(json.RawMessage(pyjson.Dumps(cfg, 0)))), 15*time.Second)
	return err == nil && r.Get("downloadsReset") == true
}

func run(dir string, timeout time.Duration, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = dir
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = strings.TrimSpace(stdout.String())
		}
		if detail == "" {
			detail = err.Error()
		}
		return "", errors.New(detail)
	}
	return stdout.String(), nil
}

func probe(path string) (Obj, error) {
	out, err := run(filepath.Dir(path), 120*time.Second, "ffprobe", "-v", "error", "-show_entries",
		"format=duration,size:stream=codec_name,width,height,pix_fmt,r_frame_rate", "-of", "json", path)
	if err != nil {
		return nil, err
	}
	v, err := pyjson.Loads([]byte(out))
	if err != nil {
		return nil, err
	}
	o, _ := asObj(v)
	return o, nil
}

func exists(p string) bool { _, err := os.Stat(p); return err == nil }

func isFile(p string) bool {
	fi, err := os.Stat(p)
	return err == nil && fi.Mode().IsRegular()
}

func export(rec, outputName string, reviewed bool) (int, error) {
	if !reviewed {
		return 0, errors.New("inspect the review sheet and full-resolution privacy frames, then rerun with --reviewed")
	}
	if _, err := exec.LookPath("ffmpeg"); err != nil {
		return 0, errors.New("ffmpeg and ffprobe are required")
	}
	if _, err := exec.LookPath("ffprobe"); err != nil {
		return 0, errors.New("ffmpeg and ffprobe are required")
	}
	reviewPath := filepath.Join(rec, "renderer-review.json")
	if !isFile(reviewPath) {
		return 0, errors.New("run browser-harness video review first")
	}
	report, err := loadJSON(reviewPath)
	if err != nil {
		return 0, err
	}
	if truthy(report.Get("errors")) {
		return 0, errors.New("renderer review has blocking errors")
	}
	if err := verifySourceManifest(rec); err != nil {
		return 0, err
	}
	comp, err := loadComposition(filepath.Join(rec, "composition.js"))
	if err != nil {
		return 0, err
	}
	expectedComp, err := compileRecording(rec, false)
	if err != nil {
		return 0, err
	}
	if !sameJSON(comp, expectedComp) {
		return 0, errors.New("composition.js is not the current compiled brief; rerun review")
	}
	hashes, _ := asObj(report.Get("artifactHashes"))
	names := map[string]bool{}
	for _, kv := range hashes {
		names[kv.K] = true
	}
	same := len(names) == len(reviewArtifacts)
	for _, n := range reviewArtifacts {
		same = same && names[n]
	}
	if !same {
		return 0, errors.New("renderer review lacks content hashes; rerun it")
	}
	for _, kv := range hashes {
		h, err := fileHash(filepath.Join(rec, kv.K))
		if err != nil || h != kv.V {
			return 0, fmt.Errorf("%s changed after review; rerun it", kv.K)
		}
	}
	rh, err := fileHash(filepath.Join(rec, "video.html"))
	if err != nil {
		return 0, err
	}
	if th, err := fileHash(templatePath()); err != nil || th != rh {
		return 0, errors.New("renderer is not the current shared template; rerun review")
	}

	output := outputName
	if !filepath.IsAbs(output) {
		output = filepath.Join(rec, output)
	}
	if strings.ToLower(filepath.Ext(output)) != ".mp4" {
		return 0, errors.New("--output must end in .mp4")
	}
	webm := strings.TrimSuffix(output, filepath.Ext(output)) + ".webm"
	for _, p := range []string{webm, output} {
		if exists(p) || exists(p+".crdownload") {
			return 0, fmt.Errorf("refusing to overwrite %s", p)
		}
	}

	expected := totalDuration(expectedComp)
	started := time.Now()
	url, stop, err := serve(rec)
	if err != nil {
		return 0, err
	}
	var browser Obj
	captureErr := func() error {
		var err error
		if browser, err = startExport(url, webm); err != nil {
			return err
		}
		pre, _ := asObj(browser.Get("preflight"))
		if el, _ := asList(pre.Get("errors")); len(el) > 0 {
			msgs := make([]string, len(el))
			for i, e := range el {
				msgs[i] = pyStr(e)
			}
			return errors.New("export preflight failed: " + strings.Join(msgs, "; "))
		}
		clicks, _ := asList(browser.Get("clicks"))
		for _, cv := range clicks {
			if c, _ := asObj(cv); !truthy(c.Get("visible")) {
				return errors.New("export click visibility failed")
			}
		}
		deadline := time.Now().Add(time.Duration((expected + 30) * float64(time.Second)))
		partial := webm + ".crdownload"
		for time.Now().Before(deadline) {
			if fi, err := os.Stat(webm); err == nil && fi.Mode().IsRegular() && !exists(partial) && fi.Size() > 0 {
				time.Sleep(250 * time.Millisecond)
				if fi2, err := os.Stat(webm); err == nil && fi2.Size() == fi.Size() {
					return nil
				}
			}
			time.Sleep(250 * time.Millisecond)
		}
		return fmt.Errorf("timed out waiting for %s", webm)
	}()
	closed := closeEditor(url, browser.Get("previous"))
	stop()
	if !closed {
		return 0, errors.New("could not restore Chrome download behavior; restart Chrome")
	}
	if captureErr != nil {
		return 0, captureErr
	}
	captureSeconds := time.Since(started).Seconds()

	convStarted := time.Now()
	if _, err := probe(webm); err != nil {
		return 0, err
	}
	if _, err := run(rec, 120*time.Second, "ffmpeg", "-v", "error", "-i", webm, "-c:v", "libx264",
		"-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output); err != nil {
		return 0, err
	}
	convSeconds := time.Since(convStarted).Seconds()

	verifyStarted := time.Now()
	pr, err := probe(output)
	if err != nil {
		return 0, err
	}
	format, _ := asObj(pr.Get("format"))
	actual, ok := toFloat(format.Get("duration"))
	if !ok {
		return 0, errors.New("ffprobe reported no duration")
	}
	if math.Abs(actual-expected) > math.Max(1.0, expected*0.08) {
		return 0, fmt.Errorf("export duration %.2fs does not match composition %.2fs", actual, expected)
	}
	if _, err := run(rec, 120*time.Second, "ffmpeg", "-v", "error", "-err_detect", "explode", "-i", output, "-f", "null", "-"); err != nil {
		return 0, err
	}
	reviewDir := filepath.Join(rec, ".renderer-review")
	var finals []capture
	for i, at := range []float64{math.Min(1.0, expected/4), expected / 2, math.Max(0, expected-0.8)} {
		p := filepath.Join(reviewDir, fmt.Sprintf("final-%02d.jpg", i+1))
		if _, err := run(rec, 120*time.Second, "ffmpeg", "-v", "error", "-y", "-ss", fmt.Sprintf("%.3f", at), "-i", output, "-frames:v", "1", p); err != nil {
			return 0, err
		}
		finals = append(finals, capture{p, at, []string{"intro", "middle", "outcome"}[i]})
	}
	finalSheet := filepath.Join(rec, "renderer-final-contact-sheet.jpg")
	if err := contactSheet(finals, finalSheet, "FINAL MP4 SAMPLE"); err != nil {
		return 0, err
	}
	verifySeconds := time.Since(verifyStarted).Seconds()
	sum, err := fileHash(output)
	if err != nil {
		return 0, err
	}
	elapsed := round(time.Since(started).Seconds())
	out := Obj{
		{K: "output", V: output},
		{K: "webm", V: webm},
		{K: "expectedDuration", V: round(expected)},
		{K: "actualDuration", V: actual},
		{K: "captureSeconds", V: round(captureSeconds)},
		{K: "conversionSeconds", V: round(convSeconds)},
		{K: "verificationSeconds", V: round(verifySeconds)},
		{K: "elapsedSeconds", V: elapsed},
		{K: "sha256", V: sum},
		{K: "probe", V: pr},
		{K: "finalContactSheet", V: finalSheet},
	}
	if err := writeText(filepath.Join(rec, "video-export.json"), pyjson.Dumps(out, 2)+"\n"); err != nil {
		return 0, err
	}
	fmt.Printf("video: %s\n", output)
	fmt.Printf("final review: %s\n", finalSheet)
	fmt.Printf("verified %.2fs MP4 in %.1fs\n", actual, elapsed)
	return 0, nil
}

const usage = "usage: browser-harness video [-h] {init,review,export} ..."

// CLI is `browser-harness video`.
func CLI(args []string) int {
	fail := func(msg string) int {
		fmt.Fprintf(os.Stderr, "%s\nbrowser-harness video: error: %s\n", usage, msg)
		return 2
	}
	if len(args) == 0 {
		return fail("the following arguments are required: command")
	}
	if args[0] == "-h" || args[0] == "--help" {
		fmt.Println(usage)
		return 0
	}
	cmd, rest := args[0], args[1:]
	var recArg string
	requireExplicit, reviewed, output := false, false, "video.mp4"
	for i := 0; i < len(rest); i++ {
		a := rest[i]
		switch {
		case cmd == "init" && a == "--require-explicit":
			requireExplicit = true
		case cmd == "export" && a == "--reviewed":
			reviewed = true
		case cmd == "export" && a == "--output" && i+1 < len(rest):
			i++
			output = rest[i]
		case cmd == "export" && strings.HasPrefix(a, "--output="):
			output = strings.TrimPrefix(a, "--output=")
		case recArg == "" && !strings.HasPrefix(a, "-"):
			recArg = a
		default:
			return fail("unrecognized arguments: " + a)
		}
	}
	if cmd != "init" && cmd != "review" && cmd != "export" {
		return fail(fmt.Sprintf("argument command: invalid choice: '%s' (choose from 'init', 'review', 'export')", cmd))
	}
	if recArg == "" {
		return fail("the following arguments are required: recording")
	}
	if strings.HasPrefix(recArg, "~/") {
		h, _ := os.UserHomeDir()
		recArg = filepath.Join(h, recArg[2:])
	}
	rec, err := filepath.Abs(recArg)
	if err == nil {
		if r, e := filepath.EvalSymlinks(rec); e == nil {
			rec = r
		}
	}
	code := 0
	switch cmd {
	case "init":
		err = initRecording(rec, requireExplicit)
	case "review":
		code, err = review(rec)
	case "export":
		code, err = export(rec, output, reviewed)
	}
	if err != nil {
		return fail(err.Error())
	}
	return code
}
