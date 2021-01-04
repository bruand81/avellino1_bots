import os
from avellino1_bots.settings.base import *

DEBUG = False

ALLOWED_HOSTS.append("avellino1-coca-bot.herokuapp.com")

SECRET_KEY = os.getenv("SECRET_KEY", "error_token")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv("DATABASE_NAME", "error_token"),
        'USER': os.getenv("DATABASE_USER", "error_token"),
        'PASSWORD': os.getenv("DATABASE_PASSWORD", "error_token"),
        'HOST': os.getenv("DATABASE_HOST", "error_token"),
        'PORT': os.getenv("DATABASE_PORT", "error_token"),
    }
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)
