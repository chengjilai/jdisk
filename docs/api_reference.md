# API Reference

This document provides a reference for the SJTU Netdisk API used by jdisk.

## Base Configuration

```
Base URL: https://pan.sjtu.edu.cn
Authentication: JAAuthCookie + OAuth 2.0
Storage Backend: AWS S3-compatible (s3pan.jcloud.sjtu.edu.cn)
```

## Authentication Flow

### 1. JAccount Authentication via JAAuthCookie

#### Generate QR Code
```
GET https://jaccount.sjtu.edu.cn/oauth2/authorize/xpw8ou8y
```

#### Token Exchange
```
POST https://pan.sjtu.edu.cn/user/v1/sign-in/verify-account-login/xpw8ou8y
Content-Type: application/json

{
  "credential": "{authorization_code}"
}
```

**Response:**
```json
{
  "userToken": "128-character token",
  "userId": "user_id",
  "organizations": [
    {
      "libraryId": "library_id",
      "orgUser": {
        "nickname": "username"
      }
    }
  ]
}
```

#### Personal Space Information
```
POST https://pan.sjtu.edu.cn/user/v1/space/1/personal
Content-Type: application/json

{
  "user_token": "128-character token"
}
```

**Response:**
```json
{
  "status": 0,
  "libraryId": "smh2ax67srucy60s",
  "spaceId": "space3jvslhfm2b78t",
  "accessToken": "acctk012a5bf334mgt82in6ghdw7nk8yrs8efrcktytx5nk95u6q7nq6p3qh23ajcwbxk7upx5p4fqnum9qdex3afkelum4jm6v924kfqz6w6d5ez4gvvccm56dbe8fc",
  "expiresIn": 1800,
  "message": "success"
}
```

## File Operations API

### Directory Listing

#### List Directory Contents
```
GET /api/v1/directory/{library_id}/{space_id}/{path}?access_token={access_token}&page={page}&page_size={size}&order_by={field}&order_by_type={asc|desc}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: Directory path (use "/" for root)
- `access_token`: Valid access token
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50)
- `order_by`: Sort field (name, size, modificationTime)
- `order_by_type`: Sort direction (asc, desc)

**Response:**
```json
{
  "path": [""],
  "contents": [
    {
      "name": "filename.txt",
      "type": "file",
      "size": "391",
      "modificationTime": "2025-10-16T10:28:15.000Z",
      "isDir": false,
      "path": ["filename.txt"],
      "contentType": "text/plain",
      "crc64": "11953636811276951993",
      "eTag": "\"f255a82c43f56b46de4057cc5a393430-1\""
    }
  ],
  "fileCount": 1,
  "subDirCount": 0,
  "totalNum": 1
}
```

### File Upload

#### Step 1: Initiate Upload
```
POST /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}&multipart=null&conflict_resolution_strategy={strategy}
Content-Type: application/json

{
  "partNumberRange": [1, 2, 3]
}
```

**Parameters:**
- `multipart`: Fixed value "null"
- `conflict_resolution_strategy`: "rename" or "overwrite"

**Response:**
```json
{
  "confirmKey": "unique_confirmation_key",
  "domain": "s3pan.jcloud.sjtu.edu.cn",
  "path": "/tced-private-{random}-sjtu/{library_id}/{confirmKey}.txt",
  "uploadId": "upload_id",
  "parts": {
    "1": {
      "headers": {
        "x-amz-date": "20251016T102800Z",
        "x-amz-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "authorization": "AWS4-HMAC-SHA256 Credential=..."
      }
    }
  },
  "expiration": "2025-10-16T11:13:00.569Z"
}
```

#### Step 2: Upload Chunks
```
PUT https://{domain}{path}?uploadId={uploadId}&partNumber={part_number}
Content-Type: application/octet-stream
Content-Length: {chunk_size}
x-amz-date: {x-amz-date}
authorization: {authorization}
x-amz-content-sha256: {x-amz-content-sha256}

[Binary chunk data]
```

#### Step 3: Confirm Upload
```
POST /api/v1/file/{library_id}/{space_id}/{confirmKey}?access_token={access_token}&confirm=null&conflict_resolution_strategy={strategy}
```

**Response:**
```json
{
  "path": ["folder", "filename.txt"],
  "name": "filename.txt",
  "type": "file",
  "creationTime": "2025-10-16T10:28:15.461Z",
  "modificationTime": "2025-10-16T10:28:15.461Z",
  "contentType": "text/plain",
  "size": "391",
  "eTag": "\"f255a82c43f56b46de4057cc5a393430-1\"",
  "crc64": "11953636811276951993",
  "metaData": {},
  "isOverwritten": false,
  "virusAuditStatus": 0,
  "sensitiveWordAuditStatus": 0,
  "previewByDoc": true,
  "previewByCI": true,
  "previewAsIcon": false,
  "fileType": "text"
}
```

### File Download

#### Request Download URL
```
GET /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}&download=true
```

**Response Flow:**
1. **302 Redirect** to AWS S3 presigned URL
2. **S3 URL** contains AWS4-HMAC-SHA256 signature with 2-hour expiration
3. **Direct Download** from `s3pan.jcloud.sjtu.edu.cn`

**S3 URL Pattern:**
```
https://s3pan.jcloud.sjtu.edu.cn/tced-private-{random}-sjtu/{library_id}/{file_id}.txt?
X-Amz-Algorithm=AWS4-HMAC-SHA256&
X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&
X-Amz-Credential={credentials}&
X-Amz-Date={timestamp}&
X-Amz-Expires=7200&
X-Amz-Signature={signature}&
X-Amz-SignedHeaders=host&
response-content-disposition=inline%3B%20filename%2A%3DUTF-8%27%27{filename}
```

### File Deletion

#### Delete File or Directory
```
DELETE /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}
```

**Response:**
- **Success**: HTTP 204 No Content or HTTP 200 OK
- **Error**: HTTP 404 Not Found, HTTP 403 Forbidden, HTTP 409 Conflict

### Directory Creation

#### Create Directory
```
PUT /api/v1/directory/{library_id}/{space_id}/{path}?conflict_resolution_strategy={strategy}&access_token={access_token}
```

**Parameters:**
- `conflict_resolution_strategy`: "ask" (default), "rename", or "overwrite"

**Response:**
```json
{
  "status": 0,
  "message": "success",
  "path": ["new", "directory"],
  "name": "directory",
  "type": "dir",
  "creationTime": "2025-10-16T10:30:00.000Z",
  "modificationTime": "2025-10-16T10:30:00.000Z"
}
```

### File Move/Rename

#### Batch Move or Rename Files
```
POST /api/v1/batch/{library_id}/{space_id}?move=&access_token={access_token}
Content-Type: application/json

[
  {
    "from": "source/file.txt",
    "to": "destination/file.txt",
    "type": "file",
    "conflict_resolution_strategy": "rename",
    "moveAuthority": false
  }
]
```

**Response:**
```json
{
  "result": [
    {
      "to": ["destination", "file.txt"],
      "from": ["source", "file.txt"],
      "path": ["destination", "file.txt"],
      "status": 200,
      "moveAuthority": false
    }
  ]
}
```

**Move Operations:**
- **Rename**: Set `to` to same directory with different filename
- **Move**: Set `to` to different directory path
- **Directory Move**: Set `moveAuthority: true` for directories
- **Batch Operations**: Multiple files can be moved in single request

## File Info

#### Get File Information
```
GET /api/v1/directory/{library_id}/{space_id}/{path}?info=&access_token={access_token}
```

**Response:**
```json
{
  "name": "filename.txt",
  "path": ["filename.txt"],
  "size": "391",
  "type": "file",
  "modificationTime": "2025-10-16T10:28:15.000Z",
  "isDir": false,
  "fileId": "file_id",
  "crc64": "11953636811276951993",
  "contentType": "text/plain",
  "eTag": "\"f255a82c43f56b46de4057cc5a393430-1\"",
  "downloadUrl": "https://s3pan.jcloud.sjtu.edu.cn/..."
}
```

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "status": 1,
  "code": "InvalidParameter",
  "message": "Invalid parameter value",
  "requestId": "request_id"
}
```

#### 401 Unauthorized
```json
{
  "status": 1,
  "code": "InvalidAccessToken",
  "message": "Access token is invalid or expired",
  "requestId": "request_id"
}
```

#### 404 Not Found
```json
{
  "status": 1,
  "code": "ResourceNotFound",
  "message": "File or directory does not exist",
  "requestId": "request_id"
}
```

#### 409 Conflict
```json
{
  "status": 1,
  "code": "SameNameDirectoryOrFileExists",
  "message": "File or directory already exists",
  "requestId": "request_id"
}
```

#### 413 Payload Too Large
```json
{
  "status": 1,
  "code": "FileTooLarge",
  "message": "File size exceeds limit",
  "requestId": "request_id"
}
```

## Rate Limiting

### Upload Constraints
- **Chunk Size**: 4MB chunks recommended (4,194,304 bytes)
- **Maximum Chunks**: 50 chunks per upload session
- **File Size Limit**: ~200MB per file (50 chunks × 4MB)
- **Conflict Resolution**: Supports "rename" and "overwrite" strategies

### Download Features
- **Streaming Support**: HTTP Range requests for partial downloads
- **Presigned URLs**: S3 URLs are valid for 2 hours
- **Integrity Verification**: CRC64 and ETag provided for file verification
- **Browser Compatible**: Uses standard HTTP redirects

## Authentication Requirements

### Session Management
- **Campus Network**: SJTU Netdisk typically requires connection through campus network or VPN
- **QR Code Authentication**: Scan with SJTU mobile app or visit authentication URL
- **Session Management**: Access tokens expire after 1 hour and need renewal

### Token Information
- **Access Token Format**: `acctk...` (SJTU-specific token)
- **Expiration**: 1 hour (1800 seconds)
- **Renewal**: Must repeat authentication process
- **Storage**: Stored locally in `~/.jdisk/session.json`

## WebSocket Communication

### QR Code Monitoring
```javascript
// WebSocket endpoint
wss://jaccount.sjtu.edu.cn/ws/{uuid}

// Message types
{
  "type": "qr_code_status",
  "status": "scanned|confirmed|expired"
}

// QR code refresh (every 50 seconds)
{
  "type": "refresh_request",
  "uuid": "session_uuid"
}
```
