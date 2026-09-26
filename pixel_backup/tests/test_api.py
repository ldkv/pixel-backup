from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from django_bolt.testing import TestClient

from history.models import Batch, UserConfig
from pixel_backup.api import api
from pixel_backup.env import NANOSECONDS

pytestmark = pytest.mark.django_db(transaction=True)

CUTOFF = datetime(2024, 1, 1, tzinfo=UTC)
CUTOFF_NS = int(CUTOFF.timestamp() * NANOSECONDS)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(api) as client:
        yield client


class TestCreateUserConfig:
    def test_stores_cutoff(self, client: TestClient) -> None:
        response = client.post(
            "/user_configs",
            json={"username": "user", "source_dir": "/x", "sync_order": 0, "sync_cutoff_at": CUTOFF.isoformat()},
        )

        assert response.status_code == 200
        assert UserConfig.objects.get().sync_cutoff_ns == CUTOFF_NS

    def test_defaults_cutoff_to_zero(self, client: TestClient) -> None:
        response = client.post("/user_configs", json={"username": "user", "source_dir": "/x", "sync_order": 0})

        assert response.status_code == 200
        assert UserConfig.objects.get().sync_cutoff_ns == 0


class TestUpdateUserConfig:
    def test_keeps_cutoff_when_not_sent(self, client: TestClient) -> None:
        user = UserConfig.objects.create(
            username="user",
            source_dir="/x",
            sync_order=0,
            sync_cutoff_ns=12345,
        )

        response = client.put(
            f"/user_configs/{user.id}",
            json={
                "username": "renamed",
                "source_dir": "/y",
                "sync_order": 1,
            },
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert (user.username, user.source_dir, user.sync_order, user.sync_cutoff_ns) == ("renamed", "/y", 1, 12345)

    def test_ignores_cutoff_when_sent(self, client: TestClient) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0, sync_cutoff_ns=12345)

        response = client.put(
            f"/user_configs/{user.id}",
            json={"username": "user", "source_dir": "/x", "sync_order": 0, "sync_cutoff_at": CUTOFF.isoformat()},
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.sync_cutoff_ns == 12345


class TestResyncBatch:
    def test_starts_resync(self, client: TestClient) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0)
        batch = Batch.objects.create(user_config=user)

        with patch("pixel_backup.api.trigger_manual_resync", AsyncMock(return_value=True)) as mock_trigger:
            response = client.post(f"/batches/{batch.id}/resync?dry_run=true")

        assert response.status_code == 200
        mock_trigger.assert_awaited_once_with(batch.id, dry_run=True)

    def test_unknown_batch(self, client: TestClient) -> None:
        response = client.post("/batches/999/resync")

        assert response.status_code == 404

    def test_conflict_when_sync_running(self, client: TestClient) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0)
        batch = Batch.objects.create(user_config=user)

        with patch("pixel_backup.api.trigger_manual_resync", AsyncMock(return_value=False)):
            response = client.post(f"/batches/{batch.id}/resync")

        assert response.status_code == 409
