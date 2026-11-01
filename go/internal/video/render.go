package video

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
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
	"strconv"
	"strings"
	"time"

	"golang.org/x/image/draw"
	"golang.org/x/image/font"
	"golang.org/x/image/font/basicfont"
	"golang.org/x/image/math/fixed"

	"github.com/browser-use/browser-harness/go/internal/admin"
)

const marker = "__BH_VIDEO_RESULT__="

// reviewed are the files whose hashes export checks against the review.
var reviewed = []string{"composition.js", "edit-brief.json", "recording-summary.json", "video-source.json", "video.html"}

type capture struct {
	Path  string  `json:"path"`
	Time  float64 `json:"time"`
	Label string  `json:"label"`
}

type sample struct {
	Time  float64 `json:"time"`
	Label string  `json:"label"`
}

// samples picks one stable moment per beat, plus every explanation reveal.
func samples(c *Composition) []sample {
	var out []sample
	start := 0.0
	for i, b := range c.Beats {
		at := func(local float64) float64 { return round3(start + math.Min(math.Max(0.05, b.Dur-0.05), local)) }
		switch {
		case b.Kind == "explanation" && len(b.Points) > 0:
			gap := math.Max(0, b.Dur-4.1) / float64(max(1, len(b.Points)-1))
			for j, p := range b.Points {
				out = append(out, sample{at(1.1 + float64(j)*gap + 0.2), fmt.Sprintf("beat %d · %s", i+1, p.Label)})
			}
		case b.Card:
			out = append(out, sample{at(1.0), fmt.Sprintf("beat %d", i+1)})
		default:
			out = append(out, sample{at(math.Max(0.12, math.Min(0.5, b.Dur/2))), fmt.Sprintf("beat %d", i+1)})
		}
		start += b.Dur
	}
	return out
}

// serve exposes the recording on loopback so the renderer can load its frames.
func serve(rec string) (string, func(), error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", nil, err
	}
	srv := &http.Server{Handler: http.FileServer(http.Dir(rec))}
	go func() { _ = srv.Serve(l) }()
	return fmt.Sprintf("http://%s/video.html", l.Addr()), func() { _ = srv.Close() }, nil
}

// runHarness runs a snippet with cfg bound and decodes its marker line into out; a seam for tests.
var runHarness = func(snippet string, cfg any, timeout time.Duration, out any) error {
	if err := admin.EnsureDaemon(-1, "", nil); err != nil {
		return err
	}
	raw, _ := json.Marshal(cfg)
	code := "import json\ncfg = json.loads(" + strconv.Quote(string(raw)) + ")\n" + snippet
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
		return fmt.Errorf("browser step failed: %v: %s", err, strings.TrimSpace(stderr.String()))
	}
	for _, line := range strings.Split(stdout.String(), "\n") {
		if rest, ok := strings.CutPrefix(line, marker); ok {
			return json.Unmarshal([]byte(rest), out)
		}
	}
	return fmt.Errorf("browser step returned no result: %s", stdout.String())
}

const reviewSnippet = `import os, time
os.makedirs(cfg['reviewDir'], exist_ok=True)

def ready():
    for _ in range(100):
        if js('window.videoReady && window.videoReady()'):
            return
        time.sleep(0.05)
    raise RuntimeError('video assets did not become ready')

def inspect(name, reduced):
    features = [{'name': 'prefers-reduced-motion', 'value': 'reduce'}] if reduced else []
    cdp('Emulation.setEmulatedMedia', media='', features=features)
    cdp('Page.reload', ignoreCache=True)
    wait_for_load()
    ready()
    out = {'preflight': js('window.videoPreflight()'), 'clicks': js('window.clickVisibility()'), 'captures': []}
    shots = [(f"beat-{i:02d}", s['time'], s['label']) for i, s in enumerate(cfg['samples'], 1)]
    for i, c in enumerate(out['clicks'], 1):
        shots += [(f"click-{i:02d}-click", c['time'], f"beat {c['beat']} · click"),
                  (f"click-{i:02d}-result", c['resultTime'], f"beat {c['beat']} · result")]
    for key, t, label in shots:
        js(f"window.seek({t})")
        path = f"{cfg['reviewDir']}/{name}-{key}.png"
        capture_screenshot(path)
        out['captures'].append({'path': path, 'time': t, 'label': f"{name} · {label}"})
    return out

try:
    previous = current_tab()['targetId']
except Exception:  # a stale session heals on the next call
    previous = None
target = new_tab(cfg['url'])
try:
    wait_for_load()
    ready()
    print(cfg['marker'] + json.dumps({'normal': inspect('normal', False), 'reduced': inspect('reduced', True)}))
finally:
    cdp('Emulation.setEmulatedMedia', media='', features=[])
    switch_tab(previous) if previous else new_tab()
    close_tab(target)
`

type modeResult struct {
	Preflight struct {
		Errors   []string `json:"errors"`
		Warnings []string `json:"warnings"`
	} `json:"preflight"`
	Clicks []struct {
		Beat    any  `json:"beat"`
		Visible bool `json:"visible"`
	} `json:"clicks"`
	Captures []capture `json:"captures"`
}

type reviewReport struct {
	Errors         []string          `json:"errors"`
	Warnings       []string          `json:"warnings"`
	Duration       float64           `json:"duration"`
	ArtifactHashes map[string]string `json:"artifactHashes"`
	ContactSheet   string            `json:"contactSheet"`
	PrivacyDir     string            `json:"privacyReviewDir"`
}

func review(rec string) (int, error) {
	started := time.Now()
	c, comp, err := compileRecording(rec)
	if err != nil {
		return 0, err
	}
	if err := os.WriteFile(filepath.Join(rec, "composition.js"), comp, 0o644); err != nil {
		return 0, err
	}
	if err := copyFile(templatePath(), filepath.Join(rec, "video.html")); err != nil {
		return 0, err
	}
	privacyDir, caps, err := privacyReview(rec, c)
	if err != nil {
		return 0, err
	}
	reviewDir := filepath.Join(rec, ".renderer-review")
	_ = os.RemoveAll(reviewDir)
	url, stop, err := serve(rec)
	if err != nil {
		return 0, err
	}
	var result map[string]modeResult
	err = runHarness(reviewSnippet, map[string]any{"url": url, "samples": samples(c), "reviewDir": reviewDir, "marker": marker},
		time.Duration(max(60, len(c.Beats)*6))*time.Second, &result)
	stop()
	if err != nil {
		return 0, err
	}
	report := reviewReport{Errors: []string{}, Warnings: []string{}, Duration: duration(c.Beats),
		ContactSheet: filepath.Join(rec, "video-review-contact-sheet.jpg"), PrivacyDir: privacyDir}
	for _, mode := range []string{"normal", "reduced"} {
		m := result[mode]
		for _, e := range m.Preflight.Errors {
			report.Errors = append(report.Errors, mode+": "+e)
		}
		for _, w := range m.Preflight.Warnings {
			report.Warnings = append(report.Warnings, mode+": "+w)
		}
		for _, cl := range m.Clicks {
			if !cl.Visible {
				report.Errors = append(report.Errors, fmt.Sprintf("%s: beat %v click is outside the safe viewport", mode, cl.Beat))
			}
		}
		caps = append(caps, m.Captures...)
	}
	if err := contactSheet(caps, report.ContactSheet, "PRIVACY · EVERY BEAT · EXACT CLICK + RESULT"); err != nil {
		return 0, err
	}
	if report.ArtifactHashes, err = hashes(rec, reviewed); err != nil {
		return 0, err
	}
	if err := writeJSON(filepath.Join(rec, "renderer-review.json"), report); err != nil {
		return 0, err
	}
	fmt.Printf("review sheet: %s\nfull-resolution privacy review: %s\nrenderer review: %d error(s) in %.1fs\n",
		report.ContactSheet, privacyDir, len(report.Errors), time.Since(started).Seconds())
	if len(report.Errors) > 0 {
		return 1, nil
	}
	return 0, nil
}

func hashes(rec string, names []string) (map[string]string, error) {
	out := map[string]string{}
	for _, n := range names {
		h, err := fileHash(filepath.Join(rec, n))
		if err != nil {
			return nil, err
		}
		out[n] = h
	}
	return out, nil
}

// --- images ---

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

func saveJPEG(path string, img image.Image) error {
	var b bytes.Buffer
	if err := jpeg.Encode(&b, img, &jpeg.Options{Quality: 92}); err != nil {
		return err
	}
	return os.WriteFile(path, b.Bytes(), 0o644)
}

func hexColor(s string) color.RGBA {
	v, _ := strconv.ParseUint(strings.TrimPrefix(s, "#"), 16, 32)
	return color.RGBA{uint8(v >> 16), uint8(v >> 8), uint8(v), 255}
}

func label(img *image.RGBA, x, y int, s string, c color.Color) {
	d := font.Drawer{Dst: img, Src: image.NewUniform(c), Face: basicfont.Face7x13, Dot: fixed.P(x, y+11)}
	d.DrawString(strings.ReplaceAll(s, "·", "|")) // the bitmap face is ASCII-only
}

// contactSheet tiles captures four across with their labels.
func contactSheet(caps []capture, output, title string) error {
	const cols, tw, th, lh, gap, banner = 4, 400, 225, 34, 8, 42
	rows := max(1, (len(caps)+cols-1)/cols)
	sheet := image.NewRGBA(image.Rect(0, 0, cols*tw+(cols+1)*gap, banner+rows*(th+lh+gap)+gap))
	draw.Draw(sheet, sheet.Bounds(), image.NewUniform(hexColor("#171a20")), image.Point{}, draw.Src)
	label(sheet, gap, 15, title, color.White)
	for i, c := range caps {
		img, err := loadRGB(c.Path)
		if err != nil {
			return err
		}
		s := math.Min(tw/float64(img.Bounds().Dx()), th/float64(img.Bounds().Dy()))
		w, h := int(float64(img.Bounds().Dx())*s), int(float64(img.Bounds().Dy())*s)
		x, y := gap+i%cols*(tw+gap), banner+gap+i/cols*(th+lh+gap)
		draw.CatmullRom.Scale(sheet, image.Rect(x+(tw-w)/2, y, x+(tw-w)/2+w, y+h), img, img.Bounds(), draw.Src, nil)
		label(sheet, x, y+th+9, fmt.Sprintf("%s  %.2fs", c.Label, c.Time), hexColor("#d7dbe3"))
	}
	return saveJPEG(output, sheet)
}

// privacyReview writes every used frame with its masks applied, at full resolution.
func privacyReview(rec string, c *Composition) (string, []capture, error) {
	dir := filepath.Join(rec, ".privacy-review")
	_ = os.RemoveAll(dir)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", nil, err
	}
	var caps []capture
	for _, frame := range usedFrames(c.Beats) {
		img, err := loadRGB(filepath.Join(rec, frame))
		if err != nil {
			return "", nil, err
		}
		sx, sy := float64(img.Bounds().Dx())/c.Viewport.W, float64(img.Bounds().Dy())/c.Viewport.H
		for _, r := range c.Redact[frame] {
			pad := c.Privacy.Pad
			if r.Pad != nil {
				pad = *r.Pad
			}
			fill := c.Privacy.Mask.Fill
			if s, ok := r.Fill.(string); ok {
				fill = s
			}
			rect := image.Rect(int((*r.X-pad)*sx), int((*r.Y-pad)*sy), int(math.Ceil((*r.X+*r.W+pad)*sx)), int(math.Ceil((*r.Y+*r.H+pad)*sy)))
			draw.Draw(img, rect.Intersect(img.Bounds()), image.NewUniform(hexColor(fill)), image.Point{}, draw.Src)
		}
		out := filepath.Join(dir, frame)
		if err := saveJPEG(out, img); err != nil {
			return "", nil, err
		}
		caps = append(caps, capture{out, 0, fmt.Sprintf("privacy · %s · masks:%d", frame, len(c.Redact[frame]))})
	}
	return dir, caps, nil
}

// --- export ---

const exportSnippet = `import time
try:
    previous = current_tab()['targetId']
except Exception:  # a stale session heals on the next call
    previous = None
target = new_tab(cfg['url'])
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
js('window.exportVideo(' + json.dumps(cfg['filename']) + ').catch(e => window.__exportError = String(e)), true')
print(cfg['marker'] + json.dumps({'previous': previous, 'preflight': preflight, 'clicks': clicks}))
`

const closeSnippet = `cdp('Browser.setDownloadBehavior', behavior='default', eventsEnabled=False)
editors = [t['targetId'] for t in list_tabs() if t.get('url') == cfg['url']]
try:
    switch_tab(cfg['previous'])
except Exception:
    new_tab()
for tab in editors:
    close_tab(tab)
print(cfg['marker'] + 'true')
`

func run(dir string, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = dir
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%s: %v: %s", name, err, strings.TrimSpace(stderr.String()))
	}
	return stdout.String(), nil
}

func probeDuration(path string) (float64, error) {
	out, err := run(filepath.Dir(path), "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path)
	if err != nil {
		return 0, err
	}
	return strconv.ParseFloat(strings.TrimSpace(out), 64)
}

func export(rec, output string, reviewedFlag bool) error {
	if !reviewedFlag {
		return errors.New("inspect the review sheet and full-resolution privacy frames, then rerun with --reviewed")
	}
	for _, tool := range []string{"ffmpeg", "ffprobe"} {
		if _, err := exec.LookPath(tool); err != nil {
			return errors.New("ffmpeg and ffprobe are required")
		}
	}
	var report reviewReport
	if err := readJSONLoose(filepath.Join(rec, "renderer-review.json"), &report); err != nil {
		return errors.New("run browser-harness video review first")
	}
	if len(report.Errors) > 0 {
		return errors.New("renderer review has blocking errors")
	}
	c, comp, err := compileRecording(rec)
	if err != nil {
		return err
	}
	if cur, _ := os.ReadFile(filepath.Join(rec, "composition.js")); !bytes.Equal(cur, comp) {
		return errors.New("composition.js is not the current compiled brief; rerun review")
	}
	now, err := hashes(rec, reviewed)
	if err != nil {
		return err
	}
	for n, h := range now {
		if report.ArtifactHashes[n] != h {
			return fmt.Errorf("%s changed after review; rerun it", n)
		}
	}
	if th, _ := fileHash(templatePath()); th != now["video.html"] {
		return errors.New("renderer is not the current shared template; rerun review")
	}
	if !filepath.IsAbs(output) {
		output = filepath.Join(rec, output)
	}
	if strings.ToLower(filepath.Ext(output)) != ".mp4" {
		return errors.New("--output must end in .mp4")
	}
	webm := strings.TrimSuffix(output, filepath.Ext(output)) + ".webm"
	for _, p := range []string{webm, webm + ".crdownload", output} {
		if _, err := os.Stat(p); err == nil {
			return fmt.Errorf("refusing to overwrite %s", p)
		}
	}
	if err := os.MkdirAll(filepath.Dir(webm), 0o755); err != nil {
		return err
	}

	expected := duration(c.Beats)
	url, stop, err := serve(rec)
	if err != nil {
		return err
	}
	defer stop()
	var started struct {
		Previous string `json:"previous"`
		Pre      struct {
			Errors []string `json:"errors"`
		} `json:"preflight"`
		Clicks []struct {
			Visible bool `json:"visible"`
		} `json:"clicks"`
	}
	err = runHarness(exportSnippet, map[string]any{"url": url, "downloadPath": filepath.Dir(webm),
		"filename": filepath.Base(webm), "marker": marker}, 30*time.Second, &started)
	if err == nil && len(started.Pre.Errors) > 0 {
		err = errors.New("export preflight failed: " + strings.Join(started.Pre.Errors, "; "))
	}
	for _, cl := range started.Clicks {
		if err == nil && !cl.Visible {
			err = errors.New("export click visibility failed")
		}
	}
	if err == nil {
		err = waitForDownload(webm, time.Duration((expected+30)*float64(time.Second)))
	}
	var closed bool
	if cerr := runHarness(closeSnippet, map[string]any{"url": url, "previous": started.Previous, "marker": marker}, 15*time.Second, &closed); cerr != nil && err == nil {
		err = fmt.Errorf("could not restore Chrome download behavior; restart Chrome: %v", cerr)
	}
	if err != nil {
		return err
	}

	if _, err := run(rec, "ffmpeg", "-v", "error", "-i", webm, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
		"-movflags", "+faststart", output); err != nil {
		return err
	}
	actual, err := probeDuration(output)
	if err != nil {
		return err
	}
	if math.Abs(actual-expected) > math.Max(1, expected*0.08) {
		return fmt.Errorf("export duration %.2fs does not match composition %.2fs", actual, expected)
	}
	reviewDir := filepath.Join(rec, ".renderer-review")
	var finals []capture
	for i, at := range []float64{math.Min(1, expected/4), expected / 2, math.Max(0, expected-0.8)} {
		p := filepath.Join(reviewDir, fmt.Sprintf("final-%02d.jpg", i+1))
		if _, err := run(rec, "ffmpeg", "-v", "error", "-y", "-ss", fmt.Sprintf("%.3f", at), "-i", output, "-frames:v", "1", p); err != nil {
			return err
		}
		finals = append(finals, capture{p, at, []string{"intro", "middle", "outcome"}[i]})
	}
	sheet := filepath.Join(rec, "renderer-final-contact-sheet.jpg")
	if err := contactSheet(finals, sheet, "FINAL MP4 SAMPLE"); err != nil {
		return err
	}
	fmt.Printf("video: %s\nfinal review: %s\nverified %.2fs MP4\n", output, sheet, actual)
	return nil
}

// waitForDownload returns once Chrome has finished writing path.
func waitForDownload(path string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	last := int64(-1)
	for time.Now().Before(deadline) {
		fi, err := os.Stat(path)
		_, partial := os.Stat(path + ".crdownload")
		if err == nil && partial != nil && fi.Size() > 0 && fi.Size() == last {
			return nil
		}
		if err == nil {
			last = fi.Size()
		}
		time.Sleep(250 * time.Millisecond)
	}
	return fmt.Errorf("timed out waiting for %s", path)
}

// CLI is `browser-harness video init|review|export <recording>`.
func CLI(args []string) int {
	const usage = "usage: browser-harness video {init [--require-explicit] | review | export [--output video.mp4] --reviewed} <recording>"
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, usage)
		return 2
	}
	fs := flag.NewFlagSet("video "+args[0], flag.ContinueOnError)
	explicit := fs.Bool("require-explicit", false, "")
	output := fs.String("output", "video.mp4", "")
	reviewedFlag := fs.Bool("reviewed", false, "")
	// Flags may follow the recording path.
	var pos []string
	for rest := args[1:]; ; rest = fs.Args()[1:] {
		if fs.Parse(rest) != nil {
			fmt.Fprintln(os.Stderr, usage)
			return 2
		}
		if fs.NArg() == 0 {
			break
		}
		pos = append(pos, fs.Arg(0))
	}
	if len(pos) != 1 {
		fmt.Fprintln(os.Stderr, usage)
		return 2
	}
	rec, err := filepath.Abs(pos[0])
	code := 0
	if err == nil {
		switch args[0] {
		case "init":
			err = initRecording(rec, *explicit)
		case "review":
			code, err = review(rec)
		case "export":
			err = export(rec, *output, *reviewedFlag)
		default:
			fmt.Fprintln(os.Stderr, usage)
			return 2
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "browser-harness video:", err)
		return 1
	}
	return code
}
