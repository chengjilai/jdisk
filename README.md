# jdisk

A CLI tool for SJTU Netdisk.

**Features:**
- 🔐 **QR Code Authentication** - Simple and secure login with auto-refresh
- 📁 **Complete File Operations** - Upload, download, list, move, delete operations
- 🔄 **Smart Session Management** - Persistent authentication with automatic renewal
- ⚡ **High-Speed Transfers** - Direct S3 integration with real-time progress tracking

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

# Option 1: Using pixi
pixi install
pixi run python src/jdisk/jdisk.py --help

# Option 2: Using hatch for packaging
hatch build
pip install dist/jdisk-*.whl

# Option 3: Development installation
pip install -e .

# Option 4: Using uv tool
hatch build
uv tool install -f dist/
```

### First Time Authentication

```bash
jdisk auth
```

**Process:**
1. QR code displayed in terminal with automatic refresh
2. Scan with SJTU mobile app
3. Authentication automatically captured and saved for future use

---

## Usage Examples

### Authentication
```bash
jdisk auth                    # QR code authentication
```

### Directory Listing
```bash
jdisk ls                      # List root directory (simple format)
jdisk ls docs/                # List specific directory
jdisk ls -l                   # Long listing format with details
jdisk ls -lH                  # Long format with human-readable sizes (B, K, M, G)
jdisk ls -lt                  # Sort by modification time (newest first)
jdisk ls -lS                  # Sort by file size (largest first)
jdisk ls -lr                  # Reverse sort order (oldest first)
jdisk ls -a                   # Show all files including hidden (starting with .)
jdisk ls -R                   # Recursive directory listing with tree structure
jdisk ls -lH -t               # Combine options: long format + human sizes + time sort
```

### File Operations
```bash
jdisk upload file.txt         # Upload to root directory with progress bar
jdisk upload file.txt docs/   # Upload to specific directory
jdisk download file.txt       # Download from root directory with progress tracking
jdisk download docs/file.txt  # Download from specific directory
```

### Directory Management
```bash
jdisk mkdir new_folder        # Create directory
jdisk mkdir -p path/to/nested # Create nested directories (parents created automatically)
jdisk rm file.txt             # Remove file
jdisk rm -r docs/             # Remove directory recursively with confirmation
jdisk mv old.txt new.txt      # Rename file (atomic operation)
jdisk mv file.txt docs/       # Move file to directory (batch move API)
```

### File operations with paths
```bash
jdisk upload ./local/file.txt /remote/path/
jdisk download /remote/file.txt ./local/
jdisk ls /folder/subfolder/
```

---

## Command Reference

### `ls` - List Directory Contents

| Option | Description | Example |
|--------|-------------|---------|
| `-l` | Long listing format with details | `jdisk ls -l` |
| `-H` | Human readable sizes (B, K, M, G) | `jdisk ls -lH` |
| `-t` | Sort by modification time (newest first) | `jdisk ls -lt` |
| `-S` | Sort by file size (largest first) | `jdisk ls -lS` |
| `-r` | Reverse sort order | `jdisk ls -lr` |
| `-a` | Show all files including hidden | `jdisk ls -a` |
| `-R` | Recursive directory listing | `jdisk ls -R` |

### `upload` - Upload Files
```bash
jdisk upload <local_path> [remote_path]
```

### `download` - Download Files
```bash
jdisk download <remote_path> [local_path]
```

### `mkdir` - Create Directories
```bash
jdisk mkdir <path> [-p]
```

### `rm` - Remove Files/Directories
```bash
jdisk rm <path> [-r]
```

### `mv` - Move/Rename Files
```bash
jdisk mv <source> <destination>
```

---

## Troubleshooting

### Authentication Issues
- **"QR code expired"**: Fixed with auto-refresh (QR codes refresh every 50 seconds)
- **"Network error"**: Ensure VPN or campus network connection to SJTU services
- **"Session expired"**: Run `jdisk auth` to re-authenticate (sessions last 30 minutes)
- **"Invalid signature"**: Restart authentication process and try again

### File Operation Issues
- **"Upload failed"**: Check file size (max ~200MB) and network connectivity
- **"Download error"**: Verify file exists and you have download permissions
- **"Permission denied"**: Re-authenticate with `jdisk auth` to refresh session
- **"Move failed"**: Ensure source file exists and destination path is valid

### Performance Issues
- **Slow uploads**: Check internet speed and try uploading smaller files first
- **Connection timeouts**: Use stable network connection, avoid WiFi if possible
- **Large directory listings**: Use specific paths instead of root directory

### Common Solutions
- Always run `jdisk auth` first if you get authentication errors
- Check network connection to SJTU servers (try `ping pan.sjtu.edu.cn`)
- Verify file paths are correct and use absolute paths starting with `/`
- Use `-p` flag with mkdir for creating nested directory structures
- For large file transfers, ensure stable internet connection

### Advanced Debugging
```bash
# Check session status
ls -la ~/.jdisk/session.json

# Test basic connectivity
curl -I https://pan.sjtu.edu.cn

# Reinstall if needed
uv tool uninstall jdisk && uv tool install jdisk
```

---

## License

MIT License

---

## Project Status

**✅ Fully Implemented Features:**
- ✅ QR Code Authentication with auto-refresh mechanism
- ✅ Complete file operations (upload, download, list, move, delete)
- ✅ Advanced directory listing with Unix-like options
- ✅ Direct S3 integration for high-speed transfers

For detailed documentation, development guides, and API reference, see the [docs/](docs/) directory.

---

**🎉 Enjoy using jdisk!**

For issues, feature requests, or questions, please create an issue on GitHub.
