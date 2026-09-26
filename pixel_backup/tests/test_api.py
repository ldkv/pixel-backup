from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from django_bolt.testing import TestClient

from history.models import UserConfig
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

    def test_updates_cutoff_when_sent(self, client: TestClient) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0, sync_cutoff_ns=12345)

        response = client.put(
            f"/user_configs/{user.id}",
            json={"username": "user", "source_dir": "/x", "sync_order": 0, "sync_cutoff_at": CUTOFF.isoformat()},
        )

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.sync_cutoff_ns == CUTOFF_NS
