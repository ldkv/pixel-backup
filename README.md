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

1. Tool runs on configured cron schedule and measures free space under `phone_limit_gb`
2. New assets are hard-linked from each user's `source_dir`, oldest first, until the upper limit is reached
3. Progress is tracked per-user with nanosecond precision and persisted in the database across runs
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

**2. Edit configuration** (`.env` — see [Configuration](#configuration) section)

**3. Set `DATA_ROOT`, `SYNCTHING_DIR`, and `LOCAL_DATA_DIR` in `.env`**

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

`LOCAL_DATA_DIR` is a separate host directory (required, no default) where the SQLite database persists — it's bind-mounted to the fixed `/data` path inside the container, independent of `DATA_ROOT`.

Matching `.env`:

```bash
DATA_ROOT=/mnt/media
SYNCTHING_DIR=/mnt/media/syncthing
LOCAL_DATA_DIR=./docker_data
```

**4. Launch it**

```bash
docker compose up -d --build
```

Syncthing UI: `http://localhost:8384`

**5. Add UserConfigs**

User Configs (and their sync progress) live in the database, managed through the Django admin. On first run, the tool automatically creates an `admin` superuser using the `ADMIN_PASSWORD` env var (default `admin`; the generated credentials are also logged on first startup). Log in and add each user under **History › User configs**:

Admin UI: `http://localhost:8000/admin/` (see [Configuration](#configuration) section for the `UserConfig` fields)

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

**3. Edit configuration** (`.env` — see [Configuration](#configuration) section)

**4. Run it**

```bash
uv run manage.py runbolt --processes 1
```

Or with Taskfile:

```bash
task run
```

This applies migrations, starts the sync daemon, and serves the API/admin. On first run, it automatically creates an `admin` superuser using `ADMIN_PASSWORD` (default `admin`; logged on first startup). Log in and add users through the Django admin (see [Configuration](#configuration) section):

Admin UI: `http://localhost:8000/admin/`

## Syncthing Setup Guide

### Server Setup

1. Go to Syncthing UI (default `http://localhost:8384`) and complete initial setup
2. Create a `syncthing` folder on the same filesystem as your library. Example: if your library is at `/mnt/media/library`, create `/mnt/media/syncthing`
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

Sync behavior is configured via environment variables (see [Environment Variables](#environment-variables)). Users and their sync progress live in the database, managed through the Django admin (see [User Configuration](#user-configuration-django-admin)).

#### Cron Schedule Examples

| Expression    | When it runs           |
| ------------- | ---------------------- |
| `0 0 * * *`   | Daily at midnight      |
| `0 */6 * * *` | Every 6 hours          |
| `30 3 * * *`  | Daily at 03:30         |
| `0 3 * * 1`   | Mondays at 03:00       |
| `* * * * *`   | Every minute (testing) |

---

### User Configuration: Django Admin

Users to sync (and their progress) are stored in the database as `UserConfig` records, managed through the Django admin at `/admin/`. Log in with the superuser account created during installation and add entries under **History › User configs**.

| Field               | Description                                                                                                    |
| ------------------- | -------------------------------------------------------------------------------------------------------------- |
| `username`          | **Required.** Used as the per-user subfolder name under `syncthing_dir`.                                       |
| `source_dir`        | **Required.** Absolute path to this user's library directory. Must share a filesystem with `syncthing_dir`.    |
| `sync_order`        | **Required.** Determines the order users are processed in during a sync run.                                   |
| `sync_cutoff_at`    | Only sync assets created on or after this date/time. Defaults to the earliest possible date (sync everything). |
| `last_timestamp_ns` | **Auto-managed.** Nanosecond timestamp of the last synced asset. Lower (or reset) it to force a resync.        |

**Multiple Users:** Users are processed in `sync_order`. Each user consumes the remaining quota under `phone_limit_gb` until exhausted; later users are skipped, with a Discord alert if configured.

Each sync run and every asset it links are also recorded (**History › Batches** / **History › Synced assets**) for auditing and to avoid re-linking recently synced files.

---

### Environment Variables

All sync behavior (paths, quota, schedule, notifications) is configured via environment variables. Values can be exported in the shell, injected by Docker Compose, or placed in a `.env` file at the project root (copy `.env.example` to get started). All variables are optional and fall back to the defaults below.

| Variable              | Default                | Description                                                                                                                                                                                                                       |
| --------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `API_PORT`            | `8000`                 | Host port mapped to the API/admin server. Docker Compose only.                                                                                                                                                                    |
| `DATA_ROOT`           | _(required)_           | Host directory bind-mounted into the container at the same path. **Must be a common parent** of every user's `source_dir` and of `SYNCTHING_DIR` — hard links require one shared filesystem. Docker-only, no fallback if unset.   |
| `SYNCTHING_DIR`       | `/mnt/media/syncthing` | Directory where hard links are created for Syncthing to sync. Must live under `DATA_ROOT`.                                                                                                                                        |
| `LOCAL_DATA_DIR`      | _(required)_           | Host directory bind-mounted to `/data` in the container, where the SQLite database persists. Docker-only, no fallback if unset — the container's `DATA_DIR` is fixed to `/data` to match this mount and isn't affected by `.env`. |
| `ADMIN_PASSWORD`      | `admin`                | Password for the auto-created `admin` superuser (created on first startup if it doesn't already exist).                                                                                                                           |
| `PHONE_LIMIT_GB`      | `19.0`                 | Maximum Syncthing folder size in GB. Tool stops adding files when reached.                                                                                                                                                        |
| `CRON_SCHEDULE`       | `0 0 * * *`            | Standard cron syntax for scheduling runs. Default runs daily at midnight.                                                                                                                                                         |
| `TIMEZONE`            | `UTC`                  | IANA timezone name for interpreting cron schedule (e.g., `America/New_York`).                                                                                                                                                     |
| `MIN_SLEEP_SECONDS`   | `60`                   | Minimum seconds between runs, regardless of cron interval.                                                                                                                                                                        |
| `DISCORD_WEBHOOK_URL` | _(empty)_              | Discord webhook URL for sync notifications. When unset, notifications are skipped.                                                                                                                                                |

---

## Usage

Once configured and running, the tool operates automatically:

- Waits until the next scheduled cron time
- Syncs new assets according to quota and user configuration
- Saves progress to the database (`last_timestamp_ns` per user)
- Returns to sleep until the next scheduled run

Logs look like this:

```
[2026-02-24 00:00:00] INFO: Next sync at 2026-02-25 00:00:00. Sleeping for 86400 seconds...
[2026-02-25 00:00:00] INFO: Syncing user alice with quota of 18432.00MB...
[2026-02-25 00:00:01] INFO: Synced 42 new assets (1331.20MB) for user.username='alice'.
[2026-02-25 00:00:01] INFO: Sync complete: 42 files, 1331.20MB in 1.2s.
```

### Discord Notifications (optional)

Set the `DISCORD_WEBHOOK_URL` environment variable to receive alerts when:

- A sync run completes (summary of files and size)
- The `phone_limit_gb` is reached before all users finish (prompt to free space on the Pixel)
- An asset is larger than a user's remaining quota and gets skipped

Notifications are skipped in dry-run mode and when the variable is unset.

### Forcing a Resync

To resync from a specific date, edit the user's `UserConfig` in the Django admin (`/admin/`):

1. Update `sync_cutoff_at` to your desired start date
2. Reset `last_timestamp_ns` to `0` if it's later than the new cutoff
3. Save — the next scheduled run picks up the change automatically

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

| Command        | Description                                  |
| -------------- | -------------------------------------------- |
| `dev-install`  | Install dependencies and dev tools           |
| `format`       | Auto-format code with ruff                   |
| `lint-fix`     | Fix linting issues                           |
| `type-check`   | Run static type checker (ty)                 |
| `code-quality` | Run all code quality checks                  |
| `test`         | Run pytest suite                             |
| `check-all`    | Run all checks and tests                     |
| `migrations`   | Generate Django migrations                   |
| `migrate`      | Apply Django migrations                      |
| `sync`         | Run a single sync (`dry_run=true` supported) |
| `run`          | Launch the service (API + sync daemon)       |
| `up` / `down`  | Start/stop Docker Compose                    |

---

## License

MIT

## TODO

- Optimize file scanning with concurrent processing
