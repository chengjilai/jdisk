# jdisk

A CLI tool for SJTU Netdisk


**Features:**
- QR Code Authentication - Simple and reliable authentication method
- Complete File Operations - Upload, download, list, navigate directories
- Smart Session Management - Persistent authentication with auto-renewal

---

## Quick Start

### Installation

#### Install from PyPI
```bash
pip install jdisk
```
or
```bash
uv tool install jdisk
```

#### Install from Source
```bash
git clone https://github.com/chengjilai/jdisk.git
cd jdisk

# Install dependencies using pixi
pixi install

# Make the jdisk script executable
chmod +x jdisk

# Verify installation
./jdisk --help
```

### First Time Authentication

```bash
jdisk auth
```

**Process:**
1. QR code displayed in terminal
2. Scan with SJTU mobile app

---

## Usage Examples

### Basic Operations

```bash
# Authentication
jdisk auth                    # QR code authentication

# Directory Listing
jdisk ls                      # List root directory
jdisk ls docs/                # List specific directory

# File Operations
jdisk upload file.txt         # Upload to root directory
jdisk upload file.txt docs/   # Upload to specific directory
jdisk download file.txt       # Download from root directory
jdisk download docs/file.txt  # Download from specific directory

# Directory Management
jdisk mkdir new_folder        # Create directory
jdisk mkdir -p path/to/nested # Create nested directories
jdisk rm file.txt             # Remove file
jdisk rm -r docs/             # Remove directory recursively
jdisk mv old.txt new.txt      # Rename file
jdisk mv file.txt docs/       # Move file to directory
```

### Advanced Usage

```bash
# Interactive operations
jdisk rm -i file.txt          # Remove with confirmation
jdisk rm -f nonexistent.txt   # Force remove (ignore errors)
jdisk rm -d empty_dir/        # Remove empty directory

# File operations with paths
jdisk upload ./local/file.txt /remote/path/
jdisk download /remote/file.txt ./local/
jdisk ls /folder/subfolder/
```


---

## Key Features

### Authentication
- **Session Persistence**: Save and reuse authentication
- **Auto-Refresh**: QR codes refresh to prevent expiration

### File Operations
- **Chunked Upload**: Efficient large file uploads with progress
- **Direct Download**: Fast downloads via S3 presigned URLs
- **Directory Navigation**: List and navigate directories
- **Secure Connections**: HTTPS/TLS for all communications

### User Experience
- **Terminal-Friendly**: Optimized for command-line usage
- **Mobile Support**: QR code scanning with mobile apps


---

## Authentication Method

### QR Code Authentication

**Features:**
- Auto-refresh prevents expiration
- Server-provided security signatures
- Real-time WebSocket communication

**How it works:**
1. Generate unique QR code with server signature
2. Scan with SJTU mobile app OR visit URL in browser
3. Login through SJTU JAccount website
4. System automatically captures authentication
5. QR code refreshes every 50 seconds to prevent expiration

**User Experience:**

QR Code Authentication for SJTU Netdisk
QR Code Generated:
[... QR code displayed in terminal ...]



---

## Project Structure

```
jdisk/
├── src/                           # Source code directory
│   └── jdisk/                 # Main package
│       ├── __init__.py           # Package initialization
│       ├── auth.py               # Authentication classes
│       ├── client.py             # Main API client
│       ├── cli.py                # CLI interface
│       ├── constants.py          # API constants and URLs
│       ├── download.py           # File download functionality
│       ├── exceptions.py         # Custom exception classes
│       ├── models.py             # Data models
│       ├── jdisk.py           # Main CLI entry point
│       └── upload.py             # File upload functionality
├── pyproject.toml                # Package configuration
├── README.md
├── LICENSE
├── pixi.lock
├── .git
└── .gitignore

```
---


## Dependencies

```toml
[dependencies]
requests
qrcode
websocket-client
```

---

## Technical Architecture

### **QR Code Authentication Flow**

1. Extract UUID from SJTU login page
2. Establish WebSocket connection to jaccount.sjtu.edu.cn
3. Request QR code signature from server
4. Generate QR code with server-provided sig/ts values
5. Display QR code and URL in terminal
6. Monitor WebSocket for authentication events
7. Auto-refresh QR code every 50 seconds
8. Capture JAAuthCookie upon successful login
9. Complete authentication process

### **Authentication Security**

- **Server-provided signatures**: QR codes use proper cryptographic signatures from SJTU servers
- **Auto-refresh mechanism**: Prevents QR code expiration with periodic updates every 50 seconds
- **Secure WebSocket communication**: Real-time, encrypted communication channels
- **Temporary sessions**: Unique UUID for each authentication session
- **Automatic cleanup**: Sessions expire and clean up automatically
- **Correct Space ID Handling**: QR code authentication now generates sessions with proper `space3jvslhfm2b78t` space_id

### **Space Info API Handling**

The space info API has been **FIXED** to handle both response formats:

#### **Success Response Format (Current):**
```json
{
  "libraryId": "smh2ax67srucy60s",
  "spaceId": "space3jvslhfm2b78t",
  "accessToken": "acctk019e278500mgm8qjucwuxta2j8swqemzv38ezcn2dzyqxm8ny2agd36pj6zfanmrhuh8way2vgjfs4asdph6s9b69z6zrjy27ulcmjdzqhv8yylpc56dbe8fc",
  "expiresIn": 1800
}
```

#### **Response Analysis:**
- **Status Field Not Required**: The API doesn't return a `"status"` field in successful responses
- **Correct Format**: All required fields are directly available (`library_id`, `space_id`, `accessToken`)
- **Proper Access Token**: Access token in format `acctk...` (SJTU-specific token)
- **Expires In**: Token has 30-minute expiration for security

### **Session Structure**

#### **QR Code Authentication:**
```json
{
  "ja_auth_cookie": "...",
  "user_token": "...",
  "library_id": "smh2...",
  "space_id": "space...",
  "access_token": "acctk...",        // SJTU-specific access token
  "username": "..."
}
```



### **File Upload Process**

Three-step chunked upload similar to AWS S3:

1. **Initiate**: Request upload permission and S3 URLs
2. **Upload**: Upload file chunks to S3 using provided credentials
3. **Confirm**: Verify upload completion and finalize file

### **File Download Process**

1. **Request**: Get download URL from SJTU Netdisk API
2. **Redirect**: Follow 302 redirect to S3 presigned URL
3. **Download**: Direct download from AWS S3 with progress tracking

### **Directory Creation Process**

1. **Path Validation**: Check and validate directory path
2. **Parent Creation**: With `-p` flag, create parent directories recursively
3. **API Request**: Send PUT request to directory creation endpoint
4. **Conflict Handling**: Handle existing directories gracefully
5. **Confirmation**: Return directory information on success

### **File Deletion Process**

1. **Path Validation**: Verify file or directory exists
2. **Permission Check**: Confirm user has deletion permissions
3. **Interactive Prompt**: With `-i` flag, prompt for confirmation
4. **Recursive Handling**: With `-r` flag, handle directory contents
5. **API Request**: Send DELETE request to file deletion endpoint
6. **Confirmation**: Return success status or error information

### **File Move/Rename Process**

1. **Source Validation**: Verify source file or directory exists
2. **Destination Check**: Validate destination path and permissions
3. **API Request**: Send POST request with move operation and destination
4. **Conflict Resolution**: Handle naming conflicts automatically
5. **Execution**: Perform atomic move operation on server
6. **Confirmation**: Return updated file/directory information


---

## API Reference

### **Base Configuration**
```
Base URL: https://pan.sjtu.edu.cn
Authentication: JAAuthCookie + OAuth 2.0
Storage Backend: AWS S3-compatible (s3pan.jcloud.sjtu.edu.cn)
```

### **Authentication Endpoints**

#### **JAccount Authentication via JAAuthCookie**
The SJTU Netdisk uses JAAuthCookie for authentication, which can be obtained from browser cookies after logging into [pan.sjtu.edu.cn](https://pan.sjtu.edu.cn).

**Authentication Endpoint:**
```
GET https://jaccount.sjtu.edu.cn/oauth2/authorize/xpw8ou8y
```

**Token Exchange:**
```
POST https://pan.sjtu.edu.cn/user/v1/sign-in/verify-account-login/xpw8ou8y
```

**Request Body:**
```json
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

**Personal Space Information:**
```
POST https://pan.sjtu.edu.cn/user/v1/space/1/personal
```

**Request Parameters:**
- `user_token`: 128-character user token

**Response:**
```json
{
  "status": 0,
  "libraryId": "library_id",
  "spaceId": "space_id",
  "accessToken": "access_token",
  "expiresIn": 3600,
  "message": "success"
}
```

### **File Upload API**

The upload process uses a three-step chunked approach similar to AWS S3 multipart upload.

#### **Step 1: Initiate Upload**
```
POST /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}&multipart=null&conflict_resolution_strategy={strategy}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: Remote file path (URL encoded)
- `access_token`: Valid access token
- `multipart`: Fixed value "null"
- `conflict_resolution_strategy`: "rename" or "overwrite"

**Request Body:**
```json
{
  "partNumberRange": [1, 2, 3]
}
```

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
        "x-amz-date": "20251011T025800Z",
        "x-amz-content-sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "authorization": "AWS4-HMAC-SHA256 Credential=..."
      }
    }
  },
  "expiration": "2025-10-11T03:13:00.569Z"
}
```

#### **Step 2: Upload Chunks**
```
PUT https://{domain}{path}?uploadId={uploadId}&partNumber={part_number}
```

**Headers:**
- `Content-Type`: `application/octet-stream`
- `Content-Length`: Chunk size in bytes
- `Accept`: `*/*`
- `Accept-Encoding`: `gzip, deflate, br`
- `Accept-Language`: `zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7`
- `x-amz-date`: From step 1 response
- `authorization`: From step 1 response
- `x-amz-content-sha256`: From step 1 response

**Request Body:**
Binary chunk data

#### **Step 3: Confirm Upload**
```
POST /api/v1/file/{library_id}/{space_id}/{confirmKey}?access_token={access_token}&confirm=null&conflict_resolution_strategy={strategy}
```

**Parameters:**
- `confirmKey`: From step 1 response
- `access_token`: Valid access token
- `confirm`: Fixed value "null"
- `conflict_resolution_strategy`: "rename" or "overwrite"

**Response:**
```json
{
  "path": ["folder", "filename.txt"],
  "name": "filename.txt",
  "type": "file",
  "creationTime": "2025-10-11T02:58:15.461Z",
  "modificationTime": "2025-10-11T02:58:15.461Z",
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

### **File Download API**

Downloads are handled through a redirect mechanism that provides AWS S3 presigned URLs.

#### **Download Request**
```
GET /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}&download=true
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: Remote file path
- `access_token`: Valid access token
- `download`: Fixed value "true"

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

### **Directory Listing API**

#### **List Directory Contents**
```
GET /api/v1/directory/{library_id}/{space_id}/{path}?access_token={access_token}&page={page}&page_size={size}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: Directory path (use "/" for root)
- `access_token`: Valid access token
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50)

**Response:**
```json
{
  "path": [""],
  "contents": [
    {
      "name": "filename.txt",
      "type": "file",
      "size": "391",
      "modificationTime": "2025-10-11T03:03:14.000Z",
      "isDir": false
    }
  ],
  "fileCount": 1,
  "subDirCount": 0,
  "totalNum": 1
}
```

### **Directory Creation API**

#### **Create Directory**
```
PUT /api/v1/directory/{library_id}/{space_id}/{path}?conflict_resolution_strategy={strategy}&access_token={access_token}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: Directory path to create (URL encoded)
- `conflict_resolution_strategy`: "ask" (default), "rename", or "overwrite"
- `access_token`: Valid access token

**Headers:**
- `Content-Type`: `application/json`
- `Accept`: `application/json`

**Response:**
```json
{
  "status": 0,
  "message": "success",
  "path": ["new", "directory"],
  "name": "directory",
  "type": "dir",
  "creationTime": "2025-01-15T10:30:00.000Z",
  "modificationTime": "2025-01-15T10:30:00.000Z"
}
```

### **File Deletion API**

#### **Delete File or Directory**
```
DELETE /api/v1/file/{library_id}/{space_id}/{path}?access_token={access_token}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `path`: File or directory path to delete (URL encoded)
- `access_token`: Valid access token

**Response:**
- **Success**: HTTP 204 No Content or HTTP 200 OK
- **Error**: HTTP 404 Not Found, HTTP 403 Forbidden, HTTP 409 Conflict

### **File Move/Rename API**

#### **Move or Rename File**
```
POST /api/v1/file/{library_id}/{space_id}/{source_path}?move=&access_token={access_token}
```

**Parameters:**
- `library_id`: User's library ID
- `space_id`: User's space ID
- `source_path`: Source file or directory path (URL encoded)
- `move`: Fixed parameter (indicates move operation)
- `access_token`: Valid access token

**Request Body:**
```json
{
  "to": "destination/path/file.txt",
  "conflict_resolution_strategy": "rename"
}
```

**Response:**
```json
{
  "status": 0,
  "message": "success",
  "path": ["destination", "path", "file.txt"],
  "name": "file.txt",
  "type": "file",
  "creationTime": "2025-01-15T10:30:00.000Z",
  "modificationTime": "2025-01-15T10:35:00.000Z",
  "contentType": "text/plain",
  "size": "1024"
}
```

**Move Operations:**
- **Rename**: Set `to` to same directory with different filename
- **Move**: Set `to` to different directory path
- **Directory Move**: Supports moving entire directories and their contents

---

### **Important Notes**

#### **Authentication Requirements**
- **Campus Network**: SJTU Netdisk typically requires connection through campus network or VPN
- **QR Code Authentication**: Scan with SJTU mobile app or visit authentication URL
- **Session Management**: Access tokens expire after 1 hour and need renewal

#### **Upload Constraints**
- **Chunk Size**: 4MB chunks recommended (4,194,304 bytes)
- **Maximum Chunks**: 50 chunks per upload session
- **File Size Limit**: ~200MB per file (50 chunks × 4MB)
- **Conflict Resolution**: Supports "rename" and "overwrite" strategies

#### **Download Features**
- **Streaming Support**: HTTP Range requests for partial downloads
- **Presigned URLs**: S3 URLs are valid for 2 hours
- **Integrity Verification**: CRC64 and ETag provided for file verification
- **Browser Compatible**: Uses standard HTTP redirects

#### **Directory Creation Features**
- **Parent Creation**: `-p` flag creates parent directories recursively
- **Conflict Resolution**: Handles existing directories gracefully
- **Path Validation**: Supports nested directory paths
- **Immediate Effect**: Directories are available immediately after creation

#### **File Deletion Features**
- **Recursive Delete**: `-r` flag removes directories and all contents
- **Interactive Mode**: `-i` flag prompts before each deletion
- **Force Mode**: `-f` flag ignores nonexistent files and suppresses errors
- **Directory-Only Delete**: `-d` flag removes only empty directories

#### **File Move/Rename Features**
- **Cross-Directory Moves**: Supports moving files between directories
- **Directory Relocation**: Can move entire directories with contents
- **Conflict Resolution**: Automatic renaming on conflicts
- **Atomic Operations**: Move operations are completed atomically

---

## 🚨 **Troubleshooting**

### **QR Code Issues**
- **"QR code expired"**: Fixed! Auto-refresh prevents expiration
- **"Invalid signature"**: Fixed! Uses server-provided signatures
- **"WebSocket timeout**: Check network connection to SJTU servers

### **Authentication Issues**
- **"QR code scan failed"**: Try scanning again or visit the provided URL directly
- **"Session expired"**: Run `jdisk auth` to re-authenticate
- **"Network error"**: Ensure VPN or campus network connection

### **File Operation Issues**
- **"Upload failed"**: Check file size and network connectivity
- **"Download error"**: Verify file exists and permissions
- **"Permission denied"**: Re-authenticate with valid session

### **Directory Creation Issues**
- **"Cannot create directory"**: Check parent directory permissions
- **"Directory already exists"**: Use existing directory or specify different name
- **"Invalid path"**: Ensure path follows valid naming conventions
- **"Parent creation failed"**: Check available space and permissions

### **File Deletion Issues**
- **"Cannot remove file"**: Verify file exists and you have deletion permissions
- **"Directory not empty"**: Use `-r` flag for recursive deletion
- **"Is a directory"**: Use `-r` flag to remove directories or `-d` for empty directories
- **"Permission denied"**: Re-authenticate or check file ownership

### **File Move/Rename Issues**
- **"Cannot move file"**: Verify source exists and destination is writable
- **"File already exists"**: System automatically handles conflicts with renaming
- **"Cross-device move error"**: This is not supported for cloud storage operations
- **"Invalid destination"**: Ensure destination path is valid and accessible

### **Error Handling**
- **Status Codes**: Standard HTTP status codes
- **Error Format**: JSON with `status`, `code`, `message`, and `requestId` fields
- **Common Errors**:
  - `400 Bad Request`: Missing parameters or invalid data
  - `401 Unauthorized`: Invalid or expired access token
  - `404 Not Found`: File or directory does not exist
  - `409 Conflict`: File already exists (when conflict_resolution_strategy is not set)
  - `413 Payload Too Large`: File exceeds size limits

---

## Development History

### Latest Updates
- QR Code Authentication: Simple and reliable authentication method
- Server-Provided Signatures: QR codes use proper cryptographic signatures
- Auto-Refresh Mechanism: QR codes refresh every 50 seconds
- Enhanced WebSocket Handling: Improved real-time communication
- Comprehensive Testing: All features verified and working

---

## License

MIT License

---

## Contributing

Contributions welcome! Please ensure:
- Code follows existing style
- Documentation is updated
- Features are backward compatible

---

**🎉 Enjoy using jdisk!**

For issues, feature requests, or questions, please check the documentation or create an issue.
