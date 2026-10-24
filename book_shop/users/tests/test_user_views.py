import pytest


@pytest.mark.django_db
def test_user_registration(client):
    response = client.get("/accounts/register")
    assert response.status_code == 200
