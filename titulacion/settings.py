"""
Django settings for Sistema de Gestión de Titulación - ITA
Instituto Tecnológico de Apizaco
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-v-!#9q7$-wuprtdv))c9rg(-fh2%kv(h%j2l)(3ezq#=293a!'

DEBUG = True

ALLOWED_HOSTS = ['*']

# ─── APLICACIONES ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps del sistema
    'administracion',
    'expediente',
    'alumnos',
    'escolares',
    'academico',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'titulacion.urls'

# ─── TEMPLATES ───────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'expediente.context_processors.notificaciones_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'titulacion.wsgi.application'

# ─── BASE DE DATOS ────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'titulacion_2026',
        'USER': 'belyview',
        'PASSWORD': '241203',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# ─── AUTENTICACIÓN ───────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'administracion.Usuario'

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/auth/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── INTERNACIONALIZACIÓN ────────────────────────────────────────────────────
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# ─── ARCHIVOS ESTÁTICOS Y MEDIA ──────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── CORREO ELECTRÓNICO ──────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'belyersua24@gmail.com'
EMAIL_HOST_PASSWORD = 'fsvz jdpr rkhm xrnb'
DEFAULT_FROM_EMAIL = 'Sistema de Titulación ITA <belyersua24@gmail.com>'
EMAIL_SUBJECT_PREFIX = '[ITA Titulación] '

# ─── TAMAÑO MÁXIMO ARCHIVOS ───────────────────────────────────────────────────
# 10 MB por archivo (los PDFs del ITA deben ser < 2MB por documento)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
