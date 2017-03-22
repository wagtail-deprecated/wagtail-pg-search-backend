import io

from setuptools import find_packages, setup

setup(
    name='wagtail-pg-search-backend',
    version='1.0.0.dev0',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    url='https://github.com/leukeleu/wagtail-pg-search-backend',
    description='PostgreSQL full text search backend for Wagtail CMS',
    long_description=io.open('README.rst').read(),
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
        'wagtail'
    ],
    test_suite='runtests.runtests'
)
