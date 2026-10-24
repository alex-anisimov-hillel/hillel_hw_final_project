from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from users.serializers import MeSerializer


class MeView(RetrieveAPIView):
    """Who am I: email, groups and effective permissions of the JWT's user."""

    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
