import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class UserThrottleLimit(models.Model):
    user = models.OneToOneField('UserModel', on_delete=models.CASCADE)
    throttle_limit = models.PositiveIntegerField()

class UserModel(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=50)
    throttle_limit = models.OneToOneField(UserThrottleLimit, on_delete=models.CASCADE, null=True)
    email = models.EmailField(max_length=100, unique=True)
    password = models.CharField(max_length=32)
    otp_enabled = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)
    otp_base32 = models.CharField(max_length=255, null=True)
    otp_auth_url = models.CharField(max_length=255, null=True)
    otp_qrcode_image = models.TextField(null=True)
    password_checked = models.BooleanField(default=False)
    

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['password', 'name', 'email']

    def __str__(self):
        return self.username
