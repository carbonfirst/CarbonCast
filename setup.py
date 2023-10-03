from setuptools import setup, find_packages, Command  # or find_namespace_packages
from subprocess import call

class RunDjangoServer(Command):
    description = "Run Django migrations and start the development server"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # Apply migrations
        call(["python", "src/CarbonCastAPI/manage.py", "migrate"])

        # Start the development server
        call(["python", "src/CarbonCastAPI/manage.py", "runserver", "--rmauth"])


setup(
    name = "CarbonCast",
    version = "0.0.1",
    install_requires = [
        "requests",
        "Django==4.2.5",
        "sqlparse==0.4.4",
        "djangorestframework==3.14.0",
        "qrcode==7.4.2",
        "pyotp==2.9.0",
        "entsoe-py==0.5.10",
        "xarray==2023.7.0",
        "drf-yasg",
        'importlib-metadata; python_version>="3.11.4"',
    ],
    # ...
    packages=find_packages(
        # All keyword arguments below are optional:
        where = ".",  # ["."] by default
        include = ["src/CarbonCastAPI/*", "real_time/*"],  # ["*"] by default
    ),

    scripts=["src/CarbonCastAPI/manage.py"],  # Include your Django's manage.py script
    cmdclass={
        "run_django_server": RunDjangoServer,
    },
    # ...
)