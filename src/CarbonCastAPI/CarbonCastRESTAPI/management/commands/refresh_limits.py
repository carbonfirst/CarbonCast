from django.core.management.base import BaseCommand
from django.utils import timezone
from CarbonCastRESTAPI.models import UserThrottleLimit, UserModel
from django.conf import settings
from CarbonCastRESTAPI.throttling import SimpleRateThrottle

class Command(BaseCommand):
    help = 'Reset username and throttling limits daily at 12:00 am'

    def handle(self, *args, **kwargs):
        # Find all users and reset their username and throttle limits
        users = UserModel.objects.all()
        for user in users:
            user.username = user.get_username()
            user.throttle_limit.throttle_limit = settings.DEFAULT_THROTTLE_LIMIT 
            user.save()
            user.throttle_limit.save()

        global_throttle_limit = '100/day'
        SimpleRateThrottle.rate = global_throttle_limit
        settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['default'] = global_throttle_limit

        self.stdout.write(self.style.SUCCESS('Username and throttling limits reset for all users.'))
