// Package pyjson renders JSON byte-for-byte like Python's json.dumps defaults
// (", " and ": " separators, ensure_ascii), for outputs agents and scripts parse.
package pyjson

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

// KV is one ordered object member.
type KV struct {
	K string
	V any
}

// Obj is an object that keeps insertion order, like a Python dict.
type Obj []KV

// Dumps renders v; indent > 0 matches json.dumps(indent=n). Plain maps are
// rendered with sorted keys (callers that need insertion order use Obj).
func Dumps(v any, indent int) string {
	var b strings.Builder
	write(&b, v, indent, 0)
	return b.String()
}

func write(b *strings.Builder, v any, indent, depth int) {
	switch t := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if t {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case string:
		writeString(b, t)
	case int:
		b.WriteString(strconv.Itoa(t))
	case int64:
		b.WriteString(strconv.FormatInt(t, 10))
	case float64:
		writeFloat(b, t)
	case json.Number:
		b.WriteString(t.String())
	case json.RawMessage:
		var x any
		d := json.NewDecoder(strings.NewReader(string(t)))
		d.UseNumber()
		if d.Decode(&x) != nil {
			b.WriteString("null")
			return
		}
		write(b, x, indent, depth)
	case Obj:
		writeObj(b, t, indent, depth)
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		o := make(Obj, len(keys))
		for i, k := range keys {
			o[i] = KV{k, t[k]}
		}
		writeObj(b, o, indent, depth)
	case map[string]string:
		m := make(map[string]any, len(t))
		for k, x := range t {
			m[k] = x
		}
		write(b, m, indent, depth)
	case []any:
		writeArr(b, t, indent, depth)
	case []string:
		a := make([]any, len(t))
		for i, s := range t {
			a[i] = s
		}
		writeArr(b, a, indent, depth)
	default:
		// Structs and other values: round-trip through encoding/json.
		raw, err := json.Marshal(t)
		if err != nil {
			b.WriteString("null")
			return
		}
		write(b, json.RawMessage(raw), indent, depth)
	}
}

func newline(b *strings.Builder, indent, depth int) {
	if indent > 0 {
		b.WriteByte('\n')
		b.WriteString(strings.Repeat(" ", indent*depth))
	}
}

func writeObj(b *strings.Builder, o Obj, indent, depth int) {
	if len(o) == 0 {
		b.WriteString("{}")
		return
	}
	b.WriteByte('{')
	for i, kv := range o {
		if i > 0 {
			b.WriteByte(',')
			if indent == 0 {
				b.WriteByte(' ')
			}
		}
		newline(b, indent, depth+1)
		writeString(b, kv.K)
		b.WriteString(": ")
		write(b, kv.V, indent, depth+1)
	}
	newline(b, indent, depth)
	b.WriteByte('}')
}

func writeArr(b *strings.Builder, a []any, indent, depth int) {
	if len(a) == 0 {
		b.WriteString("[]")
		return
	}
	b.WriteByte('[')
	for i, x := range a {
		if i > 0 {
			b.WriteByte(',')
			if indent == 0 {
				b.WriteByte(' ')
			}
		}
		newline(b, indent, depth+1)
		write(b, x, indent, depth+1)
	}
	newline(b, indent, depth)
	b.WriteByte(']')
}

func writeFloat(b *strings.Builder, f float64) {
	switch {
	case math.IsNaN(f):
		b.WriteString("NaN")
	case math.IsInf(f, 1):
		b.WriteString("Infinity")
	case math.IsInf(f, -1):
		b.WriteString("-Infinity")
	case f == math.Trunc(f) && math.Abs(f) < 1e16:
		b.WriteString(strconv.FormatFloat(f, 'f', 1, 64))
	default:
		b.WriteString(strconv.FormatFloat(f, 'g', -1, 64))
	}
}

func writeString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			// ensure_ascii: escape everything outside printable ASCII, like Python.
			switch {
			case r >= 0x20 && r <= 0x7e:
				b.WriteRune(r)
			case r >= 0x10000:
				r1, r2 := utf16.EncodeRune(r)
				fmt.Fprintf(b, `\u%04x\u%04x`, r1, r2)
			default:
				fmt.Fprintf(b, `\u%04x`, r)
			}
		}
	}
	b.WriteByte('"')
}
