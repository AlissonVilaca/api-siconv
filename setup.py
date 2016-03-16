import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'pyramid==1.0',
    'PasteDeploy==1.3.4',
    'SQLAlchemy',
    'transaction',
    'repoze.tm2>=1.0b1', # default_commit_veto
    'zope.sqlalchemy',
    'WebError',
    'WebHelpers',
    'psycopg2',
    'rdflib',
    'amara',
    'geoalchemy',
    'shapely',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='wsda-siconv',
      version='0.1',
      description='Web Service de Dados Abertos do SICONV',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='wsdasiconv',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = wsdasiconv:main
      """,
      paster_plugins=['pyramid'],
      )

