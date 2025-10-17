"""Constants and configuration for SJTU Netdisk API."""

# API URLs
BASE_URL = "https://pan.sjtu.edu.cn"
AUTH_URL = "https://jaccount.sjtu.edu.cn"

# API Endpoints
SSO_LOGIN_URL = "/user/v1/sign-in/sso-login-redirect/xpw8ou8y"
TOKEN_EXCHANGE_URL = "/user/v1/sign-in/verify-account-login/xpw8ou8y"
PERSONAL_SPACE_URL = "/user/v1/space/1/personal"
DIRECTORY_INFO_URL = "/api/v1/directory/{library_id}/{space_id}/{path}"
FILE_INFO_URL = "/api/v1/directory/{library_id}/{space_id}/{path}"
FILE_DOWNLOAD_URL = "/api/v1/file/{library_id}/{space_id}/{path}"
FILE_UPLOAD_URL = "/api/v1/file/{library_id}/{space_id}/{path}"
CREATE_DIRECTORY_URL = "/api/v1/directory/{library_id}/{space_id}/{path}"
FILE_DELETE_URL = "/api/v1/file/{library_id}/{space_id}/{path}"
FILE_MOVE_URL = "/api/v1/file/{library_id}/{space_id}/{path}"
BATCH_MOVE_URL = "/api/v1/batch/{library_id}/{space_id}"

# Configuration
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB
MAX_CHUNKS = 50
SESSION_FILE = "~/.jdisk/session.json"

# Headers
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Status codes
STATUS_SUCCESS = 0
STATUS_ERROR = 1

# Request timeout settings
DEFAULT_TIMEOUT = 30
UPLOAD_TIMEOUT = 300
DOWNLOAD_TIMEOUT = 300

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2
