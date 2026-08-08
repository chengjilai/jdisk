package main

import (
	"crypto/rand"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/gorilla/websocket"
)

const (
	jaccountBase = "https://jaccount.sjtu.edu.cn"
	mySJTUURL    = "https://my.sjtu.edu.cn/ui/appmyinfo"
)

var uuidRe = regexp.MustCompile(`uuid=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})`)
var codeRe = regexp.MustCompile(`code=([a-f0-9]+)`)

// loginWithQR performs the whole QR-code login flow:
//
//  1. visit my.sjtu.edu.cn to obtain a JAccount login uuid
//  2. open the JAccount QR WebSocket, display the QR in the terminal
//  3. once scanned & confirmed, grab the JAAuthCookie via expresslogin
//  4. SSO: authorize with pan.sjtu.edu.cn's client, get the auth code
//  5. exchange the code for a userToken, then for an accessToken
//
// Returns a saved session ready for use.
func loginWithQR() (*Session, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}
	httpc := &http.Client{
		Jar:     jar,
		Timeout: 30 * time.Second,
	}

	// 1. uuid
	uuid, err := fetchQRUUID(httpc)
	if err != nil {
		return nil, err
	}

	// 2. QR code (WebSocket)
	sig, ts, err := displayQRAndWait(httpc, uuid)
	if err != nil {
		return nil, err
	}
	_ = sig
	_ = ts

	// 3. express login -> JAAuthCookie
	if err := expressLogin(httpc, uuid); err != nil {
		return nil, err
	}

	// 4. SSO authorize -> code
	code, err := ssoAuthorize(httpc)
	if err != nil {
		return nil, err
	}

	// 5. code -> userToken
	userToken, nickname, err := exchangeCodeForUserToken(httpc, code)
	if err != nil {
		return nil, err
	}

	// 6. userToken -> accessToken
	lib, space, access, err := RefreshAccessToken(userToken)
	if err != nil {
		return nil, err
	}

	sess := &Session{
		UserToken:   userToken,
		LibraryID:   lib,
		SpaceID:     space,
		AccessToken: access,
		ExpiresAt:   time.Now().Add(25 * time.Minute),
	}
	if err := sess.save(); err != nil {
		return nil, err
	}
	fmt.Printf("logged in as %s\n", nickname)
	fmt.Printf("session saved to %s\n", mustSessionPath())
	return sess, nil
}

// fetchQRUUID visits the My SJTU page; when unauthenticated it lands on the
// JAccount login page which embeds the QR session uuid.
func fetchQRUUID(httpc *http.Client) (string, error) {
	resp, err := httpc.Get(mySJTUURL)
	if err != nil {
		return "", fmt.Errorf("my.sjtu.edu.cn unreachable: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	m := uuidRe.FindSubmatch(body)
	if m == nil {
		return "", fmt.Errorf("no QR uuid found on login page (are you already logged in to my.sjtu.edu.cn?)")
	}
	return string(m[1]), nil
}

// displayQRAndWait opens the JAccount QR WebSocket, renders the QR code to the
// terminal, re-requests a fresh signature every 30 s (re-rendering each time)
// so the code never expires while waiting, and blocks until it is scanned and
// confirmed (LOGIN message).
func displayQRAndWait(httpc *http.Client, uuid string) (sig string, ts string, err error) {
	wsURL := "wss://jaccount.sjtu.edu.cn/jaccount/sub/" + uuid
	dialer := websocket.Dialer{
		TLSClientConfig:   &tls.Config{},
		HandshakeTimeout:  10 * time.Second,
		Proxy:             http.ProxyFromEnvironment,
		EnableCompression: false,
	}

	connect := func() (*websocket.Conn, error) {
		ws, _, err := dialer.Dial(wsURL, nil)
		return ws, err
	}

	ws, err := connect()
	if err != nil {
		return "", "", fmt.Errorf("QR WebSocket connect failed: %w", err)
	}
	defer ws.Close()

	render := func(s, t string) {
		qrURL := fmt.Sprintf("%s/jaccount/confirmscancode?uuid=%s&ts=%s&sig=%s", jaccountBase, uuid, t, s)
		out, err := renderQR(qrURL)
		if err != nil {
			fmt.Printf("(qr render failed: %v)\n%s\n", err, qrURL)
			return
		}
		fmt.Print("\033[2J\033[H") // clear screen
		fmt.Println(out)
		fmt.Println("Scan with the SJTU mobile app (My SJTU) to log in.")
	}

	writeRefresh := func() { ws.WriteJSON(map[string]string{"type": "UPDATE_QR_CODE"}) }

	// reader goroutine: delivers messages, or a refresh signal when the server
	// goes quiet, or an error when the connection dies.
	type wsMsg struct {
		msg     []byte
		refresh bool
		err     error
	}
	msgCh := make(chan wsMsg, 2)
	readLoop := func() {
		for {
			ws.SetReadDeadline(time.Now().Add(25 * time.Second))
			_, msg, err := ws.ReadMessage()
			if err != nil {
				if ne, ok := err.(net.Error); ok && ne.Timeout() {
					msgCh <- wsMsg{refresh: true}
					continue
				}
				msgCh <- wsMsg{err: err}
				return
			}
			msgCh <- wsMsg{msg: msg}
		}
	}
	go readLoop()

	writeRefresh()

	lastSig, lastTs := "", ""
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	deadline := time.NewTimer(5 * time.Minute)
	defer deadline.Stop()

	for {
		select {
		case <-ticker.C:
			writeRefresh() // guaranteed refresh even if the server pushes heartbeats
		case <-deadline.C:
			return "", "", fmt.Errorf("QR code timed out after 5 minutes")
		case r := <-msgCh:
			if r.err != nil {
				// reconnect once and resume waiting
				ws2, err := connect()
				if err != nil {
					return "", "", fmt.Errorf("QR WebSocket error: %w", r.err)
				}
				ws.Close()
				ws = ws2
				go readLoop()
				writeRefresh()
				continue
			}
			if r.refresh {
				writeRefresh()
				continue
			}
			var m struct {
				Type    string `json:"type"`
				Error   int    `json:"error"`
				Payload struct {
					Sig string `json:"sig"`
					Ts  int64  `json:"ts"`
				} `json:"payload"`
			}
			if err := json.Unmarshal(r.msg, &m); err != nil {
				continue
			}
			if m.Error != 0 {
				return "", "", fmt.Errorf("QR code error from server (code %d)", m.Error)
			}
			switch strings.ToUpper(m.Type) {
			case "UPDATE_QR_CODE":
				if m.Payload.Sig != "" && m.Payload.Ts != 0 {
					lastSig, lastTs = m.Payload.Sig, fmt.Sprintf("%d", m.Payload.Ts)
					render(lastSig, lastTs)
				}
			case "LOGIN":
				return lastSig, lastTs, nil
			}
		}
	}
}

// expressLogin finalizes the QR scan and stores the JAAuthCookie in the jar.
func expressLogin(httpc *http.Client, uuid string) error {
	u := fmt.Sprintf("%s/jaccount/expresslogin?uuid=%s", jaccountBase, uuid)
	resp, err := httpc.Get(u)
	if err != nil {
		return fmt.Errorf("express login failed: %w", err)
	}
	io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("express login failed: HTTP %d", resp.StatusCode)
	}
	found := false
	for _, c := range httpc.Jar.Cookies(mustParseURL(jaccountBase)) {
		if c.Name == "JAAuthCookie" {
			found = true
			break
		}
	}
	if !found {
		return fmt.Errorf("no JAAuthCookie after QR scan")
	}
	return nil
}

func mustParseURL(s string) *url.URL {
	u, _ := url.Parse(s)
	return u
}

// ssoAuthorize redirects to pan.sjtu.edu.cn's SSO authorize endpoint and
// returns the one-time auth code from the /login?code=... redirect.
func ssoAuthorize(httpc *http.Client) (string, error) {
	// discover the org id and the authorize URL from the server
	corpID, err := loginOrgCorpID(httpc)
	if err != nil {
		return "", err
	}
	authzURL, err := ssoRedirectURL(httpc, corpID)
	if err != nil {
		return "", err
	}

	codeURL := ""
	httpc.CheckRedirect = func(req *http.Request, via []*http.Request) error {
		if strings.Contains(req.URL.String(), "code=") {
			codeURL = req.URL.String()
			return http.ErrUseLastResponse
		}
		if len(via) >= 10 {
			return fmt.Errorf("too many redirects during SSO")
		}
		return nil
	}
	resp, err := httpc.Get(authzURL)
	if err != nil && !strings.Contains(err.Error(), "use last response") && resp == nil {
		return "", fmt.Errorf("SSO authorize failed: %w", err)
	}
	if resp != nil {
		io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
		if codeURL == "" && resp.StatusCode >= 300 {
			if loc := resp.Header.Get("Location"); strings.Contains(loc, "code=") {
				codeURL = loc
			}
		}
	}
	if codeURL == "" {
		return "", fmt.Errorf("SSO did not return an auth code (JAccount session invalid?)")
	}
	m := codeRe.FindStringSubmatch(codeURL)
	if m == nil {
		return "", fmt.Errorf("no auth code in SSO redirect")
	}
	return m[1], nil
}

// loginOrgCorpID returns the organization id (e.g. "xpw8ou8y") for the netdisk
// deployment, from the public login-org-list endpoint.
func loginOrgCorpID(httpc *http.Client) (string, error) {
	resp, err := httpc.Get(baseURL + "/user/v1/organization/login-org-list")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var out struct {
		OrganizationList []struct {
			CorpID string `json:"corpId"`
		} `json:"organizationList"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	if len(out.OrganizationList) == 0 || out.OrganizationList[0].CorpID == "" {
		return "", fmt.Errorf("no organization found in login-org-list")
	}
	return out.OrganizationList[0].CorpID, nil
}

// ssoRedirectURL fetches the jaccount authorize URL for the org.
func ssoRedirectURL(httpc *http.Client, corpID string) (string, error) {
	u := fmt.Sprintf("%s/user/v1/sign-in/sso-login-redirect/%s?auto_redirect=false", baseURL, corpID)
	resp, err := httpc.Get(u)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var out struct {
		URL string `json:"url"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	if out.URL == "" {
		return "", fmt.Errorf("empty SSO redirect URL")
	}
	return out.URL, nil
}

// exchangeCodeForUserToken trades the SSO auth code for a userToken.
func exchangeCodeForUserToken(httpc *http.Client, code string) (userToken, nickname string, err error) {
	corpID, err := loginOrgCorpID(httpc)
	if err != nil {
		return "", "", err
	}
	q := url.Values{}
	q.Set("device_id", randomDeviceID())
	q.Set("type", "sso")
	q.Set("credential", code)
	u := fmt.Sprintf("%s/user/v1/sign-in/verify-account-login/%s?%s", baseURL, corpID, q.Encode())

	req, err := http.NewRequest(http.MethodPost, u, nil)
	if err != nil {
		return "", "", err
	}
	resp, err := httpc.Do(req)
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return "", "", fmt.Errorf("token exchange failed: HTTP %d: %s", resp.StatusCode, truncate(string(body), 200))
	}
	var out struct {
		Status        int    `json:"status"`
		Code          string `json:"code"`
		Message       string `json:"message"`
		UserToken     string `json:"userToken"`
		Organizations []struct {
			LibraryID string `json:"libraryId"`
			OrgUser   struct {
				Nickname string `json:"nickname"`
			} `json:"orgUser"`
		} `json:"organizations"`
	}
	if err := json.Unmarshal(body, &out); err != nil {
		return "", "", fmt.Errorf("token exchange: bad response: %v", err)
	}
	// an error envelope is present, or we simply got no token
	if out.Code != "" || out.UserToken == "" {
		msg := out.Message
		if msg == "" {
			msg = truncate(string(body), 200)
		}
		return "", "", fmt.Errorf("token exchange failed: %s", msg)
	}
	if len(out.UserToken) != 128 {
		return "", "", fmt.Errorf("token exchange returned invalid userToken (len %d)", len(out.UserToken))
	}
	name := ""
	if len(out.Organizations) > 0 {
		name = out.Organizations[0].OrgUser.Nickname
	}
	return out.UserToken, name, nil
}

func randomDeviceID() string {
	b := make([]byte, 8)
	rand.Read(b)
	return "jdisk-" + hex.EncodeToString(b)
}
