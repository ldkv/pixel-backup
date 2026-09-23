import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError
from django_bolt import BoltAPI
from django_bolt.exceptions import BadRequest, Conflict, NotFound
from django_bolt.responses import HTML

from history.models import Batch, GlobalConfig, UserConfig
from pixel_backup.core.daemon import run_daemon, trigger_manual_sync
from pixel_backup.env import ENV_VARS
from pixel_backup.schemas import BatchOut, GlobalConfigSchema, SyncOut, UserConfigIn, UserConfigOut

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@contextlib.asynccontextmanager
async def lifespan(_api: BoltAPI) -> AsyncGenerator[None, Any]:
    await asyncio.to_thread(call_command, "migrate", verbosity=0)
    await oneshot_setup()
    daemon_task = asyncio.create_task(run_daemon())
    try:
        yield
    finally:
        daemon_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await daemon_task


api = BoltAPI(lifespan=lifespan)


@api.get("/")
async def admin_page() -> HTML:
    return HTML(STATIC_DIR.joinpath("admin.html").read_text())


@api.get("/global_config")
async def get_global_config() -> GlobalConfigSchema:
    return GlobalConfigSchema.from_model(await GlobalConfig.load())


@api.put("/global_config")
async def update_global_config(body: GlobalConfigSchema) -> GlobalConfigSchema:
    global_config = await GlobalConfig.load()
    updated_fields = body.dump(exclude_none=True)
    for key, value in updated_fields.items():
        setattr(global_config, key, value)
    await global_config.asave()
    return GlobalConfigSchema.from_model(global_config)


@api.get("/user_configs")
async def list_user_configs() -> list[UserConfigOut]:
    return await UserConfigOut.afrom_models(UserConfig.load())


@api.post("/user_configs")
async def create_user_config(body: UserConfigIn) -> UserConfigOut:
    try:
        user_config = await UserConfig.objects.acreate(
            username=body.username, source_dir=body.source_dir, sync_order=body.sync_order
        )
    except IntegrityError as e:
        raise BadRequest(detail=str(e)) from e
    return UserConfigOut.from_model(user_config)


@api.put("/user_configs/{config_id}")
async def update_user_config(config_id: int, body: UserConfigIn) -> UserConfigOut:
    user_config = await UserConfig.objects.filter(id=config_id).afirst()
    if user_config is None:
        raise NotFound(detail=f"UserConfig {config_id} not found")

    user_config.username = body.username
    user_config.source_dir = body.source_dir
    user_config.sync_order = body.sync_order
    try:
        await user_config.asave(update_fields=["username", "source_dir", "sync_order"])
    except IntegrityError as e:
        raise BadRequest(detail=str(e)) from e
    return UserConfigOut.from_model(user_config)


@api.delete("/user_configs/{config_id}")
async def delete_user_config(config_id: int) -> dict:
    deleted, _ = await UserConfig.objects.filter(id=config_id).adelete()
    if not deleted:
        raise NotFound(detail=f"UserConfig {config_id} not found")
    return {"deleted": deleted}


@api.get("/batches")
async def list_batches(username: str | None = None, limit: int = 100) -> list[BatchOut]:
    batches = Batch.objects.select_related("user_config")
    if username:
        batches = batches.filter(user_config__username=username)
    return await BatchOut.afrom_models(batches.order_by("-synced_at")[:limit])


@api.post("/sync")
async def trigger_sync(dry_run: bool = False) -> SyncOut:
    started = await trigger_manual_sync(dry_run=dry_run)
    if not started:
        raise Conflict(detail="A sync is already running")
    return SyncOut(started=True)


async def oneshot_setup(username: str = "admin") -> None:
    """Oneshot - creates a super user and a default GlobalConfig."""

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

    await GlobalConfig.objects.aget_or_create(id=1)
