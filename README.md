# jdisk

SJTU Netdisk CLI: `ls`, `download`, `upload`.

## Install

```sh
go install github.com/chengjilai/jdisk@latest
```

## Commands

```sh
jdisk login                  # QR login, scan with My SJTU app
jdisk ls [path] [-l]
jdisk download <remote> [local]
jdisk upload <local> [remote] [--overwrite]
```

Session cached in `~/.config/jdisk/session.json`, auto-refreshed.

## Verify

```sh
go vet ./...
go test ./...
```

## API schema

Base: `https://pan.sjtu.edu.cn`. Every file call takes `access_token` as a query
param (`Authorization` header is not accepted). Sizes appear as number (list) or
string (info) — parse both.

### Auth chain

| Step | Call |
|---|---|
| QR uuid | `GET https://my.sjtu.edu.cn/ui/appmyinfo` (follow redirects) → page contains `uuid=…` |
| QR sig | WS `wss://jaccount.sjtu.edu.cn/jaccount/sub/{uuid}`, send `{"type":"UPDATE_QR_CODE"}` → `{"type":"UPDATE_QR_CODE","payload":{"sig","ts"}}`; wait for `{"type":"LOGIN"}` |
| QR content | `https://jaccount.sjtu.edu.cn/jaccount/confirmscancode?uuid={uuid}&ts={ts}&sig={sig}` |
| cookie | `GET https://jaccount.sjtu.edu.cn/jaccount/expresslogin?uuid={uuid}` → sets `JAAuthCookie` |
| SSO URL | `GET /user/v1/organization/login-org-list` → `organizationList[0].corpId`; `GET /user/v1/sign-in/sso-login-redirect/{corpId}?auto_redirect=false` → `{"url"}` (jaccount authorize) |
| auth code | follow SSO url with jaccount cookies → redirect to `/login?code={code}` |
| userToken | `POST /user/v1/sign-in/verify-account-login/{corpId}?type=sso&credential={code}&device_id={d}` → `{userId, userToken, organizations:[{libraryId, orgUser:{nickname}}]}` |
| accessToken | `POST /user/v1/space/1/personal?user_token={userToken}` → `{libraryId, spaceId, accessToken, expiresIn:1800}` |

### File API

| Method | Path | Query params | Body | Returns |
|---|---|---|---|---|
| GET | `/api/v1/directory/{lib}/{space}[/{path}]` | `access_token` (+ `page`, `page_size`, `order_by`, `order_by_type`) | — | `{path[], contents:[{name,type,size,eTag,crc64,path[],modificationTime}], totalNum}` |
| GET | `/api/v1/file/{lib}/{space}/{path}` | `access_token`, `info`, `content_disposition=attachment` | — | `{size,eTag,crc64,contentType,cosUrl,cosUrlExpiration}` (no `name`; cosUrl valid 7200s) |
| GET | `{cosUrl}` | — | — | file bytes |
| PUT | `/api/v1/file/{lib}/{space}/{path}` | `access_token`, `filesize`, `conflict_resolution_strategy=rename\|overwrite` | `{"size":N}` (opt) | `{confirmKey,domain,path,headers}` (simple upload init) |
| PUT | `https://{domain}{path}` | — | file bytes; headers from init | 200 |
| POST | `/api/v1/file/{lib}/{space}/{confirmKey}` | `access_token`, `confirm`, `conflict_resolution_strategy` | `{}` | created file record |
| POST | same as simple init | `access_token`, `multipart`, `filesize`, `conflict_resolution_strategy` | `{"partNumberRange":[1..N]}` | `{confirmKey,domain,path,uploadId,parts:{N:{headers}}}` (multipart init) |
| PUT | `https://{domain}{path}?uploadId={id}&partNumber={i}` | — | part bytes; `parts[i].headers` | 200 |
| DELETE | `/api/v1/file/{lib}/{space}/{path}` | `access_token`, `permanent=0\|1` | — | 204 |

Upload: single PUT first; if the server rejects it (object too large for one
request), it is retried as multipart (chunk = max(5 MB, size/10000), ≤ 10000 parts).

Limits: no per-file API limit; only the space quota applies (this account:
1024 GiB quota — measured via `GET /api/v1/space/{lib}/{space}/size` and
`check-available-size?size=` → 204 if it fits). S3 protocol caps, taken from
the web client constants (not empirically exercised): single PUT ≤ 5 GiB,
≤ 10000 parts per multipart upload.

Errors: HTTP 404 body `{status,code,message}` (e.g. `DirectoryNotFound`,
`EmptyAccessToken`), some with HTTP 200 + `status != 0`.
