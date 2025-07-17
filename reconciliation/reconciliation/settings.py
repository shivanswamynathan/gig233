import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
env_file_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_file_path)

# Media and static paths
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Secret Key & Debug
SECRET_KEY = os.getenv(
    'SECRET_KEY', 'django-insecure-hy&@#2*#huv0rubixkshqpwf9*$v7ee#4e9uh(b+42r#j@)3^=')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,*').split(',')

# Logging setup
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / 'database_connection.log')
    ]
)
logger = logging.getLogger(__name__)
logger.info("Loading environment variables from: %s", env_file_path)

# Helper to load and log env


def get_env_var(key, default=None, mask=False):
    val = os.getenv(key, default)
    log_val = '***MASKED***' if mask and val else val
    logger.info(f"{key}: {log_val}")
    return val


# Database Configuration
DB_NAME = get_env_var('DB_NAME')
DB_USER = get_env_var('DB_USER')
DB_PASSWORD = get_env_var('DB_PASSWORD', mask=True)
DB_HOST = get_env_var('DB_HOST')
DB_PORT = get_env_var('DB_PORT')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'CONN_MAX_AGE': 600,
    }
}

# Optional: Database Pooling
DATABASE_CONNECTION_POOLING = {
    'default': {
        'BACKEND': 'django_db_pool.backends.postgresql',
        'POOL_OPTIONS': {
            'INITIAL_CONNS': 1,
            'MAX_CONNS': 20,
            'MIN_CACHED_CONNS': 0,
            'MAX_CACHED_CONNS': 50,
            'MAX_LIFETIME': 3600,
        }
    }
}

# Google AI Config
GEMINI_MODEL = get_env_var('GEMINI_MODEL', 'gemini-2.0-flash')
GOOGLE_API_KEY = get_env_var('GOOGLE_API_KEY', mask=True)

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'document_processing',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'reconciliation.urls'

# Templates
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

WSGI_APPLICATION = 'reconciliation.wsgi.application'

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Localization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Auto Field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File Upload Limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{levelname}] {asctime} {module} {message}', 'style': '{'},
        'simple': {'format': '[{levelname}] {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'file': {'class': 'logging.FileHandler', 'filename': LOG_DIR / 'invoice_processing.log', 'formatter': 'verbose'},
        'db_file': {'class': 'logging.FileHandler', 'filename': LOG_DIR / 'database_operations.log', 'formatter': 'verbose'},
        'itemwise_grn_file': {'class': 'logging.FileHandler', 'filename': LOG_DIR / 'itemwise_grn_processing.log', 'formatter': 'verbose'},
    },
    'loggers': {
        'document_processing': {
            'handlers': ['console', 'file', 'db_file', 'itemwise_grn_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'document_processing.reconciliation': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['db_file'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}
