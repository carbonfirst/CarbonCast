from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import permissions
from django.utils import timezone
from django.contrib.auth import get_user_model
from CarbonCastRESTAPI.models import UserThrottleLimit

from CarbonCastRESTAPI.models import EmissionActual
from CarbonCastRESTAPI.views import CarbonIntensityApiView

class DBIntegrationTest(TestCase):
    def setUp(self):
        # Ensure view does not enforce throttle/auth during the unit test
        CarbonIntensityApiView.permission_classes = [permissions.AllowAny]
        self.factory = APIRequestFactory()
        # create a lightweight test user to avoid AnonymousUser errors
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='pw', email='test@example.com')
        # create a related UserThrottleLimit so view logic that accesses user.userthrottlelimit works
        try:
            UserThrottleLimit.objects.create(user=self.user, throttle_limit=100)
        except Exception:
            # defensive: if creation fails, tests will still run but may hit throttle checks
            pass

    def test_ci_latest_from_db(self):
        # create a simple EmissionActual row
        ts = timezone.now()
        EmissionActual.objects.create(
            region='PJM',
            ts=ts,
            lifecycle=1.23,
            direct=4.56,
            data={'creation_time (UTC)': 'ct', 'version': 'v'}
        )

        request = self.factory.get('/CarbonIntensity', {'region_code': 'PJM'})
        # authenticate the request to satisfy view logic that expects a user
        force_authenticate(request, user=self.user)
        response = CarbonIntensityApiView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item.get('region_code'), 'PJM')
        # numeric fields may be returned as numbers or strings; compare as float
        self.assertAlmostEqual(float(item.get('carbon_intensity_avg_lifecycle')), 1.23, places=3)
        self.assertAlmostEqual(float(item.get('carbon_intensity_avg_direct')), 4.56, places=3)