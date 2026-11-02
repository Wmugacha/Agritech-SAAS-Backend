import pytest
from django.contrib.auth import get_user_model

REGISTER_URL = "/api/accounts/register/"
LOGIN_URL = "/api/auth/login/"
REFRESH_URL = "/api/auth/refresh/"
ME_URL = "/api/accounts/me/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(password):
    return get_user_model().objects.create_user(email="wanjiru@example.com", password=password)


def login(api_client, email, password):
    return api_client.post(LOGIN_URL, {"email": email, "password": password}, format="json")


class TestRegister:
    def test_register_returns_user_and_tokens(self, api_client, password):
        response = api_client.post(
            REGISTER_URL, {"email": "new@example.com", "password": password}, format="json"
        )

        assert response.status_code == 201
        assert response.data["user"]["email"] == "new@example.com"
        assert {"access", "refresh"} <= response.data.keys()
        assert "password" not in response.data["user"]
        # Password is hashed, never stored as plain text
        created = get_user_model().objects.get(email="new@example.com")
        assert created.password != password
        assert created.check_password(password)

    def test_register_rejects_duplicate_email(self, api_client, user, password):
        response = api_client.post(
            REGISTER_URL, {"email": user.email, "password": password}, format="json"
        )

        assert response.status_code == 400
        assert "email" in response.data

    def test_register_rejects_short_password(self, api_client):
        response = api_client.post(
            REGISTER_URL, {"email": "short@example.com", "password": "abc"}, format="json"
        )

        assert response.status_code == 400
        assert "password" in response.data


class TestLogin:
    def test_login_returns_jwt_pair(self, api_client, user, password):
        response = login(api_client, user.email, password)

        assert response.status_code == 200
        assert {"access", "refresh"} <= response.data.keys()

    def test_login_with_wrong_password_is_rejected(self, api_client, user):
        response = login(api_client, user.email, "wrong-password")

        assert response.status_code == 401

    def test_refresh_returns_new_access_token(self, api_client, user, password):
        refresh = login(api_client, user.email, password).data["refresh"]

        response = api_client.post(REFRESH_URL, {"refresh": refresh}, format="json")

        assert response.status_code == 200
        assert "access" in response.data


class TestMe:
    def test_me_requires_auth(self, api_client):
        response = api_client.get(ME_URL)

        assert response.status_code == 401

    def test_me_with_bearer_token_returns_current_user(self, api_client, user, password):
        access = login(api_client, user.email, password).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = api_client.get(ME_URL)

        assert response.status_code == 200
        assert response.data == {"id": str(user.id), "email": user.email}

    def test_me_rejects_garbage_token(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

        response = api_client.get(ME_URL)

        assert response.status_code == 401
