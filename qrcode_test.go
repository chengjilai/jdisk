package main

import (
	"strings"
	"testing"
)

func TestRenderQR(t *testing.T) {
	out, err := renderQR("https://jaccount.sjtu.edu.cn/jaccount/confirmscancode?uuid=x&ts=1&sig=y")
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimRight(out, "\n"), "\n")
	if len(lines) < 20 {
		t.Fatalf("QR too small: %d lines", len(lines))
	}
	// must contain block characters and spaces
	if !strings.ContainsAny(out, "█▀▄ ") {
		t.Fatalf("QR lacks block chars")
	}
	// QR should be roughly square (rows = cols/2 because of half blocks)
	if len(lines) < len([]rune(lines[0]))/2 {
		t.Fatalf("QR aspect ratio wrong: %d lines vs %d cols", len(lines), len([]rune(lines[0])))
	}
	t.Logf("rendered %d x %d chars", len(lines), len([]rune(lines[0])))
}
