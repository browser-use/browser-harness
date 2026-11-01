package paths

import (
	"bufio"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// Discover fills BH_PACKAGE_DIR, BH_PYTHON, BH_PYTHON_VERSION, BH_VERSION and
// BH_REPO_ROOT from where this binary sits, so it runs without a Python launcher.
// It handles the venv script dir (<venv>/bin) and a source checkout
// (<repo>/bin, with <repo>/src/browser_harness and <repo>/.venv). Set variables win.
func Discover() {
	exe, err := os.Executable()
	if err != nil {
		return
	}
	if r, err := filepath.EvalSymlinks(exe); err == nil {
		exe = r
	}
	// Snippets calling admin helpers come back to this same binary.
	setDefault("BH_CORE", exe)
	bin := filepath.Dir(exe)
	pkg, venv := "", ""
	if repo := filepath.Dir(bin); isPackage(filepath.Join(repo, "src", "browser_harness")) {
		pkg = filepath.Join(repo, "src", "browser_harness")
		venv = filepath.Join(repo, ".venv")
	} else {
		venv = filepath.Dir(bin)
	}
	site := sitePackages(venv)
	if pkg == "" && site != "" {
		pkg = packageIn(site)
	}
	setDefault("BH_PACKAGE_DIR", pkg)
	setDefault("BH_PYTHON", python(venv))
	if site != "" {
		// <venv>/lib/python3.12/site-packages
		setDefault("BH_PYTHON_VERSION", strings.TrimPrefix(filepath.Base(filepath.Dir(site)), "python"))
		if m, _ := filepath.Glob(filepath.Join(site, "browser_harness-*.dist-info")); len(m) > 0 {
			setDefault("BH_VERSION", strings.TrimSuffix(strings.TrimPrefix(filepath.Base(m[0]), "browser_harness-"), ".dist-info"))
		}
	}
	if pkg != "" {
		for _, c := range []string{filepath.Dir(pkg), filepath.Dir(filepath.Dir(pkg))} {
			if fi, err := os.Stat(filepath.Join(c, ".git")); err == nil && fi.IsDir() {
				setDefault("BH_REPO_ROOT", c)
				break
			}
		}
	}
}

func setDefault(k, v string) {
	if v != "" && os.Getenv(k) == "" {
		os.Setenv(k, v)
	}
}

func isPackage(dir string) bool {
	_, err := os.Stat(filepath.Join(dir, "runner.py"))
	return err == nil && filepath.Base(dir) == "browser_harness"
}

func sitePackages(venv string) string {
	pattern := filepath.Join(venv, "lib", "python*", "site-packages")
	if runtime.GOOS == "windows" {
		pattern = filepath.Join(venv, "Lib", "site-packages")
	}
	m, _ := filepath.Glob(pattern)
	if len(m) == 0 {
		return ""
	}
	return m[0]
}

// packageIn finds browser_harness in site-packages, following an editable .pth.
func packageIn(site string) string {
	if p := filepath.Join(site, "browser_harness"); isPackage(p) {
		return p
	}
	pths, _ := filepath.Glob(filepath.Join(site, "*browser_harness*.pth"))
	for _, pth := range pths {
		f, err := os.Open(pth)
		if err != nil {
			continue
		}
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			if p := filepath.Join(strings.TrimSpace(sc.Text()), "browser_harness"); isPackage(p) {
				f.Close()
				return p
			}
		}
		f.Close()
	}
	return ""
}

func python(venv string) string {
	names := []string{filepath.Join("bin", "python3"), filepath.Join("bin", "python")}
	if runtime.GOOS == "windows" {
		names = []string{filepath.Join("Scripts", "python.exe")}
	}
	for _, n := range names {
		if _, err := os.Stat(filepath.Join(venv, n)); err == nil {
			return filepath.Join(venv, n)
		}
	}
	return ""
}
