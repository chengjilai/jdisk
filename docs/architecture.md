# Architecture Documentation

This document describes the architecture and design patterns used in jdisk.

## Project Structure

```
jdisk/
├── src/
│   └── jdisk/                     # Main package
│       ├── __init__.py           # Package initialization
│       ├── jdisk.py              # Main CLI entry point
│       ├── constants.py          # API constants and URLs
│       ├── cli/                  # Command line interface layer
│       │   ├── __init__.py
│       │   ├── main.py          # Main CLI entry point
│       │   ├── commands.py      # CLI command handlers
│       │   └── utils.py         # CLI utilities
│       ├── core/                 # Core business logic
│       │   ├── __init__.py
│       │   ├── session.py       # Session management
│       │   ├── operations.py    # High-level operations
│       │   └── config.py        # Configuration management
│       ├── services/             # Service layer
│       │   ├── __init__.py
│       │   ├── auth_service.py  # QR code authentication
│       │   ├── file_client.py   # File operations API
│       │   ├── uploader.py      # File upload service
│       │   └── downloader.py    # File download service
│       ├── models/               # Data models
│       │   ├── __init__.py
│       │   ├── data.py          # Core data models
│       │   ├── requests.py      # API request models
│       │   └── responses.py     # API response models
│       ├── utils/                # Utilities
│       │   ├── __init__.py
│       │   ├── errors.py        # Exception hierarchy
│       │   ├── validators.py    # Input validation
│       │   └── helpers.py       # Helper functions
│       ├── api/                  # API layer
│       │   ├── __init__.py
│       │   ├── client.py        # Base API client
│       │   ├── auth.py          # Authentication API
│       │   ├── files.py         # Files API
│       │   └── endpoints.py     # API endpoint definitions
├── docs/                         # Documentation
├── pyproject.toml                # Package configuration
└── README.md                     # User documentation
```

## Architecture Layers

### 1. CLI Layer (`cli/`)
**Purpose**: Command-line interface and argument parsing
- **Entry Point**: `main.py` - CLI initialization
- **Command Handlers**: `commands.py` - Command implementation
- **Utilities**: `utils.py` - CLI helper functions

**Key Components**:
- `CommandHandler`: Main command router
- Argument parsing with `argparse`
- Custom help formatting

### 2. Core Layer (`core/`)
**Purpose**: High-level business operations and session management
- **Session Management**: `session.py` - Authentication session handling
- **Operations**: `operations.py` - High-level file operations
- **Configuration**: `config.py` - Application configuration

**Key Components**:
- `SessionManager`: Persistent session storage and validation
- `NetdiskOperations`: High-level file operation orchestrator

### 3. Service Layer (`services/`)
**Purpose**: Specialized services for specific operations
- **Authentication**: `auth_service.py` - QR code authentication flow
- **File Client**: `file_client.py` - File operations API client
- **Uploader**: `uploader.py` - File upload implementation
- **Downloader**: `downloader.py` - File download implementation

**Key Design Patterns**:
- Service pattern for encapsulating business logic
- Dependency injection for testability
- Progress callback pattern for user feedback

### 4. Models Layer (`models/`)
**Purpose**: Data structures with validation
- **Core Models**: `data.py` - FileInfo, DirectoryInfo, etc.
- **Request Models**: `requests.py` - API request structures
- **Response Models**: `responses.py` - API response structures

**Key Features**:
- Type hints for all data structures
- Validation methods
- JSON serialization/deserialization

### 5. Utils Layer (`utils/`)
**Purpose**: Reusable utilities and error handling
- **Errors**: `errors.py` - Exception hierarchy
- **Validators**: `validators.py` - Input validation
- **Helpers**: `helpers.py` - Common utility functions

### 6. API Layer (`api/`)
**Purpose**: HTTP client abstraction
- **Base Client**: `client.py` - Common HTTP operations
- **Authentication**: `auth.py` - Auth-specific API calls
- **Files**: `files.py` - File operation API calls

## Key Design Patterns

### 1. Separation of Concerns
Each layer has a specific responsibility:
- **CLI**: User interface and command parsing
- **Core**: Business logic and orchestration
- **Services**: Specialized operation implementations
- **Models**: Data structures
- **Utils**: Cross-cutting concerns
- **API**: External communication

### 2. Dependency Injection
Services receive dependencies through constructors:
```python
class FileUploader:
    def __init__(self, auth_service: AuthService):
        self.auth = auth_service
```

### 3. Progress Callback Pattern
Long-running operations provide progress feedback:
```python
def progress_callback(uploaded: int, total: int):
    percent = (uploaded / total) * 100
    print(f"Progress: {percent:.1f}%")
```

### 4. Service Pattern
Complex operations are encapsulated in service classes:
- `AuthService`: Handles complete authentication flow
- `FileUploader`: Manages three-step upload process
- `FileDownloader`: Handles S3 presigned URL downloads

## Critical Implementation Decisions

### 1. Batch Move API Usage
**Problem**: Single file move API required complex S3 form upload handling
**Solution**: Used batch move API from JboxTransfer implementation
**Benefits**:
- Simpler implementation
- More reliable operation
- Support for multiple files in single request

### 2. Three-Step Upload Process
**Implementation**: AWS S3-like multipart upload
1. **Initiate**: Request upload credentials and URLs
2. **Upload**: Upload chunks to S3
3. **Confirm**: Verify upload completion

### 3. WebSocket Authentication
**Challenge**: QR code expiration and user feedback
**Solution**: Real-time WebSocket monitoring with auto-refresh
- QR codes refresh every 50 seconds
- WebSocket events for authentication status
- Automatic session capture

### 4. S3 Integration
**Direct Downloads**: Use S3 presigned URLs for fast downloads
- 302 redirects to S3
- 2-hour URL expiration
- Direct streaming from S3

## Error Handling Strategy

### Exception Hierarchy
```python
SJTUNetdiskError
├── AuthenticationError
├── APIError
├── NetworkError
└── ValidationError
```

### Error Recovery
- **Network Errors**: Automatic retry with exponential backoff
- **Authentication Errors**: Prompt for re-authentication
- **API Errors**: Graceful degradation with clear messages

## Security Considerations

### 1. Authentication
- QR codes use server-provided cryptographic signatures
- Sessions have limited lifetime (1 hour)
- Secure WebSocket communication

### 2. File Operations
- All API calls use HTTPS
- S3 URLs are presigned and time-limited
- No credentials stored in plain text

### 3. Session Management
- Sessions stored in user home directory
- File permissions: `600` (user read/write only)
- Automatic session cleanup on expiration

## Performance Optimizations

### 1. Chunked Uploads
- 4MB chunks optimal for network conditions
- Maximum 50 chunks per upload
- Parallel upload capability (future enhancement)

### 2. Direct S3 Downloads
- Bypass SJTU servers for file downloads
- Stream directly from S3 storage
- Progress tracking without full file buffering

### 3. Efficient Directory Listing
- Pagination support for large directories
- Lazy loading of directory contents
- Configurable page sizes

## Future Architecture Enhancements

### 1. Async Support
- Async/await for I/O operations
- Concurrent file uploads
- Non-blocking operations

### 2. Plugin System
- Extensible command system
- Custom output formatters
- Third-party integrations

### 3. Caching Layer
- File metadata caching
- Directory listing cache
- Session token caching
