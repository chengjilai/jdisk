# Troubleshooting Guide

This guide covers common issues and their solutions when using and developing jdisk.

## User Issues

### Authentication Problems

#### QR Code Authentication

**Issue**: "QR code expired" or authentication timeout
**Solution**:
- QR codes auto-refresh every 50 seconds
- Simply wait for the next QR code to appear
- Ensure you have a stable internet connection

**Issue**: "Network error" during authentication
**Solution**:
- Ensure VPN or campus network connection
- Check internet connectivity
- Try authenticating during off-peak hours

**Issue**: "Invalid signature" error
**Solution**:
- Restart the authentication process
- Check if you're using the latest version
- Ensure you're not behind a proxy that blocks WebSocket connections

#### Session Issues

**Issue**: "Session expired" error during file operations
**Solution**:
```bash
jdisk auth  # Re-authenticate
```

**Issue**: "Authentication required" after recent auth
**Solution**:
- Check if session file exists: `ls -la ~/.jdisk/`
- Verify file permissions: `chmod 600 ~/.jdisk/session.json`
- Run `jdisk auth` to create fresh session

### File Operation Issues

#### Upload Problems

**Issue**: "Upload failed" with large files
**Solution**:
- Check file size (limit ~200MB)
- Ensure stable internet connection
- Split large files into smaller chunks

**Issue**: "Permission denied" during upload
**Solution**:
- Re-authenticate with `jdisk auth`
- Check if you have write permissions
- Verify destination directory exists

**Issue**: "File already exists" error
**Solution**:
- The upload system automatically handles conflicts
- Use a different filename if needed
- Check the file was uploaded with a number suffix

#### Download Problems

**Issue**: "Download error" or slow downloads
**Solution**:
- Verify file exists on server
- Check internet connection
- Try downloading during off-peak hours

**Issue**: "File not found" error
**Solution**:
- Verify file path is correct
- Use `jdisk ls` to list files
- Check if file was moved or deleted

#### Directory Operations

**Issue**: "Directory not found" error
**Solution**:
- Use `jdisk ls /` to see available directories
- Check spelling and case sensitivity
- Use absolute paths starting with `/`

**Issue**: Cannot create nested directories
**Solution**:
```bash
jdisk mkdir -p path/to/nested/directory
```

**Issue**: "Directory not empty" when trying to delete
**Solution**:
```bash
jdisk rm -r directory_name
```

#### Move/Rename Issues

**Issue**: "Move failed" or "Cannot move file"
**Solution**:
- Verify source file exists
- Check destination permissions
- Ensure both paths are correct
- Try moving to a different location first

### Listing Issues

**Issue**: `ls` command shows no output
**Solution**:
- Check if directory is empty
- Use `jdisk ls -a` to show hidden files
- Verify you're in the correct directory

**Issue**: `ls -R` shows too much output
**Solution**:
- Use `jdisk ls -R | head -20` to see first 20 lines
- Use specific directory path instead of root
- Use `jdisk ls -R /specific/path` for targeted listing

## Development Issues

### Setup Problems

#### Installation Issues

**Issue**: "No module named 'jdisk'" error
**Solution**:
```bash
# Install from source
cd jdisk
pixi install

# Or install in development mode
pip install -e .
```

**Issue**: Import errors when running tests
**Solution**:
```bash
# Ensure you're in the project root
cd /path/to/jdisk
# Install development dependencies
pip install -e ".[dev]"
```

#### Environment Issues

**Issue**: Python version incompatibility
**Solution**:
- Ensure Python 3.8+ is installed
- Use `python --version` to check
- Update Python if necessary

**Issue**: pixi not found
**Solution**:
```bash
# Install pixi
curl -fsSL https://pixi.sh/install.sh | sh
# Follow installation instructions
```

### Code Issues

#### Import Problems

**Issue**: Relative import errors
**Solution**:
```python
# Correct import
from ..services.auth_service import AuthService

# Not correct
from services.auth_service import AuthService
```

**Issue**: Module not found errors
**Solution**:
- Check PYTHONPATH includes project src directory
- Run from project root
- Use `export PYTHONPATH=$PWD/src:$PYTHONPATH`

#### API Integration Issues

**Issue**: API rate limiting during development
**Solution**:
- Use mocked responses for unit tests
- Implement delays between API calls
- Cache test results

**Issue**: WebSocket connection failures
**Solution**:
- Check internet connectivity
- Verify firewall allows WebSocket connections
- Mock WebSocket for unit tests

### Testing Issues

#### Test Failures

**Issue**: Tests failing with authentication errors
**Solution**:
```bash
# Set test mode environment variable
export JDISK_TEST_MODE=true

# Or create test session file
mkdir -p ~/.jdisk
echo '{"access_token": "test_token"}' > ~/.jdisk/session.json
```

**Issue**: File not found errors in tests
**Solution**:
- Use temporary test files
- Clean up test files after tests
- Use relative paths from project root

**Issue**: Network-related test failures
**Solution**:
- Mock external API calls
- Use pytest fixtures for test data
- Mark integration tests with appropriate markers

### Performance Issues

#### Slow Operations

**Issue**: Uploads are very slow
**Solution**:
- Check internet connection speed
- Reduce chunk size if needed
- Use progress monitoring

**Issue**: Directory listing takes too long
**Solution**:
- Use pagination with smaller page sizes
- Cache directory listings when appropriate
- Use filters to reduce results

#### Memory Issues

**Issue**: High memory usage with large files
**Solution**:
- Use streaming uploads instead of loading entire file
- Process files in chunks
- Implement garbage collection for temporary data

## Debugging Techniques

### 1. Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add debug logging to specific functions
def _debug_api_call(self, method, url, **kwargs):
    logger.debug(f"{method} {url}")
    logger.debug(f"Headers: {kwargs.get('headers', {})}")
    response = self.session.request(method, url, **kwargs)
    logger.debug(f"Status: {response.status_code}")
    return response
```

### 2. Use pdb for Debugging

```python
import pdb

def problematic_function(self, data):
    pdb.set_trace()  # Set breakpoint
    # Debug code here
    result = self._process_data(data)
    return result
```

### 3. Print Debug Information

```python
def _debug_response(self, response, operation=""):
    """Print debug information for API response."""
    print(f"\n=== DEBUG: {operation} ===")
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")

    if response.headers.get('Content-Type', '').startswith('application/json'):
        try:
            print(f"Body: {response.json()}")
        except:
            print("Body: [Unable to parse JSON]")
    else:
        print("Body: [Binary data]")
    print("=" * 40)
```

### 4. Network Debugging

```python
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Configure session with retries
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
```

## Common Error Messages and Solutions

### Authentication Errors

| Error | Cause | Solution |
|-------|--------|---------|
| "QR code expired" | QR code timeout | Wait for auto-refresh |
| "Invalid signature" | WebSocket issue | Restart authentication |
| "Session expired" | Token timeout | Run `jdisk auth` |
| "Authentication required" | No valid session | Run `jdisk auth` |

### File Operation Errors

| Error | Cause | Solution |
|-------|--------|---------|
| "Permission denied" | Invalid session | Re-authenticate |
| "File not found" | Wrong path | Check with `jdisk ls` |
| "Upload failed" | Network/file issue | Check file size, retry |
| "Directory not found" | Wrong path | List directories first |

### Network Errors

| Error | Cause | Solution |
|-------|--------|---------|
| "Connection timeout" | Network issues | Check connection, retry |
| "SSL verification failed" | Certificate issue | Check system time/certificates |
| "DNS resolution failed" | Network DNS issue | Check DNS settings |

## Getting Help

### 1. Check Logs

```bash
# Check for error logs
tail -f ~/.jdisk/logs/jdisk.log

# Check system logs for network issues
tail -f /var/log/syslog
```

### 2. Test Basic Functionality

```bash
# Test basic connectivity
ping pan.sjtu.edu.cn

# Test authentication
jdisk auth

# Test simple operations
jdisk ls /
jdisk ls -l
```

### 3. Report Issues

When reporting issues, include:
- Operating system and version
- Python version
- jdisk version
- Complete error message
- Steps to reproduce
- Network environment (VPN, campus network, etc.)

### 4. Community Support

- Check GitHub issues for similar problems
- Search documentation before asking
- Provide detailed information when asking for help

## Performance Optimization

### 1. Upload Optimization

```python
# Optimal chunk size for SJTU Netdisk
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks

# Maximum chunks per upload
MAX_CHUNKS = 50

# Progress callback for user feedback
def progress_callback(uploaded: int, total: int):
    if total > 0:
        percent = (uploaded / total) * 100
        print(f"\rProgress: {percent:.1f}%")
```

### 2. Download Optimization

```python
# Use streaming for large files
def download_with_stream(self, url: str, local_path: str):
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
```

### 3. Memory Management

```python
# Process files in chunks
def process_large_file(self, file_path: str):
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(4096)  # 4KB chunks
            if not chunk:
                break
            yield chunk
```

This troubleshooting guide should help resolve most common issues with jdisk. For additional help, consult the documentation or create an issue on GitHub.