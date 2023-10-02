from django.conf import settings
from rest_framework import permissions, authentication

carbon_cast_version = "v3.0"

authentication_classes = []
permission_classes = []

if settings.REQUIRES_AUTH == 'True':
    print("From here if")
    authentication_classes = [authentication.SessionAuthentication, authentication.BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]
else:
    print("From here else")
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    