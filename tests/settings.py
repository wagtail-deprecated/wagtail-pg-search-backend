SECRET_KEY = 'this is required'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wagtail_pgsearchbackend',
        'USER': 'postgres'
    }
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',

    'modelcluster',
    'taggit',

    'wagtail.wagtailcore',
    'wagtail.wagtailsearch',
    'wagtail.tests.search',

    'wagtail_pgsearchbackend',
]

WAGTAILSEARCH_BACKENDS = {
    'default': {
        'BACKEND': 'wagtail_pgsearchbackend.backend',
    }
}


# Don't run migrations, just create tables.

class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
