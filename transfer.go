package main

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

const baseChunkSize = 5 * 1024 * 1024 // multipart part size floor
const maxPartNumber = 10000

// chunkSizeFor computes the part size so that the file splits into at most
// maxPartNumber parts.
func chunkSizeFor(size int64) int64 {
	chunk := int64(baseChunkSize)
	for chunk*int64(maxPartNumber) < size {
		chunk *= 2
	}
	return chunk
}

// cosError is a non-2xx response from the COS/S3 server.
type cosError struct{ status int }

func (e *cosError) Error() string { return fmt.Sprintf("COS PUT failed: HTTP %d", e.status) }

// Upload uploads localPath to remotePath on the netdisk. If overwrite is
// false, a name collision produces a renamed copy (server-side "rename").
//
// We never decide a size limit: a single-PUT upload is attempted first and
// multipart is only used when the server rejects it.
func (c *Client) Upload(localPath, remotePath string, overwrite bool, progress func(done, total int64)) error {
	st, err := os.Stat(localPath)
	if err != nil {
		return err
	}
	if st.IsDir() {
		return fmt.Errorf("%s is a directory", localPath)
	}
	if st.Size() == 0 {
		return errors.New("refusing to upload an empty file")
	}
	size := st.Size()
	strategy := "rename"
	if overwrite {
		strategy = "overwrite"
	}

	// Try the single-PUT path first.
	err = c.simpleUpload(localPath, remotePath, size, strategy, progress)
	if err == nil {
		return nil
	}

	// Fall back to multipart only if the server rejected the PUT itself
	// (e.g. the object is too large for one request). The rejection comes
	// from the Content-Length header, before any body is transferred.
	var ce *cosError
	if !errors.As(err, &ce) ||
		(ce.status != http.StatusBadRequest &&
			ce.status != http.StatusRequestEntityTooLarge &&
			ce.status != http.StatusNotImplemented) {
		return err
	}
	return c.multipartUpload(localPath, remotePath, size, strategy, progress)
}

func (c *Client) simpleUpload(localPath, remotePath string, size int64, strategy string, progress func(int64, int64)) error {
	info, err := c.InitSimpleUpload(remotePath, size, strategy)
	if err != nil {
		return fmt.Errorf("init upload: %w", err)
	}
	if err := putToCOS(transferHTTP, info.cosURL(), info.Headers, size, localPath, progress, 0); err != nil {
		c.cancelUpload(info.ConfirmKey) // best-effort: drop the pending upload
		return err
	}
	if err := c.ConfirmUpload(info.ConfirmKey, strategy); err != nil {
		return fmt.Errorf("confirm upload: %w", err)
	}
	return nil
}

func (c *Client) multipartUpload(localPath, remotePath string, size int64, strategy string, progress func(int64, int64)) error {
	chunk := chunkSizeFor(size)
	nparts := int((size + chunk - 1) / chunk)
	partRange := make([]int, nparts)
	for i := range partRange {
		partRange[i] = i + 1
	}
	info, err := c.InitMultipartUpload(remotePath, size, partRange, strategy)
	if err != nil {
		return fmt.Errorf("init multipart upload: %w", err)
	}

	var done int64
	for i := 1; i <= nparts; i++ {
		key := fmt.Sprintf("%d", i)
		ph, ok := info.Parts[key]
		if !ok {
			return fmt.Errorf("server did not authorize part %d", i)
		}
		start := int64(i-1) * chunk
		length := chunk
		if start+length > size {
			length = size - start
		}
		u := info.cosURL() + "?uploadId=" + info.UploadID + "&partNumber=" + key
		if err := putToCOS(transferHTTP, u, ph.Headers, length, localPath, nil, start); err != nil {
			return fmt.Errorf("part %d: %w", i, err)
		}
		done += length
		if progress != nil {
			progress(done, size)
		}
	}
	if err := c.ConfirmUpload(info.ConfirmKey, strategy); err != nil {
		return fmt.Errorf("confirm upload: %w", err)
	}
	return nil
}

// putToCOS streams a byte range of localPath to the presigned COS URL with the
// returned auth headers. Simple uploads pass offset 0 and the whole file.
func putToCOS(httpc *http.Client, url string, headers map[string]string, length int64, localPath string, progress func(int64, int64), offset int64) error {
	f, err := os.Open(localPath)
	if err != nil {
		return err
	}
	defer f.Close()
	if offset > 0 {
		if _, err := f.Seek(offset, io.SeekStart); err != nil {
			return err
		}
	}

	req, err := http.NewRequest(http.MethodPut, url, io.LimitReader(f, length))
	if err != nil {
		return err
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	req.ContentLength = length

	pr := &progressReader{r: req.Body, total: length, done: 0, progress: progress}
	req.Body = io.NopCloser(pr)

	resp, err := httpc.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	if resp.StatusCode >= 400 {
		return &cosError{status: resp.StatusCode}
	}
	return nil
}

type progressReader struct {
	r        io.Reader
	total    int64
	done     int64
	progress func(int64, int64)
}

func (p *progressReader) Read(b []byte) (int, error) {
	n, err := p.r.Read(b)
	p.done += int64(n)
	if p.progress != nil {
		p.progress(p.done, p.total)
	}
	return n, err
}

// Download streams remotePath to localPath, verifying the size afterwards.
func (c *Client) Download(remotePath, localPath string, progress func(done, total int64)) (int64, error) {
	fi, err := c.FileInfo(remotePath)
	if err != nil {
		return 0, err
	}
	if fi.CosURL == "" {
		return 0, fmt.Errorf("no download URL returned for %s", remotePath)
	}
	if localPath == "" || strings.HasSuffix(localPath, string(os.PathSeparator)) {
		base := filepath.Base(remotePath)
		if localPath == "" {
			localPath = base
		} else {
			localPath = filepath.Join(localPath, base)
		}
	}
	if err := os.MkdirAll(filepath.Dir(localPath), 0o755); err != nil {
		return 0, err
	}

	req, err := http.NewRequest(http.MethodGet, fi.CosURL, nil)
	if err != nil {
		return 0, err
	}
	resp, err := transferHTTP.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return 0, fmt.Errorf("download failed: HTTP %d", resp.StatusCode)
	}

	out, err := os.Create(localPath)
	if err != nil {
		return 0, err
	}
	defer out.Close()

	expected := int64(fi.Size)
	pr := &progressReader{r: resp.Body, total: expected, progress: progress}
	n, err := io.Copy(out, pr)
	if err != nil {
		os.Remove(localPath)
		return n, err
	}
	if expected > 0 && n != expected {
		os.Remove(localPath)
		return n, fmt.Errorf("size mismatch: got %d bytes, expected %d", n, expected)
	}
	return n, nil
}

// newProgress returns a progress callback that redraws a single-line
// percentage on stderr when stderr is a terminal, else prints nothing.
func newProgress(what string) func(done, total int64) {
	if !isTerminal(os.Stderr) {
		return nil
	}
	var last int64
	return func(done, total int64) {
		if total <= 0 {
			return
		}
		pct := done * 100 / total
		if pct == last {
			return
		}
		last = pct
		fmt.Fprintf(os.Stderr, "\r%s %s / %s (%d%%)    ", what,
			humanSize(done), humanSize(total), pct)
	}
}

func finishProgress() {
	if isTerminal(os.Stderr) {
		fmt.Fprintln(os.Stderr)
	}
}

func isTerminal(f *os.File) bool {
	st, err := f.Stat()
	if err != nil {
		return false
	}
	return st.Mode()&os.ModeCharDevice != 0
}

// humanSize formats bytes as B/K/M/G with one decimal.
func humanSize(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%dB", n)
	}
	div, exp := int64(unit), 0
	for m := n / unit; m >= unit; m /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f%c", float64(n)/float64(div), "KMGTPE"[exp])
}
