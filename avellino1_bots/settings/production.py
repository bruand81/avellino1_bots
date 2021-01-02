import os
from avellino1_bots.settings.base import *

DEBUG = False

ALLOWED_HOSTS.append("avellino1-coca-bot.herokuapp.com")

SECRET_KEY = os.getenv("SECRET_KEY", "error_token")