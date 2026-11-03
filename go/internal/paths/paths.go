// Package paths is the on-disk layout: config, runtime, tmp and workspace dirs.
package paths

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
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

// Home is BH_HOME, $XDG_CONFIG_HOME/browser-harness or ~/.config/browser-harness.
func Home() string {
	if raw := os.Getenv("BH_HOME"); raw != "" {
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
	_ = os.MkdirAll(dir, 0o777) //nolint:gosec // Preserve umask-based creation of parent directories before restricting the leaf.
	if !existed && runtime.GOOS != "windows" {
		_ = os.Chmod(dir, 0o700) //nolint:gosec // Owner execute permission is required for directory traversal.
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

// LoadEnv reads <repo>/.env (source checkouts) then <workspace>/.env; existing variables win.
func LoadEnv() {
	var files []string
	if root := RepoRoot(); root != "" {
		files = append(files, filepath.Join(root, ".env"))
	}
	files = append(files, filepath.Join(WorkspaceDir(), ".env"))
	for _, f := range files {
		raw, err := os.ReadFile(f) //nolint:gosec // Load environment files from the configured repository and workspace.
		if err != nil {
			continue
		}
		s := strings.ReplaceAll(strings.TrimPrefix(string(raw), "\ufeff"), "\r\n", "\n")
		for _, line := range strings.Split(s, "\n") {
			k, v, ok := strings.Cut(strings.TrimSpace(line), "=")
			if !ok || k == "" || k[0] == '#' {
				continue
			}
			k = strings.TrimSpace(k)
			v = strings.Trim(strings.Trim(strings.TrimSpace(v), `"`), `'`)
			if _, set := os.LookupEnv(k); !set {
				_ = os.Setenv(k, v)
			}
		}
	}
}

// Enabled reports whether an environment value explicitly turns a feature on.
func Enabled(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

// Disabled reports whether an environment value turns a feature off.
func Disabled(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "0", "false", "no", "off":
		return true
	}
	return false
}

// WriteFileAtomic replaces path with data via a temporary file in the same
// directory, so readers never see a partial file.
func WriteFileAtomic(path string, data []byte, perm os.FileMode) error {
	f, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".*.tmp")
	if err != nil {
		return err
	}
	defer func() { _ = os.Remove(f.Name()) }()
	_, err = f.Write(data)
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err == nil {
		err = os.Chmod(f.Name(), perm)
	}
	if err == nil {
		err = os.Rename(f.Name(), path)
	}
	return err
}
