// Package assets holds files shipped inside the binary.
package assets

import _ "embed"

// Skill is SKILL.md, kept identical to the repository root copy (see assets_test.go).
//
//go:embed SKILL.md
var Skill string

// VideoTemplate renders compositions in the browser for video review and export.
//
//go:embed video-template.html
var VideoTemplate []byte
