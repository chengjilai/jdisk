package main

import (
	"strings"

	qrcode "github.com/skip2/go-qrcode"
)

// renderQR renders a QR code to a terminal using half-block characters so the
// result is crisp when scanned from the screen.
func renderQR(content string) (string, error) {
	q, err := qrcode.New(content, qrcode.Medium)
	if err != nil {
		return "", err
	}
	bits := q.Bitmap() // [][]bool, already includes a quiet zone

	var sb strings.Builder
	// print two module rows per terminal line (top half / bottom half)
	for i := 0; i < len(bits); i += 2 {
		for j := 0; j < len(bits[i]); j++ {
			top := bits[i][j]
			bottom := i+1 < len(bits) && bits[i+1][j]
			switch {
			case top && bottom:
				sb.WriteString("█")
			case top:
				sb.WriteString("▀")
			case bottom:
				sb.WriteString("▄")
			default:
				sb.WriteString(" ")
			}
		}
		sb.WriteString("\n")
	}
	// terminal-specific width hint for the user
	return sb.String(), nil
}
