import pytest
from django.test import Client

from history.models import UserConfig

pytestmark = pytest.mark.django_db


class TestUserConfigAdmin:
    def test_cutoff_can_be_set_on_creation(self, admin_client: Client) -> None:
        admin_client.post(
            "/admin/history/userconfig/add/",
            {"username": "user", "source_dir": "/x", "sync_order": 0, "sync_cutoff_ns": 12345},
        )

        assert UserConfig.objects.get().sync_cutoff_ns == 12345

    def test_cutoff_cannot_be_changed(self, admin_client: Client) -> None:
        user = UserConfig.objects.create(username="user", source_dir="/x", sync_order=0, sync_cutoff_ns=12345)

        admin_client.post(
            f"/admin/history/userconfig/{user.id}/change/",
            {"username": "renamed", "source_dir": "/x", "sync_order": 0, "sync_cutoff_ns": 99999},
        )

        user.refresh_from_db()
        assert (user.username, user.sync_cutoff_ns) == ("renamed", 12345)
