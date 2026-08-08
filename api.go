package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	baseURL   = "https://pan.sjtu.edu.cn"
	userAgent = "jdisk/0.1 (SJTU Netdisk CLI)"
)

// apiErr is the error envelope returned by the SMH API for failed requests.
type apiErr struct {
	Status  int    `json:"status"`
	Code    string `json:"code"`
	Message string `json:"message"`
}

func (e *apiErr) Error() string {
	if e.Code != "" {
		return fmt.Sprintf("%s: %s", e.Code, e.Message)
	}
	return e.Message
}

// Client talks to the SJTU Netdisk SMH API.
type Client struct {
	HTTP *http.Client // API calls (short timeout)

	LibraryID   string
	SpaceID     string
	AccessToken string
}

func NewClient(lib, space, token string) *Client {
	return &Client{
		HTTP:        &http.Client{Timeout: 60 * time.Second},
		LibraryID:   lib,
		SpaceID:     space,
		AccessToken: token,
	}
}

// transferHTTP has no timeout for large COS PUT/GET streaming.
var transferHTTP = &http.Client{}

// escapePath percent-encodes each path segment (names may contain spaces/unicode).
func escapePath(p string) string {
	parts := strings.Split(strings.Trim(p, "/"), "/")
	for i := range parts {
		parts[i] = url.PathEscape(parts[i])
	}
	return strings.Join(parts, "/")
}

// request performs an HTTP request against the SMH API and decodes the JSON
// response, translating API error envelopes into Go errors.
func (c *Client) request(method, path string, query url.Values, body []byte) ([]byte, error) {
	if query == nil {
		query = url.Values{}
	}
	query.Set("access_token", c.AccessToken)
	u := baseURL + path + "?" + query.Encode()

	var rdr io.Reader
	if body != nil {
		rdr = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, u, rdr)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		var e apiErr
		if json.Unmarshal(data, &e) == nil && e.Code != "" {
			return nil, fmt.Errorf("HTTP %d: %w", resp.StatusCode, &e)
		}
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
	}
	// Some errors are delivered with HTTP 200 and a status != 0 envelope.
	var probe map[string]any
	if json.Unmarshal(data, &probe) == nil {
		if st, _ := probe["status"].(float64); st != 0 && st != 200 {
			e := apiErr{
				Status:  int(st),
				Code:    str(probe["code"]),
				Message: str(probe["message"]),
			}
			return nil, &e
		}
	}
	return data, nil
}

func str(v any) string {
	s, _ := v.(string)
	return s
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

// --- auth ---

// RefreshAccessToken exchanges a USER_TOKEN (browser cookie credential) for a
// fresh accessToken plus library/space ids. Returns the new credential fields.
func RefreshAccessToken(userToken string) (lib, space, access string, err error) {
	u := baseURL + "/user/v1/space/1/personal?user_token=" + url.QueryEscape(userToken)
	req, err := http.NewRequest(http.MethodPost, u, nil)
	if err != nil {
		return "", "", "", err
	}
	req.Header.Set("User-Agent", userAgent)
	resp, err := (&http.Client{Timeout: 30 * time.Second}).Do(req)
	if err != nil {
		return "", "", "", err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", "", "", err
	}
	if resp.StatusCode >= 400 {
		return "", "", "", fmt.Errorf("login failed: HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
	}
	var out struct {
		LibraryID   string `json:"libraryId"`
		SpaceID     string `json:"spaceId"`
		AccessToken string `json:"accessToken"`
		ExpiresIn   int    `json:"expiresIn"`
	}
	if err := json.Unmarshal(data, &out); err != nil {
		return "", "", "", fmt.Errorf("login failed: bad response: %v", err)
	}
	if out.AccessToken == "" || out.LibraryID == "" || out.SpaceID == "" {
		return "", "", "", fmt.Errorf("login failed: incomplete response: %s", truncate(string(data), 200))
	}
	return out.LibraryID, out.SpaceID, out.AccessToken, nil
}

// --- directory listing ---

type Entry struct {
	Name             string   `json:"name"`
	Type             string   `json:"type"` // "dir" | "file"
	Size             Size     `json:"size"`
	ETag             string   `json:"eTag"`
	Crc64            string   `json:"crc64"`
	ContentType      string   `json:"contentType"`
	ModificationTime string   `json:"modificationTime"`
	CreationTime     string   `json:"creationTime"`
	UserID           string   `json:"userId"`
	Path             []string `json:"path"`
}

type ListResponse struct {
	Path        []string `json:"path"`
	Contents    []Entry  `json:"contents"`
	SubDirCount int      `json:"subDirCount"`
	FileCount   int      `json:"fileCount"`
	TotalNum    int      `json:"totalNum"`
}

// List returns all entries of a directory, following pagination.
func (c *Client) List(dirPath string) (*ListResponse, error) {
	var all []Entry
	var lastPath []string
	for page := 1; ; page++ {
		q := url.Values{}
		q.Set("page", strconv.Itoa(page))
		q.Set("page_size", "1000")
		data, err := c.request(http.MethodGet,
			"/api/v1/directory/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(dirPath), q, nil)
		if err != nil {
			return nil, err
		}
		var resp ListResponse
		if err := json.Unmarshal(data, &resp); err != nil {
			return nil, fmt.Errorf("list: bad response: %v", err)
		}
		lastPath = resp.Path
		all = append(all, resp.Contents...)
		if len(resp.Contents) == 0 || len(all) >= resp.TotalNum || page >= 100 {
			return &ListResponse{Path: lastPath, Contents: all,
				SubDirCount: resp.SubDirCount, FileCount: resp.FileCount, TotalNum: resp.TotalNum}, nil
		}
	}
}

// --- file info / download URL ---

type FileInfo struct {
	Name        string `json:"name"`
	Size        Size   `json:"size"`
	ETag        string `json:"eTag"`
	Crc64       string `json:"crc64"`
	ContentType string `json:"contentType"`
	CosURL      string `json:"cosUrl"`
}

// FileInfo returns metadata for a file, including a presigned COS download URL
// (valid 2h). The response omits name/path, so we fill Name from the input path.
func (c *Client) FileInfo(filePath string) (*FileInfo, error) {
	q := url.Values{}
	q.Set("info", "")
	q.Set("content_disposition", "attachment")
	data, err := c.request(http.MethodGet,
		"/api/v1/file/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(filePath), q, nil)
	if err != nil {
		return nil, err
	}
	var fi FileInfo
	if err := json.Unmarshal(data, &fi); err != nil {
		return nil, fmt.Errorf("file info: bad response: %v", err)
	}
	fi.Name = fileBase(filePath)
	return &fi, nil
}

// --- upload support ---

// uploadInitInfo is the common part of the initiate-upload response
// (both simple and multipart).
type uploadInitInfo struct {
	ConfirmKey string            `json:"confirmKey"`
	Domain     string            `json:"domain"`
	Path       string            `json:"path"`
	UploadID   string            `json:"uploadId"`
	Headers    map[string]string `json:"headers"` // simple upload: top-level
	Parts      map[string]part   `json:"parts"`   // multipart: per-part
}

type part struct {
	Headers map[string]string `json:"headers"`
}

// InitSimpleUpload prepares a single-PUT (simple) upload.
func (c *Client) InitSimpleUpload(filePath string, size int64, strategy string) (*uploadInitInfo, error) {
	q := url.Values{}
	q.Set("filesize", strconv.FormatInt(size, 10))
	q.Set("conflict_resolution_strategy", strategy)
	body := []byte(fmt.Sprintf(`{"size":%d}`, size))
	data, err := c.request(http.MethodPut,
		"/api/v1/file/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(filePath), q, body)
	if err != nil {
		return nil, err
	}
	var out uploadInitInfo
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("init upload: bad response: %v", err)
	}
	if out.ConfirmKey == "" || out.Domain == "" || out.Path == "" {
		return nil, fmt.Errorf("init upload: incomplete response: %s", truncate(string(data), 200))
	}
	return &out, nil
}

// InitMultipartUpload prepares a multipart upload for the given part numbers.
func (c *Client) InitMultipartUpload(filePath string, size int64, partRange []int, strategy string) (*uploadInitInfo, error) {
	q := url.Values{}
	q.Set("multipart", "")
	q.Set("filesize", strconv.FormatInt(size, 10))
	q.Set("conflict_resolution_strategy", strategy)
	body, err := json.Marshal(map[string]any{"partNumberRange": partRange})
	if err != nil {
		return nil, err
	}
	data, err := c.request(http.MethodPost,
		"/api/v1/file/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(filePath), q, body)
	if err != nil {
		return nil, err
	}
	var out uploadInitInfo
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("init multipart upload: bad response: %v", err)
	}
	if out.ConfirmKey == "" || out.Domain == "" || out.Path == "" || out.UploadID == "" {
		return nil, fmt.Errorf("init multipart upload: incomplete response: %s", truncate(string(data), 200))
	}
	return &out, nil
}

// ConfirmUpload finalizes an upload (simple or multipart).
func (c *Client) ConfirmUpload(confirmKey, strategy string) error {
	q := url.Values{}
	q.Set("confirm", "")
	q.Set("conflict_resolution_strategy", strategy)
	_, err := c.request(http.MethodPost,
		"/api/v1/file/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(confirmKey), q, []byte(`{}`))
	return err
}

// cancelUpload aborts a pending upload (best-effort; pending uploads also
// expire server-side).
func (c *Client) cancelUpload(confirmKey string) {
	q := url.Values{}
	q.Set("upload", "")
	c.request(http.MethodDelete,
		"/api/v1/file/"+c.LibraryID+"/"+c.SpaceID+"/"+escapePath(confirmKey), q, nil)
}

// cosURL builds the COS endpoint for a part upload.
func (info *uploadInitInfo) cosURL() string {
	return "https://" + info.Domain + info.Path
}

// Size parses the API's inconsistent size field, which appears as a JSON
// number in listings and as a string in file-info responses. Dirs have no
// size; we represent that as -1.
type Size int64

func (s *Size) UnmarshalJSON(b []byte) error {
	if len(b) == 0 || string(b) == "null" {
		*s = -1
		return nil
	}
	var n int64
	if err := json.Unmarshal(b, &n); err == nil {
		*s = Size(n)
		return nil
	}
	var str string
	if err := json.Unmarshal(b, &str); err != nil {
		return fmt.Errorf("invalid size %s", b)
	}
	v, err := strconv.ParseInt(str, 10, 64)
	if err != nil {
		return fmt.Errorf("invalid size %q", str)
	}
	*s = Size(v)
	return nil
}

func (s Size) String() string {
	if s < 0 {
		return ""
	}
	return strconv.FormatInt(int64(s), 10)
}

// Session caches the credentials needed to call the file API.
type Session struct {
	UserToken   string    `json:"userToken"`
	LibraryID   string    `json:"libraryId"`
	SpaceID     string    `json:"spaceId"`
	AccessToken string    `json:"accessToken"`
	ExpiresAt   time.Time `json:"expiresAt"`
}

func sessionPath() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "jdisk", "session.json"), nil
}

func loadSession() (*Session, error) {
	p, err := sessionPath()
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return nil, err
	}
	var s Session
	if err := json.Unmarshal(data, &s); err != nil {
		return nil, fmt.Errorf("corrupt session file %s: %v", p, err)
	}
	return &s, nil
}

func (s *Session) save() error {
	p, err := sessionPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(p, data, 0o600)
}

// expired reports whether the cached accessToken needs a refresh.
func (s *Session) expired() bool {
	return s.AccessToken == "" || time.Now().After(s.ExpiresAt)
}

// refresh re-exchanges the USER_TOKEN for a fresh accessToken.
func (s *Session) refresh() error {
	lib, space, access, err := RefreshAccessToken(s.UserToken)
	if err != nil {
		return fmt.Errorf("session expired and refresh failed (run `jdisk login`): %w", err)
	}
	s.LibraryID, s.SpaceID, s.AccessToken = lib, space, access
	s.ExpiresAt = time.Now().Add(25 * time.Minute) // token lifetime is 30 min
	return s.save()
}

// client returns an API client, refreshing the accessToken if needed.
func (s *Session) client() (*Client, error) {
	if s.expired() {
		if err := s.refresh(); err != nil {
			return nil, err
		}
	}
	return NewClient(s.LibraryID, s.SpaceID, s.AccessToken), nil
}
