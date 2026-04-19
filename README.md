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
- **Per-User Tracking**: Multiple users with independent sync progress and source directories
- **Library Agnostic**: Works with any local photo library organized by user folders, not just Immich
- **Quota Management**: Configurable size limit prevents overwhelming backup device storage
- **Discord Notifications**: Optional webhook alerts on sync completion or when upper limit is reached
- **Low Maintenance**: Requires only periodic cleanup on the backup device after initial setup

## How It Works

```
Local library  ──hard-link──▶  Syncthing folder  ──sync──▶  Backup Pixel  ──upload──▶  Google Photos
```

1. Tool runs on configured cron schedule and measures free space under `upper_limit_gb`
2. New assets are hard-linked from each user's `source_dir`, oldest first, until the upper limit is reached
3. Progress is tracked per-user with nanosecond precision and persisted across runs
4. Syncthing syncs to Pixel → uploads to Google Photos → manual cleanup frees space for next batch
5. Optional Discord webhook notifies on sync completion or when the upper limit is hit

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

**3. Edit configuration** (`configs/users.json` and `.env` — see Configuration section)

**4. Set `DATA_ROOT` and `SYNCTHING_DIR` in `.env`**

`DATA_ROOT` is the single host directory that gets bind-mounted into the container at the exact same path. It **must be a common parent** of:

- every user's `source_dir` (the media libraries you want to back up), **and**
- `SYNCTHING_DIR` (where hard links are staged for Syncthing).

Both conditions are required because hard links only work when source and destination are on the same filesystem, and because the container sees these paths verbatim (no path translation).

Example layout:

```
/mnt/media/                        <- DATA_ROOT
├── library/
│   ├── alice/                     <- user source_dir
│   └── bob/                       <- user source_dir
└── syncthing/                     <- SYNCTHING_DIR
```

Matching `.env`:

```bash
DATA_ROOT=/mnt/media
SYNCTHING_DIR=/mnt/media/syncthing
```

And `users.json`:

```json
{ "username": "alice", "source_dir": "/mnt/media/library/alice", ... }
```

Defaults (`DATA_ROOT=/immich`, `SYNCTHING_DIR=/immich/syncthing`) work if your library already lives under `/immich`.

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

Sync behavior is configured via environment variables (see [Environment Variables](#environment-variables)). Per-user state is stored in a JSON file whose path is set by `USER_CONFIGS` (default `./configs/users.json`).

#### Cron Schedule Examples

| Expression    | When it runs           |
| ------------- | ---------------------- |
| `0 0 * * *`   | Daily at midnight      |
| `0 */6 * * *` | Every 6 hours          |
| `30 3 * * *`  | Daily at 03:30         |
| `0 3 * * 1`   | Mondays at 03:00       |
| `* * * * *`   | Every minute (testing) |

---

### User Configurations: `users.json`

Defines which users to sync and tracks progress.

```json
{
  "users": [
    {
      "username": "<USERNAME>",
      "source_dir": "/path/to/source/directory",
      "asset_created_after": "1970-01-01T00:00:00"
    }
  ]
}
```

| Field                 | Description                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------- |
| `username`            | **Required.** Used as the per-user subfolder name under `syncthing_dir`.                                    |
| `source_dir`          | **Required.** Absolute path to this user's library directory. Must share a filesystem with `syncthing_dir`. |
| `asset_created_after` | Only sync assets created after this timestamp (ISO 8601). Use `1970-01-01T00:00:00` for all assets.         |
| `last_timestamp_ns`   | **Auto-managed.** Nanosecond timestamp of last synced file. Modify only to force resync.                    |

**Multiple Users:** Users are processed sequentially. Each user consumes the remaining quota under `upper_limit_gb` until exhausted; later users are skipped with a Discord alert (if configured).

```json
{
  "users": [
    { "username": "alice", "source_dir": "/immich/library/alice", "asset_created_after": "2024-01-01T00:00:00" },
    { "username": "bob", "source_dir": "/immich/library/bob", "asset_created_after": "2024-06-01T00:00:00" }
  ]
}
```

> **Note:** This file is required. The tool will exit with an error if `users.json` is not found.

---

### Environment Variables

All sync behavior (paths, quota, schedule, notifications) is configured via environment variables. Values can be exported in the shell, injected by Docker Compose, or placed in a `.env` file at the project root (copy `.env.example` to get started). All variables are optional and fall back to the defaults below.

| Variable              | Default                | Description                                                                                                                                                                                               |
| --------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USER_CONFIGS`        | `./configs/users.json` | Path to the `users.json` config file. Ignored inside Docker (always `/app/configs/users.json`).                                                                                                           |
| `DATA_ROOT`           | `/data`                | Host directory bind-mounted into the container at the same path. **Must be a common parent** of every user's `source_dir` and of `SYNCTHING_DIR` — hard links require one shared filesystem. Docker-only. |
| `SYNCTHING_DIR`       | `/data/syncthing`      | Directory where hard links are created for Syncthing to sync. Must live under `DATA_ROOT`.                                                                                                                |
| `UPPER_LIMIT_GB`      | `20.0`                 | Maximum Syncthing folder size in GB. Tool stops adding files when reached.                                                                                                                                |
| `CRON_SCHEDULE`       | `0 0 * * *`            | Standard cron syntax for scheduling runs. Default runs daily at midnight.                                                                                                                                 |
| `TIMEZONE`            | `UTC`                  | IANA timezone name for interpreting cron schedule (e.g., `America/New_York`).                                                                                                                             |
| `MIN_SLEEP_SECONDS`   | `60`                   | Minimum seconds between runs, regardless of cron interval.                                                                                                                                                |
| `DISCORD_WEBHOOK_URL` | _(empty)_              | Discord webhook URL for sync notifications. When unset, notifications are skipped.                                                                                                                        |

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
[2026-02-25 00:00:00] INFO: Syncing user alice with quota of 18432.00MB...
[2026-02-25 00:00:01] INFO: Added 42 files (1331.20MB) for user alice.
[2026-02-25 00:00:01] INFO: Sync complete: 42 files, 1331.20MB in 1.2s.
```

### Discord Notifications (optional)

Set the `DISCORD_WEBHOOK_URL` environment variable to receive alerts when:

- A sync run completes (summary of files and size)
- The `upper_limit_gb` is reached before all users finish (prompt to free space on the Pixel)

Notifications are skipped in dry-run mode and when the variable is unset.

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
