"""Validadores SIGET."""
import re
from django.core.exceptions import ValidationError


class ComplexPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError('La contraseña debe tener al menos 8 caracteres.')
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Debe incluir al menos una letra mayúscula.')
        if not re.search(r'[a-z]', password):
            raise ValidationError('Debe incluir al menos una letra minúscula.')
        if not re.search(r'\d', password):
            raise ValidationError('Debe incluir al menos un número.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Debe incluir al menos un carácter especial.')

    def get_help_text(self):
        return (
            'Mínimo 8 caracteres, con mayúscula, minúscula, número y carácter especial.'
        )


def validar_archivo_tipo_documento(archivo, tipo_documento):
    if not archivo or not tipo_documento:
        return
    if not tipo_documento.admite_extension(archivo.name):
        formatos = tipo_documento.get_formatos_display()
        raise ValidationError(
            f'Formato no permitido. Formatos admitidos: {formatos}.'
        )
    max_bytes = float(tipo_documento.tamano_max_mb) * 1024 * 1024
    if archivo.size > max_bytes:
        raise ValidationError(
            f'El archivo excede el tamaño máximo de {tipo_documento.tamano_max_mb} MB.'
        )
