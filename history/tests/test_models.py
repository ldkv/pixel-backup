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


class TestGetSinceNs:
    def test_uses_cutoff_when_no_assets_synced_yet(self) -> None:
        cutoff = datetime(2024, 1, 1, tzinfo=UTC)
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0, sync_cutoff_at=cutoff)

        assert user.active_cutoff_ns == int(cutoff.timestamp() * NANOSECONDS)

    def test_uses_last_timestamp_when_later_than_cutoff(self) -> None:
        cutoff = datetime(2024, 1, 1, tzinfo=UTC)
        user = UserConfig.objects.create(
            username="user",
            source_dir="/x",
            sync_order=0,
            sync_cutoff_at=cutoff,
            last_timestamp_ns=int(datetime(2024, 6, 1, tzinfo=UTC).timestamp() * NANOSECONDS),
        )

        assert user.active_cutoff_ns == user.last_timestamp_ns

    def test_uses_cutoff_when_later_than_last_timestamp(self) -> None:
        cutoff = datetime(2024, 6, 1, tzinfo=UTC)
        user = UserConfig.objects.create(
            username="user",
            source_dir="/x",
            sync_order=0,
            sync_cutoff_at=cutoff,
            last_timestamp_ns=int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * NANOSECONDS),
        )

        assert user.active_cutoff_ns == int(cutoff.timestamp() * NANOSECONDS)


class TestUpdateTimestamp:
    def test_persists_new_timestamp(self) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0)

        user.update_timestamp(12345)

        user.refresh_from_db()
        assert user.last_timestamp_ns == 12345
