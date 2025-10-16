# Implementation Details

This document provides detailed technical implementation information and insights gained during development.

## Critical Implementation Decisions

### 1. Batch Move API vs Single File Move API

#### Problem Encountered
Initially attempted to use the single file move API:
```
POST /api/v1/file/{library_id}/{space_id}/{source_path}?move=&access_token={access_token}
```

This API returned S3 form upload parameters that required complex multipart form data handling:
```json
{
  "domain": "s3pan.jcloud.sjtu.edu.cn",
  "form": {
    "key": "file_key",
    "Content-Type": "application/octet-stream",
    "policy": "base64_policy",
    "signature": "signature"
  }
}
```

#### Solution: Batch Move API
After researching JboxTransfer implementation, switched to the batch move API:
```
POST /api/v1/batch/{library_id}/{space_id}?move=&access_token={access_token}
```

**Benefits:**
- No S3 upload required - server handles everything
- Simpler implementation with standard JSON POST
- Support for multiple files in single request
- More reliable and atomic operations

**Implementation:**
```python
def _batch_move(self, from_paths: List[str], to_path: str) -> bool:
    url = f"{BASE_URL}{BATCH_MOVE_URL.format(library_id=self.auth.library_id, space_id=self.auth.space_id)}"

    batch_data = []
    for from_path in from_paths:
        clean_from_path = from_path.lstrip('/')
        filename = clean_from_path.split('/')[-1]

        # Construct destination path
        if to_path.endswith('/'):
            dest_path = to_path + filename
        else:
            dest_path = to_path

        file_info = self.get_file_info(from_path)
        is_dir = file_info.is_dir
        file_type = "" if is_dir else "file"

        batch_data.append({
            "from": clean_from_path,
            "to": dest_path.lstrip('/'),
            "type": file_type,
            "conflict_resolution_strategy": "rename",
            "moveAuthority": is_dir,
        })

    resp = self._make_request("POST", url, params=params, json=batch_data)
    # Handle response...
```

### 2. QR Code Authentication with Auto-Refresh

#### Challenge: QR Code Expiration
Initial implementation failed because QR codes expired after 60 seconds, requiring user to restart the process.

#### Solution: WebSocket Monitoring + Auto-Refresh
```python
class AuthService:
    def authenticate_with_qrcode(self):
        uuid = self._extract_uuid()
        ws_url = f"wss://jaccount.sjtu.edu.cn/ws/{uuid}"

        # Start QR code refresh timer (every 50 seconds)
        refresh_timer = threading.Timer(50.0, self._refresh_qr_code)
        refresh_timer.daemon = True
        refresh_timer.start()

        # Monitor WebSocket for authentication
        while not self.authenticated:
            try:
                message = websocket.recv()
                data = json.loads(message)
                if data.get("type") == "qr_code_status" and data.get("status") == "confirmed":
                    self._complete_authentication()
                    break
            except websocket.WebSocketTimeoutException:
                continue
```

**Key Insights:**
- QR codes must be refreshed before expiration (50-second interval)
- WebSocket provides real-time authentication status
- Server provides cryptographic signatures for QR codes

### 3. Three-Step Upload Process

#### S3 Integration Challenge
SJTU Netdisk uses AWS S3-compatible storage, requiring a multipart upload process similar to AWS S3.

#### Implementation: Three-Step Upload
```python
class FileUploader:
    def upload_file(self, local_path: str, remote_path: str, progress_callback=None):
        # Step 1: Initiate upload
        upload_info = self._start_upload(remote_path)

        # Step 2: Upload chunks
        with open(local_path, 'rb') as f:
            for chunk_num, chunk in enumerate(self._read_chunks(f)):
                self._upload_chunk(upload_info, chunk, chunk_num + 1, progress_callback)

        # Step 3: Confirm upload
        result = self._confirm_upload(upload_info.confirm_key)
        return result
```

**Chunk Upload Details:**
```python
def _upload_chunk(self, upload_info, chunk_data, part_number, progress_callback):
    url = f"https://{upload_info.domain}{upload_info.path}"
    headers = upload_info.parts[str(part_number)].headers

    params = {
        "uploadId": upload_info.upload_id,
        "partNumber": str(part_number)
    }

    resp = self.session.put(url, data=chunk_data, headers=headers, params=params)
    resp.raise_for_status()
```

### 4. Enhanced `ls` Command Implementation

#### Challenge: Unix-like Options
Users expect familiar Unix `ls` functionality with multiple sorting and formatting options.

#### Solution: Modular Display System
```python
class CommandHandler:
    def _handle_ls(self, remote_path: str, args) -> int:
        if args.recursive:
            return self._list_recursive(operations, remote_path, args)
        else:
            return self._list_directory(operations, remote_path, args)

    def _list_directory(self, operations, remote_path: str, args) -> int:
        dir_info = operations.list_files(remote_path)
        files = dir_info.get_files()
        directories = dir_info.get_directories()

        # Apply filters
        if not args.all:
            files = [f for f in files if not f.name.startswith('.')]
            directories = [d for d in directories if not d.name.startswith('.')]

        # Apply sorting
        if args.time:
            files.sort(key=lambda x: x.modification_time or "", reverse=not args.reverse)
            directories.sort(key=lambda x: x.modification_time or "", reverse=not args.reverse)
        elif args.size:
            files.sort(key=lambda x: int(x.size), reverse=not args.reverse)
        else:
            files.sort(key=lambda x: x.name.lower(), reverse=args.reverse)
            directories.sort(key=lambda x: x.name.lower(), reverse=args.reverse)

        # Display
        if args.long:
            self._print_long_listing(directories, files, args)
        else:
            self._print_simple_listing(directories, files, args)
```

**Format Output Examples:**
```
# Simple format with human sizes
AAA/                    fresh_new_directory/
debug_test.txt (13.0B)    introduction.md (5.9K)

# Long format
AAA/                          <DIR>           Oct 04 06:04
debug_test.txt                  13           Oct 16 10:21
introduction.md               6025           Oct 01 09:51
```

## Session Management Architecture

### Session Structure
```python
@dataclass
class Session:
    ja_auth_cookie: str
    user_token: str
    library_id: str
    space_id: str
    access_token: str
    username: str
    expires_at: datetime
```

### Session Storage
```python
class SessionManager:
    def __init__(self):
        self.session_file = Path.home() / ".jdisk" / "session.json"

    def save_session(self, session: Session):
        os.makedirs(self.session_file.parent, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump(asdict(session), f, indent=2)
        os.chmod(self.session_file, 0o600)  # User read/write only
```

### Session Validation
```python
def is_valid(self, session: Session) -> bool:
    if not session.access_token:
        return False

    # Check if session is expired
    if session.expires_at and datetime.now() >= session.expires_at:
        return False

    # Validate access token by making a test API call
    try:
        self._test_access_token(session.access_token)
        return True
    except APIError:
        return False
```

## Error Handling Strategy

### Exception Hierarchy
```python
class SJTUNetdiskError(Exception):
    """Base exception for jdisk errors."""
    pass

class AuthenticationError(SJTUNetdiskError):
    """Authentication related errors."""
    pass

class APIError(SJTUNetdiskError):
    """API request errors."""
    pass

class NetworkError(SJTUNetdiskError):
    """Network related errors."""
    pass

class ValidationError(SJTUNetdiskError):
    """Input validation errors."""
    pass
```

### Graceful Error Recovery
```python
def _handle_api_error(self, error: APIError):
    if "InvalidAccessToken" in str(error):
        print("Session expired. Please run 'jdisk auth' to re-authenticate.")
    elif "ResourceNotFound" in str(error):
        print("File or directory not found.")
    elif "SameNameDirectoryOrFileExists" in str(error):
        print("File already exists.")
    else:
        print(f"API Error: {error}")
```

## Performance Optimizations

### 1. Chunked Upload Strategy
```python
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks
MAX_CHUNKS = 50  # Maximum chunks per upload

def _read_chunks(self, file_handle):
    """Read file in chunks for upload."""
    while True:
        chunk = file_handle.read(CHUNK_SIZE)
        if not chunk:
            break
        yield chunk
```

### 2. Direct S3 Downloads
```python
def _get_download_url(self, remote_path: str) -> str:
    # Get presigned URL from SJTU API
    resp = self._make_request("GET", url, params=params, allow_redirects=False)

    if resp.status_code == 302:
        return resp.headers.get("Location")  # Direct S3 URL

    # Fallback to JSON response
    data = resp.json()
    return data.get("downloadUrl")
```

### 3. Efficient Directory Listing
```python
def list_directory(self, path: str, page: int = 1, page_size: int = 50):
    """List directory with pagination support."""
    params = {
        "page": page,
        "page_size": min(page_size, 100),  # Cap at 100 items
        "access_token": self.auth.access_token
    }
    # Implementation...
```

## Debugging and Troubleshooting Insights

### 1. Move Operation Issues
**Problem**: S3 policy validation errors (403 "Policy check failed")
**Root Cause**: Wrong API endpoint - single file move requires complex S3 form upload
**Solution**: Use batch move API which handles S3 operations server-side

### 2. QR Code Authentication Issues
**Problem**: QR codes expiring during authentication
**Root Cause**: Fixed 60-second expiration time
**Solution**: Auto-refresh every 50 seconds with WebSocket monitoring

### 3. Session Management Issues
**Problem**: Invalid access tokens
**Root Cause**: Tokens expire after 1 hour
**Solution**: Automatic token validation and re-authentication prompts

### 4. Upload Progress Tracking
**Problem**: No user feedback during large uploads
**Solution**: Progress callbacks with percentage and byte counters

## Testing Challenges and Solutions

### 1. API Rate Limiting
**Issue**: Too many API calls during testing
**Solution**: Mock external dependencies for unit tests, use test tokens for integration tests

### 2. Network Dependencies
**Issue**: Tests failing due to network issues
**Solution**: Test isolation with mocked HTTP responses

### 3. File System Dependencies
**Issue**: Tests requiring actual files
**Solution**: Temporary test files with proper cleanup

## Security Considerations

### 1. Credential Storage
```python
# Secure session storage
session_file = Path.home() / ".jdisk" / "session.json"
os.chmod(session_file, 0o600)  # User read/write only
```

### 2. URL Encoding
```python
# Proper URL encoding for API calls
import urllib.parse
encoded_path = urllib.parse.quote(path)
```

### 3. Input Validation
```python
def _validate_path(self, path: str) -> str:
    """Validate and normalize file paths."""
    if not path or path == "/":
        return "/"

    # Remove leading/trailing slashes
    path = path.strip("/")

    # Validate path components
    for component in path.split("/"):
        if not component or component in (".", ".."):
            raise ValidationError(f"Invalid path component: {component}")

    return "/" + path if path else "/"
```

## Future Enhancement Opportunities

### 1. Async Support
- Async/await for concurrent operations
- Parallel chunk uploads
- Non-blocking directory listings

### 2. Caching Layer
- File metadata caching
- Directory listing cache
- Session token caching

### 3. Plugin System
- Custom output formatters
- Additional commands
- Third-party integrations

This implementation has been thoroughly tested and refined based on real-world usage and API behavior. The solutions documented here represent actual challenges encountered during development and their working solutions.