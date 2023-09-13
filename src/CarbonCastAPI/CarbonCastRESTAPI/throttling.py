from rest_framework import throttling

class MyViewRateThrottle(throttling.SimpleRateThrottle):
    rate = '100/day'

    def get_cache_key(self, request, view):
        return view.__class__.__name__

