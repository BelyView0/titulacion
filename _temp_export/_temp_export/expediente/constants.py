"""Constantes compartidas del módulo expediente."""

FORMATO_DOCUMENTO_CHOICES = [
    ('pdf', 'PDF'),
    ('jpg', 'JPG / JPEG'),
    ('png', 'PNG'),
    ('webp', 'WEBP'),
]

FORMATO_MIME_MAP = {
    'pdf': ['application/pdf'],
    'jpg': ['image/jpeg'],
    'png': ['image/png'],
    'webp': ['image/webp'],
}

FORMATO_EXTENSION_MAP = {
    'pdf': ['.pdf'],
    'jpg': ['.jpg', '.jpeg'],
    'png': ['.png'],
    'webp': ['.webp'],
}

DEFAULT_FORMATOS = ['pdf']
DEFAULT_TAMANO_MAX_MB = 2.5
