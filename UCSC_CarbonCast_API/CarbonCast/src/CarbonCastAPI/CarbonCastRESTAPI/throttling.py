from rest_framework import throttling

class MyViewRateThrottle(throttling.SimpleRateThrottle):
    # Disabled - no rate limit
    rate = None

    def allow_request(self, request, view):
        # Always allow - no rate limiting
        return True

    def get_cache_key(self, request, view):
        # Return None to disable caching
        return None

