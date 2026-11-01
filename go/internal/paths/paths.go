// Package paths mirrors browser_harness/paths.py: the on-disk layout shared by
// the Go core and the Python snippet runner.
package paths

import (
	"os"
	"path/filepath"
	"runtime"
)

func abs(p string) string {
	if len(p) > 1 && p[:2] == "~/" {
		if h, err := os.UserHomeDir(); err == nil {
			p = filepath.Join(h, p[2:])
		}
	}
	if a, err := filepath.Abs(p); err == nil {
		p = a
	}
	if r, err := filepath.EvalSymlinks(p); err == nil {
		p = r
	}
	return p
}

// Home is BH_HOME, BROWSER_HARNESS_HOME, $XDG_CONFIG_HOME/browser-harness or ~/.config/browser-harness.
func Home() string {
	if raw := firstEnv("BH_HOME", "BROWSER_HARNESS_HOME"); raw != "" {
		return abs(raw)
	}
	if base := os.Getenv("XDG_CONFIG_HOME"); base != "" {
		return abs(filepath.Join(base, "browser-harness"))
	}
	h, _ := os.UserHomeDir()
	return abs(filepath.Join(h, ".config", "browser-harness"))
}

// EnsurePrivateDir creates dir and, when it did not exist, restricts it to the owner.
func EnsurePrivateDir(dir string) string {
	_, err := os.Stat(dir)
	existed := err == nil
	_ = os.MkdirAll(dir, 0o777)
	if !existed && runtime.GOOS != "windows" {
		_ = os.Chmod(dir, 0o700)
	}
	return dir
}

func ConfigDir() string { return EnsurePrivateDir(envOr("BH_CONFIG_DIR", Home())) }
func RuntimeDir() string {
	return EnsurePrivateDir(envOr("BH_RUNTIME_DIR", filepath.Join(Home(), "runtime")))
}
func TmpDir() string { return EnsurePrivateDir(envOr("BH_TMP_DIR", filepath.Join(Home(), "tmp"))) }
func WorkspaceDir() string {
	return EnsurePrivateDir(envOr("BH_AGENT_WORKSPACE", filepath.Join(Home(), "agent-workspace")))
}

// InspectMarker records that the harness opened a chrome://inspect tab.
func InspectMarker() string { return filepath.Join(ConfigDir(), "inspect-opened") }

func envOr(key, def string) string {
	if raw := os.Getenv(key); raw != "" {
		return abs(raw)
	}
	return def
}

func firstEnv(keys ...string) string {
	for _, k := range keys {
		if v := os.Getenv(k); v != "" {
			return v
		}
	}
	return ""
}

// LoadEnv mirrors _load_env(): <repo>/.env (repo from BH_REPO_ROOT, set by the
// Python package) then <workspace>/.env; existing variables win.
func LoadEnv() {
	var files []string
	if root := os.Getenv("BH_REPO_ROOT"); root != "" {
		files = append(files, filepath.Join(root, ".env"))
	}
	files = append(files, filepath.Join(WorkspaceDir(), ".env"))
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		s := string(raw)
		s = trimBOM(s)
		for _, line := range splitLines(s) {
			line = trimSpace(line)
			if line == "" || line[0] == '#' {
				continue
			}
			i := indexByte(line, '=')
			if i < 0 {
				continue
			}
			k := trimSpace(line[:i])
			v := trimQuotes(trimSpace(line[i+1:]))
			if _, set := os.LookupEnv(k); !set {
				_ = os.Setenv(k, v)
			}
		}
	}
}
