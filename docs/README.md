# jdisk Developer Documentation

This directory contains comprehensive documentation for developers working with the jdisk project.

## Documentation Structure

- [**architecture.md**](architecture.md) - Project architecture and design patterns
- [**api_reference.md**](api_reference.md) - Complete API reference and endpoints
- [**implementation_details.md**](implementation_details.md) - Technical implementation details
- [**troubleshooting.md**](troubleshooting.md) - Advanced troubleshooting guide

## Quick Links

### Core Components
- **Authentication**: QR code authentication with auto-refresh
- **File Operations**: Upload, download, list, move, delete operations
- **Session Management**: Persistent authentication with renewal
- **S3 Integration**: Direct transfers with progress tracking

### Key Implementation Notes
- Uses **batch move API** for file operations (not single file API)
- **Three-step upload process** similar to AWS S3 multipart upload
- **WebSocket communication** for real-time authentication monitoring
- **Auto-refresh mechanism** prevents QR code expiration

### Architecture Overview
```
jdisk/
├── src/jdisk/
│   ├── cli/           # Command line interface
│   ├── core/          # Core business logic
│   ├── services/      # Service layer (auth, upload, download)
│   ├── models/        # Data models
│   ├── utils/         # Utilities and helpers
│   └── api/           # API client layer
└── docs/              # Documentation
```

## Getting Started

For user documentation, see the main [README.md](../README.md) in the project root.
