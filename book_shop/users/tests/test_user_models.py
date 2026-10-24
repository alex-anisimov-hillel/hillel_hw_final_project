import pytest

from users.models import User


@pytest.mark.django_db
def test_user_number(user_factory):
    user = user_factory(phone_number="0123456778")
    assert user.phone_number == "0123456778"


@pytest.mark.django_db
def test_user_number_multiple(user_factory):
    user1 = user_factory()
    user2 = user_factory()
    assert user1 != user2


@pytest.mark.django_db
def test_user_str_representation(user_factory):
    # Generated with AI, reviewed and modified
    user = user_factory(email="jane@example.com", first_name="Jane", last_name="Doe")
    assert str(user) == "jane@example.com -- Jane Doe"


@pytest.mark.django_db
def test_create_user_sets_hashed_password_and_defaults():
    # Generated with AI, reviewed and modified
    user = User.objects.create_user(
        email="newuser@example.com",
        first_name="New",
        last_name="User",
        password="strong-pass-123",
        phone_number="1112223333",
    )
    assert user.check_password("strong-pass-123")
    assert user.email == "newuser@example.com"
    assert user.is_staff is False
    assert user.is_superuser is False


@pytest.mark.django_db
def test_create_user_without_email_raises_value_error():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="", first_name="A", last_name="B", password="pass"
        )


@pytest.mark.django_db
def test_create_user_without_first_name_raises_value_error():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="a@example.com", first_name="", last_name="B", password="pass"
        )


@pytest.mark.django_db
def test_create_user_without_last_name_raises_value_error():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="a@example.com", first_name="A", last_name="", password="pass"
        )


@pytest.mark.django_db
def test_create_superuser_sets_staff_and_superuser_flags():
    # Generated with AI, reviewed and modified
    user = User.objects.create_superuser(
        email="admin@example.com",
        first_name="Admin",
        last_name="Root",
        password="pass",
        phone_number="9998887777",
    )
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_create_superuser_with_is_staff_false_raises_value_error():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin2@example.com",
            first_name="Admin",
            last_name="Root",
            password="pass",
            is_staff=False,
        )


@pytest.mark.django_db
def test_create_superuser_with_is_superuser_false_raises_value_error():
    # Generated with AI, reviewed and modified
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email="admin3@example.com",
            first_name="Admin",
            last_name="Root",
            password="pass",
            is_superuser=False,
        )
