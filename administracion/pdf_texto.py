"""Utilidades de texto para documentos PDF oficiales."""
import unicodedata
from pathlib import Path

from django.conf import settings


def texto_sin_acentos(valor):
    """Elimina diacríticos (á→a, ñ→n, ü→u, etc.)."""
    if valor is None:
        return ''
    s = unicodedata.normalize('NFKD', str(valor))
    return ''.join(c for c in s if not unicodedata.combining(c))


def nombre_documento(valor):
    """
    Nombre para documentos oficiales:
    mayúsculas y minúsculas (Title Case) y sin acentos.
    Ej: 'BELÉN YERAHÍ' → 'Belen Yerahi'
    """
    s = texto_sin_acentos(valor).strip()
    if not s:
        return ''
    return ' '.join(parte.capitalize() for parte in s.split())


def static_dir():
    """Ruta absoluta a static/ del proyecto (para fuentes e imágenes en xhtml2pdf)."""
    return Path(settings.BASE_DIR) / 'static'
