package pyjson

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
)

// Loads parses JSON like json.loads: objects become Obj in document order
// (a repeated key keeps its first position and last value), numbers json.Number.
func Loads(data []byte) (any, error) {
	d := json.NewDecoder(bytes.NewReader(data))
	d.UseNumber()
	v, err := readValue(d)
	if err != nil {
		return nil, err
	}
	if _, err := d.Token(); err != io.EOF {
		return nil, errors.New("extra data after JSON value")
	}
	return v, nil
}

func readValue(d *json.Decoder) (any, error) {
	tok, err := d.Token()
	if err != nil {
		return nil, err
	}
	delim, ok := tok.(json.Delim)
	if !ok {
		return tok, nil
	}
	switch delim {
	case '{':
		o := Obj{}
		for d.More() {
			kt, err := d.Token()
			if err != nil {
				return nil, err
			}
			v, err := readValue(d)
			if err != nil {
				return nil, err
			}
			o = o.Set(kt.(string), v)
		}
		_, err = d.Token()
		return o, err
	case '[':
		a := []any{}
		for d.More() {
			v, err := readValue(d)
			if err != nil {
				return nil, err
			}
			a = append(a, v)
		}
		_, err = d.Token()
		return a, err
	}
	return nil, errors.New("unexpected delimiter")
}

// Get returns the value for k, like dict.get.
func (o Obj) Get(k string) any {
	for _, kv := range o {
		if kv.K == k {
			return kv.V
		}
	}
	return nil
}

// Has reports whether k is present, like `k in dict`.
func (o Obj) Has(k string) bool {
	for _, kv := range o {
		if kv.K == k {
			return true
		}
	}
	return false
}

// Set replaces k in place or appends it, like dict assignment.
func (o Obj) Set(k string, v any) Obj {
	for i := range o {
		if o[i].K == k {
			o[i].V = v
			return o
		}
	}
	return append(o, KV{k, v})
}
