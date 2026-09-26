from datetime import UTC, datetime

import pytest

from history.models import UserConfig
from pixel_backup.env import NANOSECONDS

pytestmark = pytest.mark.django_db


class TestUserConfigLoad:
    def test_orders_by_sync_order_ascending(self) -> None:
        UserConfig.objects.create(username="charlie", source_dir="/c", sync_order=2)
        UserConfig.objects.create(username="alice", source_dir="/a", sync_order=0)
        UserConfig.objects.create(username="bob", source_dir="/b", sync_order=1)

        loaded = UserConfig.load()

        assert [user.username for user in loaded] == ["alice", "bob", "charlie"]


class TestCutoffAt:
    def test_defaults_to_epoch(self) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0)

        assert user.sync_cutoff_ns == 0
        assert user.sync_cutoff_at == datetime(1970, 1, 1, tzinfo=UTC)

    def test_create_from_datetime(self) -> None:
        cutoff = datetime(2024, 1, 1, tzinfo=UTC)
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0, sync_cutoff_at=cutoff)

        user.refresh_from_db()
        assert user.sync_cutoff_ns == int(cutoff.timestamp() * NANOSECONDS)
        assert user.sync_cutoff_at == cutoff

    def test_clamps_pre_epoch_datetime_to_zero(self) -> None:
        user = UserConfig(username="user", source_dir="/x", sync_order=0)

        user.sync_cutoff_at = datetime(1900, 1, 1, tzinfo=UTC)

        assert user.sync_cutoff_ns == 0


class TestUpdateTimestamp:
    def test_persists_new_timestamp(self) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0)

        user.update_timestamp(12345)

        user.refresh_from_db()
        assert user.sync_cutoff_ns == 12345
