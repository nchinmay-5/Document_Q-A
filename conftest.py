"""Shared test fixtures. Test settings live in config/settings_test.py."""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="alice", password="pw-alice-123")


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(username="bob", password="pw-bob-123")


@pytest.fixture
def api_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client
