import asyncio
import contextlib
import logging
from typing import Any, AsyncGenerator

from django.contrib.auth.models import User
from django.core.management import call_command
from django_bolt import BoltAPI

from history.models import GlobalConfig
from pixel_backup.core.daemon import run_daemon
from pixel_backup.env import ENV_VARS

logger = logging.getLogger(__name__)


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
