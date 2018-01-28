# setup.py
# ========
#
# Copying
# -------
#
# Copyright (c) 2018 loggen authors and contributors.
#
# This file is part of the *loggen* project.
#
# Loggen is a free software project. You can redistribute it and/or
# modify if under the terms of the MIT License.
#
# This software project is distributed *as is*, WITHOUT WARRANTY OF ANY
# KIND; including but not limited to the WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE and NONINFRINGEMENT.
#
# You should have received a copy of the MIT License along with
# loggen. If not, see <http://opensource.org/licenses/MIT>.
#
import os

from contextlib import suppress
from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))
LONG_DESCRIPTION = ''
with suppress(OSError), open(os.path.join(HERE, 'README.rst')) as fp:
    LONG_DESCRIPTION = fp.read()


setup(
    name='loggen',
    version='1.2.0',
    license='MIT',
    url='https://github.com/spack971/loggen',

    author='Jimmy Thrasibule',
    author_email='loggen@jimmy.lt',

    description='A syslog message generator.',
    long_description=LONG_DESCRIPTION,
    keywords='syslog generator rfc5424 rfc3164',

    packages=find_packages(),

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers.
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Development Status :: 5 - Production/Stable',

        'Environment :: Console',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Topic :: System :: Logging',
        'Topic :: Utilities',
    ],

    install_requires=[
        'rfc5424-logging-handler',
        'semver',
    ],

    entry_points={
        'console_scripts': [
            'loggen = loggen:main',
        ],
    },
)
