# pixel-backup

Automatically sync your Immich library to Google Photos using an old Google Pixel as a backup device.

## Why?

Older Google Pixels (Pixel 1 with original quality, Pixel 2-5 with compressed quality) offer unlimited photo storage to Google Photos. While they make excellent backup devices for Immich libraries, the standard Syncthing approach has limitations:

- Running Syncthing on your primary phone requires persistent background services that drain battery
- Photos sync twice from your primary phone: first to Immich, then separately to the backup Pixel
- Limited storage on the backup device requires constant manual management
- Multi-user setups with separate devices become difficult to maintain

This tool optimizes the workflow by syncing directly from your Immich library using hard links, with Syncthing running only on the server. This eliminates redundant transfers and simplifies the backup process.

## Features

- **Automated Syncing**: Cron-scheduled synchronization from library to Syncthing folder
- **Per-User Tracking**: Multiple users with independent sync progress
- **Library Agnostic**: Works with any local photo library organized by user folders, not just Immich
- **Quota Management**: Configurable size limits prevent overwhelming backup device storage
- **Low Maintenance**: Requires only periodic cleanup on the backup device after initial setup

## How It Works

```
Local library  ──hard-link──▶  Syncthing folder  ──sync──▶  Backup Pixel  ──upload──▶  Google Photos
```

1. Tool runs on configured cron schedule and checks Syncthing folder size
2. If folder size exceeds lower limit, run is skipped (allows Syncthing to catch up)
3. When space is available, new assets are hard-linked from the library, oldest first
4. Progress is tracked with nanosecond precision and persisted across runs
5. Syncthing syncs to Pixel → uploads to Google Photos → manual cleanup frees space for next batch

> **Important:** Hard links require that the local library and Syncthing folder reside on the same filesystem. This approach uses no additional disk space.

## Prerequisites

- A local library with separate user folders (e.g., `/library/alice/`, `/library/bob/`)
- [Syncthing](https://syncthing.net/) (included in the Docker Compose setup)
- Docker + Docker Compose **or** Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- A Google Pixel device with unlimited photo storage capability

## Installation

### Option A — Docker Compose (Recommended)

Includes both the backup tool and Syncthing.

**1. Clone the repository**

```bash
git clone https://github.com/ldkv/pixel-backup.git
cd pixel-backup
```

**2. Copy the example configs**

```bash
cp -r configs_example configs
```

**3. Edit configuration files** (`configs/settings.json` and `configs/users.json` — see Configuration section)

**4. Update volume paths in `docker-compose.yml`**

Default configuration assumes library at `/immich`:

```yaml
volumes:
  - /immich:/immich # adjust if your setup is special
  - ./configs:/app/configs
```

**5. Launch it**

```bash
docker compose up -d --build
```

Syncthing UI: `http://localhost:8384`

---

### Option B — Local Python Installation

**1. Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and install**

```bash
git clone https://github.com/ldkv/pixel-backup.git
cd pixel-backup
uv sync
```

**3. Copy configs**

```bash
cp -r configs_example configs
```

**4. Edit configuration files** (see Configuration section)

**5. Run it**

```bash
uv run pixel-backup
```

## Syncthing Setup Guide

### Server Setup

1. Go to Syncthing UI (default `http://localhost:8384`) and complete initial setup
2. Create a `syncthing` folder on the same filesystem as your library. Example: if your library is at `/immich/docker_data/library`, create `/immich/syncthing`
3. In Syncthing, add a folder pointing to your `syncthing` directory where hard links will be created

### Pixel Device Setup

1. Create a sync folder on the Pixel (e.g., `Pictures`). **Important:** For multi-user setups, avoid the `DCIM` directory to prevent conflicts with Google Photos
2. Install Syncthing from the Play Store
3. Connect to your server's Syncthing instance using the in-app pairing instructions
4. Share the server's `syncthing` folder to the Pixel at your chosen location (e.g., `Pictures`). The tool automatically manages per-user subfolders
5. Start syncing. Subfolders for each user (e.g., `Pictures/alice`, `Pictures/bob`) will be created automatically
6. Configure Google Photos backup:
   - Sign in with each user's Google account
   - Navigate to Settings → Back up & sync → Back up device folders
   - Enable backup for the corresponding user folder
7. After all users' photos upload to Google Photos, delete photos from the Pixel to free space for the next sync cycle

## Configuration

Configuration is managed through two JSON files in the `configs/` directory.

### `configs/settings.json`

Controls sync behavior, paths, quotas, and scheduling.

```json
{
  "syncthing_dir": "/immich/syncthing",
  "upper_limit_gb": 20.0,
  "lower_limit_gb": 5.0,
  "cron_schedule": "0 0 * * *",
  "timezone": "UTC",
  "min_sleep_seconds": 60
}
```

| Field               | Description                                                                           |
| ------------------- | ------------------------------------------------------------------------------------- |
| `syncthing_dir`     | Directory where hard links are created for Syncthing to sync.                         |
| `upper_limit_gb`    | Maximum Syncthing folder size in GB. Tool stops adding files when reached.            |
| `lower_limit_gb`    | Threshold in GB. If folder exceeds this size, skip run to allow Syncthing to sync.    |
| `cron_schedule`     | Standard cron syntax for scheduling runs. Default `0 0 * * *` runs daily at midnight. |
| `timezone`          | IANA timezone name for interpreting cron schedule (e.g., `America/New_York`).         |
| `min_sleep_seconds` | Minimum seconds between runs, regardless of cron interval. Prevents excessive runs.   |

**Note:** If this file is missing, the tool will auto-generate it with the default values shown above.

#### Cron Schedule Examples

| Expression    | When it runs           |
| ------------- | ---------------------- |
| `0 0 * * *`   | Daily at midnight      |
| `0 */6 * * *` | Every 6 hours          |
| `30 3 * * *`  | Daily at 03:30         |
| `0 3 * * 1`   | Mondays at 03:00       |
| `* * * * *`   | Every minute (testing) |

---

### `configs/users.json`

Defines which Immich users to sync and tracks progress.

```json
{
  "users": [
    {
      "username": "<USERNAME>",
      "asset_created_after": "1970-01-01T00:00:00"
    }
  ]
}
```

| Field                 | Description                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------- |
| `username`            | **Required.** Must match folder name in library directory.                                          |
| `asset_created_after` | Only sync assets created after this timestamp (ISO 8601). Use `1970-01-01T00:00:00` for all assets. |
| `last_timestamp_ns`   | **Auto-managed.** Nanosecond timestamp of last synced file. Modify only to force resync.            |

**Multiple Users:** The tool supports multiple users, with the available quota distributed equally among them:

```json
{
  "users": [
    { "username": "alice", "asset_created_after": "2024-01-01T00:00:00" },
    { "username": "bob", "asset_created_after": "2024-06-01T00:00:00" }
  ]
}
```

> **Note:** This file is required. The tool will exit with an error if `users.json` is not found.

---

## Usage

Once configured and running, the tool operates automatically:

- Waits until the next scheduled cron time
- Syncs new assets according to quota and user configuration
- Saves progress to `configs/users.json`
- Returns to sleep until the next scheduled run

Logs look like this:

```
[2026-02-24 00:00:00] INFO: Next sync at 2026-02-25 00:00:00. Sleeping for 1440 minutes...
[2026-02-25 00:00:00] INFO: Syncing user alice...
[2026-02-25 00:00:01] INFO: Synced 42 files (1.3 GB) for alice.
```

### Forcing a Resync

To resync from a specific date, edit `configs/users.json`:

1. Update `asset_created_after` to your desired start date
2. Remove the `last_timestamp_ns` field if present
3. Restart the service

```json
{
  "username": "alice",
  "asset_created_after": "2023-01-01T00:00:00"
}
```

### Stopping the Service

```bash
docker compose down  # Docker
# or Ctrl+C          # Python
```

---

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [Task](https://taskfile.dev/) for task automation.

```bash
uv sync           # Install all dependencies
uv run pytest     # Run tests
task code-quality # Run format, lint, and type checks
task check-all    # Run all checks and tests
```

Available tasks (run `task --list` for complete list):

| Command        | Description                        |
| -------------- | ---------------------------------- |
| `dev-install`  | Install dependencies and dev tools |
| `format`       | Auto-format code with ruff         |
| `lint-fix`     | Fix linting issues                 |
| `type-check`   | Run static type checker (ty)       |
| `code-quality` | Run all code quality checks        |
| `test`         | Run pytest suite                   |
| `check-all`    | Run all checks and tests           |
| `up` / `down`  | Start/stop Docker Compose          |

---

## License

MIT

## TODO

- Optimize file scanning with concurrent processing
