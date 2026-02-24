# google-photos-pixel-backup

Automatically create a portion of new photos from a given directory based on user defined quota to a separate folder for syncing to Google Photos through a Google Pixel phone.

## Why do I need this?

This service serves my niche use case where I use Immich as my main photo management solution but also
want to back up my Immich assets to Google Photos through a Google Pixel phone with unlimited storage, such as Google Pixel 1 (original quality) up to Pixel 5 (compressed quality).

To achieve this, I would need to sync photos from my main phone to Immich, then manually copy them to the Pixel's local storage, which is tedious and error-prone. Another common solution is to setup Syncthing both on the main phone and on the old Pixel, which also has its own issues:

- I have to install a permanent background service on my main phone, which is undesirable for battery and privacy reasons.
- My main phone will have to sync all photos twice, once to Immich and once to the Pixel, which is inefficient and drains more battery.
- The old Pixel has very limited storage, so I can only sync a portion of the photos, which requires manual management to avoid running out of space.
- If I want to sync for multiple users with multiple phones, the process becomes even more complicated and unmanageable.

Since all photos already exist in the Immich library, I have the idea of syncing directly from its local disk as a source of truth, with only one instance of Syncthing running permanently on the server. The only missing piece is a tool that can automatically manage the syncing process, and thus `immich-backup` was born.

## Features

This tool provides the following features:

- **Automated Syncing**: Runs on a cron schedule to automatically sync new assets from the Immich library to a Syncthing-watched folder.
- **Per-User Syncing**: Supports multiple Immich users with independent sync progress tracking
- **Quota Management**: Maintains the Syncthing folder size within user-defined upper and lower limits to prevent overfilling the Pixel's storage.
- Minimal manual intervention after setup: the only manual step is to free-up space on the backup Pixel once the photos are synced to Google Photos Cloud. The tool handles the rest of the process automatically.

## How It Works

```
Immich library  ──hard-link──▶  Syncthing folder  ──sync──▶  Phone / Cloud
(/immich/docker_data/library)   (/immich/syncthing)           (Google Photos, etc.)
```

1. On each scheduled run, the tool checks the current size of the Syncthing folder.
2. If it is already above `lower_limit_gb`, it skips the run and waits — Syncthing is still catching up.
3. Otherwise, it calculates available quota (`upper_limit_gb − current size`) and hard-links new assets from all specified users (directories) into the Syncthing folder, oldest files first, until the quota is consumed.
4. Per-user progress is tracked with nanosecond-precision timestamps and persisted in `users.json` so syncs resume exactly where they left off.
5. Once the photos are synced to the Pixel and then to Google Photos, users can free up space on the Pixel for the next batch. The Syncthing folder will be automatically cleared as a result, and the tool will add more files on the next run.

> **Important:** Hard links require that the Immich library and the Syncthing folder reside on the **same filesystem**. No extra disk space is used by the links.

## Prerequisites

- A local library on disk, which separate folders for each user, e.g. `/library/alice/`, `/library/bob/`, etc.
- [Syncthing](https://syncthing.net/) (or the Docker Compose setup below).
- Docker + Docker Compose **or** Python 3.14+ with [uv](https://docs.astral.sh/uv/).

## Installation

### Option A — Docker Compose (recommended)

This is the easiest path. The compose file starts both `immich-backup` and Syncthing together.

**1. Clone the repository**

```bash
git clone https://github.com/<you>/immich-backup.git
cd immich-backup
```

**2. Create the config directory from the examples**

```bash
cp -r configs_example configs
```

**3. Edit the configuration files** (see [Configuration](#configuration) below).

**4. Adjust volume paths in `docker-compose.yml`**

The default mounts assume your Immich data lives at `/immich` on the host:

```yaml
volumes:
  - /immich:/immich # parent of both library and Syncthing dirs
  - ./configs:/app/configs # config files
```

Change `/immich` to wherever your Immich data is stored.

**5. Start the services**

```bash
docker compose up -d --build
```

The Syncthing web UI is available at `http://localhost:8384`.

---

### Option B — Local Python (uv)

**1. Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and install**

```bash
git clone https://github.com/<you>/immich-backup.git
cd immich-backup
uv sync
```

**3. Create the config directory from the examples**

```bash
cp -r configs_example configs
```

**4. Edit the configuration files** (see [Configuration](#configuration) below).

**5. Run**

```bash
uv run immich-backup
```

## Configuration

All configuration lives in two JSON files inside the `configs/` directory.

### `configs/settings.json`

Controls global behaviour — paths, disk quotas, and the sync schedule.

```json
{
  "immich_library_dir": "/immich/docker_data/library",
  "syncthing_dir": "/immich/syncthing",
  "upper_limit_gb": 20.0,
  "lower_limit_gb": 5.0,
  "cron_schedule": "0 0 * * *",
  "timezone": "UTC",
  "min_sleep_seconds": 60
}
```

| Field                | Type   | Default                       | Description                                                                                                         |
| -------------------- | ------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `immich_library_dir` | path   | `/immich/docker_data/library` | Root of the Immich local library. Must be on the same filesystem as `syncthing_dir`.                                |
| `syncthing_dir`      | path   | `/immich/syncthing`           | Directory watched by Syncthing. Files are hard-linked here.                                                         |
| `upper_limit_gb`     | float  | `20.0`                        | Maximum total size (GB) to maintain in the Syncthing folder. The tool will not add more files once this is reached. |
| `lower_limit_gb`     | float  | `5.0`                         | If the Syncthing folder is already this large or larger, skip the sync run and wait for Syncthing to clear space.   |
| `cron_schedule`      | string | `0 0 * * *`                   | Standard 5-field cron expression controlling when syncs run.                                                        |
| `timezone`           | string | `UTC`                         | IANA timezone name used to interpret `cron_schedule` (e.g. `Europe/Paris`, `America/New_York`).                     |
| `min_sleep_seconds`  | int    | `60`                          | Minimum number of seconds to wait between runs, regardless of the cron interval.                                    |

**If `settings.json` is missing**, the tool auto-generates it with the defaults above.

#### Cron schedule examples

| `cron_schedule` | Meaning                    |
| --------------- | -------------------------- |
| `0 0 * * *`     | Every day at midnight      |
| `0 */6 * * *`   | Every 6 hours              |
| `30 3 * * *`    | Every day at 03:30         |
| `0 3 * * 1`     | Every Monday at 03:00      |
| `* * * * *`     | Every minute (for testing) |

---

### `configs/users.json`

Lists the Immich users whose assets should be backed up, and tracks sync progress.

```json
{
  "users": [
    {
      "username": "<IMMICH_USERNAME>",
      "asset_created_after": "1970-01-01T00:00:00"
    }
  ]
}
```

| Field                 | Type     | Description                                                                                                                                                                                                                           |
| --------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `username`            | string   | **Required.** The Immich username. This must match the directory name under `immich_library_dir` (i.e. `<immich_library_dir>/<username>/` must exist).                                                                                |
| `asset_created_after` | datetime | Only sync assets created **after** this timestamp. Accepts ISO 8601 format (`YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`, or with timezone offset). All times are stored as UTC internally. Set to `"1970-01-01T00:00:00"` to sync everything. |
| `last_timestamp_ns`   | int      | **Auto-managed.** Nanosecond timestamp of the last successfully synced file. Updated automatically after each run. Do not edit unless you want to force a resync.                                                                     |

**Multiple users** are supported. The available quota is distributed equally among them each run:

```json
{
  "users": [
    {
      "username": "alice",
      "asset_created_after": "2024-01-01T00:00:00"
    },
    {
      "username": "bob",
      "asset_created_after": "2024-06-01T00:00:00"
    }
  ]
}
```

> **`users.json` is required.** The tool will exit with an error on startup if this file is missing.

---

## Usage

Once running, the tool operates fully automatically:

- It sleeps until the next scheduled time, then wakes up and syncs new assets.
- Progress is saved to `configs/users.json` after each run.
- Logs are written to stdout with timestamps:

```
[2026-02-24 00:00:00] INFO: Next sync at 2026-02-25 00:00:00. Sleeping for 1440 minutes...
[2026-02-25 00:00:00] INFO: Syncing user alice...
[2026-02-25 00:00:01] INFO: Synced 42 files (1.3 GB) for alice.
```

### Forcing a resync

To resync assets for a user from a specific date, edit `asset_created_after` in `configs/users.json` and remove or reset `last_timestamp_ns`:

```json
{
  "username": "alice",
  "asset_created_after": "2023-01-01T00:00:00"
}
```

Then restart the service.

### Stopping

```bash
# Docker Compose
docker compose down

# uv
# Ctrl+C in the terminal running immich-backup
```

---

## Development

The project uses [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/).

```bash
# Install all dependencies including dev tools
uv sync

# Run tests
uv run pytest

# Code quality (format + lint + type-check)
task code-quality

# Run all checks and tests
task check-all
```

Available tasks (`task --list`):

| Task           | Description                                  |
| -------------- | -------------------------------------------- |
| `dev-install`  | Install all dependencies including dev tools |
| `format`       | Auto-format code with ruff                   |
| `lint-fix`     | Fix linting issues with ruff                 |
| `type-check`   | Run static type checker (ty)                 |
| `code-quality` | Run format + lint + type checks              |
| `test`         | Run pytest suite                             |
| `check-all`    | Run all checks and tests                     |
| `up`           | Start Docker Compose                         |
| `down`         | Stop Docker Compose                          |

## License

MIT
