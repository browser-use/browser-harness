package paths

import "strings"

func trimBOM(s string) string        { return strings.TrimPrefix(s, "\ufeff") }
func splitLines(s string) []string   { return strings.Split(strings.ReplaceAll(s, "\r\n", "\n"), "\n") }
func trimSpace(s string) string      { return strings.TrimSpace(s) }
func indexByte(s string, c byte) int { return strings.IndexByte(s, c) }

// trimQuotes strips leading/trailing double quotes, then single quotes.
func trimQuotes(s string) string { return strings.Trim(strings.Trim(s, `"`), `'`) }
