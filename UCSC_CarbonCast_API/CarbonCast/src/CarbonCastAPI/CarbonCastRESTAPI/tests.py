# Make the "tests" name resolve to the tests/ package directory so Django
# test discovery can load tests from CarbonCastRESTAPI/tests/*.py
#
# This file intentionally sets __path__ so the module acts as a package
# whose submodules live in the tests/ directory. Do NOT add tests here;
# place test modules under src/CarbonCastAPI/CarbonCastRESTAPI/tests/
import os
__path__ = [os.path.join(os.path.dirname(__file__), "tests")]
