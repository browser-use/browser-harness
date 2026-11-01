package assets

import (
	"os"
	"testing"
)

func TestSkillMatchesRoot(t *testing.T) {
	root, err := os.ReadFile("../../../SKILL.md")
	if err != nil {
		t.Fatal(err)
	}
	if string(root) != Skill {
		t.Fatal("go/internal/assets/SKILL.md differs from the root SKILL.md; copy it over")
	}
}
