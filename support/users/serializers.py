from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.models import User


class GroupsTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds the user's groups (roles) to the JWT so clients can inspect their role."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["groups"] = list(user.groups.values_list("name", flat=True))
        return token


class MeSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "groups", "permissions"]

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.get_all_permissions())
