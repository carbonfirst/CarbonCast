from django.core.management.base import BaseCommand
from django.conf import settings
from CarbonCastRESTAPI.models import UserModel


class Command(BaseCommand):
    help = 'Reset user throttling limits daily at 12:00 am'

    def handle(self, *args, **kwargs):
        # Throttling is disabled when DEFAULT_THROTTLE_LIMIT is None; the
        # throttle_limit column is non-nullable, so skip the reset entirely.
        if settings.DEFAULT_THROTTLE_LIMIT is None:
            self.stdout.write(self.style.SUCCESS(
                'Throttling disabled (DEFAULT_THROTTLE_LIMIT is None); nothing to reset.'))
            return

        reset_count = 0
        for user in UserModel.objects.select_related('throttle_limit'):
            if user.throttle_limit is None:
                continue
            user.throttle_limit.throttle_limit = settings.DEFAULT_THROTTLE_LIMIT
            user.throttle_limit.save()
            reset_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Throttling limits reset for {reset_count} users.'))
