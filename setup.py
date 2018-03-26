import os
import pip
from pip.req import parse_requirements
from setuptools import find_packages, setup

requirements = parse_requirements(
    "requirements.txt", session=pip.download.PipSession())
reqs = [str(ir.req) for ir in requirements]

setup(
    name="influxdb_logging",
    version=(os.environ['CIRCLE_TAG']
             if 'CIRCLE_TAG' in os.environ else '2.0.0'),
    description="InfluxDB logging handlers",
    url="https://github.com/gsr-zug/influxdb_logging",
    author="Jefferson Heard",
    author_email="jheard@teamworks.com",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=reqs,
    setup_requires=[
        'pytest-runner'
    ],
    tests_require=[
        "pytest-cov",
        "pytest"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Logging"
    ],
    python_requires='>=3'
)
