// Package tabs classifies browser tabs by URL and title, the same way in the daemon and the helpers.
package tabs

import (
	"os"
	"strings"

	"github.com/browser-use/browser-harness/go/internal/paths"
)

// Mark and Unmark add and remove the 🐴 title prefix on the tab the harness controls.
const (
	Mark   = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"
	Unmark = "if(document.title.startsWith('\U0001F434 '))document.title=document.title.slice(3)"
)

// Marked is whether the controlled tab gets the title marker (BH_TAB_MARKER=0 turns it off).
func Marked() bool { return !paths.Disabled(os.Getenv("BH_TAB_MARKER")) }

// Internal is a browser page, such as chrome:// or about:.
func Internal(url string) bool {
	return hasPrefix(url, "chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
}

// AboutBlank is about:blank, with or without a fragment.
func AboutBlank(url string) bool {
	return url == "about:blank" || strings.HasPrefix(url, "about:blank#")
}

// NewTabPage is a browser's new tab page.
func NewTabPage(url string) bool {
	return hasPrefix(url, "chrome://newtab", "chrome://new-tab-page", "edge://newtab", "about:newtab")
}

// Placeholder is a blank tab another agent opened and is still claiming.
func Placeholder(title, url string) bool {
	return strings.HasPrefix(title, "Starting agent ") && (url == "" || AboutBlank(url))
}

func hasPrefix(s string, prefixes ...string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}
