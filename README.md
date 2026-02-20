# ftp-sync

Sync a local folder with an FTP folder. Supports both download and upload directions with concurrent operations and recursive subfolder syncing.

## Features

- **Bidirectional sync** — download from FTP to local (`down`) or upload from local to FTP (`up`)
- **Recursive subfolder sync** — syncs all files and subdirectories, creating missing directories automatically
- **Concurrent operations** — configurable number of parallel uploads/downloads
- **Skip unchanged files** — files with matching sizes are skipped
- **Old file handling** — when downloading, local files no longer on the server are moved to an `old` subfolder
- **CLI overrides** — override `LOCAL_DIRECTORY` and `FTP_DIRECTORY` from the command line
- **Auto-create FTP directories** — target FTP directory is created if it does not exist

## Install

- Make sure you have Python 3.11+ installed
- `pip install -r requirements.txt`
- Copy `settings_example.ini` and fill in the required fields

## Usage

```
python main.py <settings_file> [--local-dir <path>] [--ftp-dir <path>]
```

### Examples

Basic usage with INI file:
```
python main.py settings.ini
```

Override directories via CLI:
```
python main.py settings.ini --local-dir "C:\my\local\folder" --ftp-dir "/remote/path"
```

### INI file format

```ini
[FTP]
LOCAL_DIRECTORY = c:\ftp_backup
FTP_DIRECTORY = /remote/path
FTP_HOST = server.com
FTP_USER = user
FTP_PASS = password

# Direction of sync: down = FTP to local, up = local to FTP
DIRECTION = down

# Number of concurrent uploads or downloads (default: 1)
CONCURRENT_UPLOADS_OR_DOWNLOADS = 1
```

`LOCAL_DIRECTORY` and `FTP_DIRECTORY` are optional in the INI file if provided via `--local-dir` / `--ftp-dir` CLI arguments.
