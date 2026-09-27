import httpx
import pytest

from tests.helpers import STRONG_PASSWORD

Headers = dict[str, str]


async def sign_up(api: httpx.AsyncClient, email: str) -> Headers:
    response = await api.post(
        "/api/v1/auth/register", json={"email": email, "password": STRONG_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def alice(api: httpx.AsyncClient) -> Headers:
    return await sign_up(api, "alice@example.com")


@pytest.fixture
async def bob(api: httpx.AsyncClient) -> Headers:
    return await sign_up(api, "bob@example.com")
