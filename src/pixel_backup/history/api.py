import asyncio
import contextlib

from django.core.management import call_command
from django_bolt import BoltAPI

from pixel_backup.daemon import run_daemon
from pixel_backup.history.models import Batch, SyncedFile


@contextlib.asynccontextmanager
async def lifespan(_api: BoltAPI):
    await asyncio.to_thread(call_command, "migrate", verbosity=0)
    daemon_task = asyncio.create_task(run_daemon())
    try:
        yield
    finally:
        daemon_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await daemon_task


api = BoltAPI(lifespan=lifespan)


@api.get("/status")
async def status() -> dict:
    return {
        "total_files": await SyncedFile.objects.acount(),
        "total_batches": await Batch.objects.acount(),
    }


@api.get("/history/{username}")
async def history(username: str) -> list[dict]:
    return [
        {
            "id": batch.id,
            "synced_at": batch.synced_at.isoformat(),
            "files_count": batch.files_count,
            "total_bytes": batch.total_bytes,
        }
        async for batch in Batch.objects.filter(username=username).order_by("-synced_at")
    ]
