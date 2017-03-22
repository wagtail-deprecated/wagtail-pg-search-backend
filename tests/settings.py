SECRET_KEY = 'this is required'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'wagtail_pgsearchbackend'
]

WAGTAILSEARCH_BACKENDS = {
    'default': {
        'BACKEND': 'wagtail_pgsearchbackend.backend',
    }
}
