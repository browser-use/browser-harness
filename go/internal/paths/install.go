package paths

import (
	"os"
	"path/filepath"
)

// RepoRoot is the source checkout this binary was built into (<repo>/bin), or "".
func RepoRoot() string {
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	if r, err := filepath.EvalSymlinks(exe); err == nil {
		exe = r
	}
	repo := filepath.Dir(filepath.Dir(exe))
	if _, err := os.Stat(filepath.Join(repo, "go", "go.mod")); err != nil {
		return ""
	}
	return repo
}
