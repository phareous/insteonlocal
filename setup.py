#from distutils.core import setup
from setuptools import setup, find_packages
setup(
  name = 'insteonlocal',
  py_modules = ['insteonlocal'],
  version = '0.54',
  description = 'InsteonLocal allows local (non-cloud) control of the Insteon Hub 2245-222',
  author = 'Michael Long',
  author_email = 'mplong@gmail.com',
  url = 'https://github.com/phareous/insteonlocal',
  download_url = 'https://github.com/phareous/insteonlocal/tarball/0.53',
  keywords = ['insteon'],
  package_data = {'': ['data/*.json']},
  requires = [],
  provides = ['insteonlocal'],
  install_requires = [],
#  packages=find_packages(exclude=['tests', 'tests.*']),
  packages=['insteonlocal'],
  include_package_data=True, # use MANIFEST.in during install
  zip_safe=False,
)
