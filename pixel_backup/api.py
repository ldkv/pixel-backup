import asyncio
import contextlib
import logging
from typing import Any, AsyncGenerator

from django.contrib.auth.models import User
from django.core.management import call_command
from django_bolt import BoltAPI

from history.models import Batch, SyncedAsset
from pixel_backup.core.daemon import ENV_VARS, run_daemon

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_api: BoltAPI) -> AsyncGenerator[None, Any]:
    await asyncio.to_thread(call_command, "migrate", verbosity=0)
    await _create_super_user()
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
        "total_assets": await SyncedAsset.objects.acount(),
        "total_batches": await Batch.objects.acount(),
    }


@api.get("/history/{username}")
async def history(username: str) -> list[dict]:
    return [
        {
            "id": batch.id,
            "synced_at": batch.synced_at,
            "files_count": batch.files_count,
            "total_bytes": batch.total_bytes,
        }
        async for batch in Batch.objects.filter(user_config__username=username).order_by("-synced_at")
    ]


async def _create_super_user(username: str = "admin") -> None:
    user, created = await User.objects.aget_or_create(
        username=username,
        defaults={
            "is_superuser": True,
            "is_staff": True,
        },
    )
    if created:
        password = ENV_VARS.admin_password.get_secret_value()
        user.set_password(password)
        await user.asave()
        logger.info(f"Generated super user: {username=} / {password=}")
