package auth

import (
	"os"
	"path/filepath"
	"testing"
)

func writeAuth(t *testing.T, raw string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "auth.json")
	if raw != "" {
		if err := os.WriteFile(p, []byte(raw), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	t.Setenv("BH_AUTH_PATH", p)
	t.Setenv("BROWSER_USE_API_KEY", "")
	return p
}

func TestNonObjectAuthFileIsAnError(t *testing.T) {
	for _, raw := range []string{"[]", "null", `"token"`, "123", "{"} {
		p := writeAuth(t, raw)
		if _, err := loadFile(p); err == nil {
			t.Errorf("loadFile(%s) accepted", raw)
		}
		if _, err := APIKey(); err == nil || err == ErrRequired {
			t.Errorf("APIKey with %s: %v", raw, err)
		}
		if _, err := Status(); err == nil {
			t.Errorf("Status with %s accepted", raw)
		}
		if _, err := Clear(); err == nil {
			t.Errorf("Clear with %s accepted", raw)
		}
		if _, err := os.Stat(p); err != nil {
			t.Errorf("Clear removed a corrupt file: %v", err)
		}
	}
}

func TestAuthFileMissingAndObject(t *testing.T) {
	p := writeAuth(t, "")
	if m, err := loadFile(p); err != nil || len(m) != 0 {
		t.Fatalf("missing: %v %v", m, err)
	}
	if _, err := APIKey(); err != ErrRequired {
		t.Fatalf("missing key: %v", err)
	}
	p = writeAuth(t, `{"browser_use": {"api_key": "k"}}`)
	if k, err := APIKey(); err != nil || k != "k" {
		t.Fatalf("stored key: %q %v", k, err)
	}
	st, err := Status()
	if err != nil || st != (StatusInfo{"authenticated", "stored", p}) {
		t.Fatalf("status: %v %v", st, err)
	}
}

func TestEnvKeyWinsOverCorruptFile(t *testing.T) {
	writeAuth(t, "[]")
	t.Setenv("BROWSER_USE_API_KEY", "envkey")
	if k, err := APIKey(); err != nil || k != "envkey" {
		t.Fatalf("APIKey: %q %v", k, err)
	}
	if st, err := Status(); err != nil || st.Source != "env" {
		t.Fatalf("Status: %v %v", st, err)
	}
}

func TestClearKeepsOtherEntries(t *testing.T) {
	p := writeAuth(t, `{"browser_use": {"api_key": "k"}, "other": 1}`)
	removed, err := Clear()
	if err != nil || !removed {
		t.Fatalf("Clear: %v %v", removed, err)
	}
	raw, _ := os.ReadFile(p)
	if m, err := loadFile(p); err != nil || len(m) != 1 || m["other"] == nil {
		t.Fatalf("after Clear: %s %v", raw, err)
	}
}
