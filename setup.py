import io

from setuptools import find_packages, setup


def read(fname):
    with io.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='wagtail-pg-search-backend',
    version='1.0.0.dev0',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    url='https://github.com/leukeleu/wagtail-pg-search-backend',
    description='PostgreSQL full text search backend for Wagtail CMS',
    long_description=read('README.rst'),
    keywords=['wagtail', 'postgres', 'fulltext', 'search'],
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'License :: OSI Approved :: MIT License'
    ],
    license='MIT',
    install_requires=[
        'Django>=1.10',
        'psycopg2',
        'six',
        'wagtail'
    ],
    test_suite='runtests.runtests'
)
