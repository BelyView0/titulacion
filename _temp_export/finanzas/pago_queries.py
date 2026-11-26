"""Consultas compartidas del módulo Finanzas — etapa de pago."""
from expediente.models import EstadoExpediente, Expediente

# Expedientes visibles en la bandeja de pagos de Finanzas.
ESTADOS_BANDEJA_PAGO_FINANZAS = (
    EstadoExpediente.OFICIO_FIRMADO,
    EstadoExpediente.PAGO_PENDIENTE,
    EstadoExpediente.PAGO_VALIDADO,
)

# Estados en los que Finanzas puede generar la preficha.
ESTADOS_GENERAR_PREFICHA = (
    EstadoExpediente.OFICIO_FIRMADO,
    EstadoExpediente.PAGO_PENDIENTE,
)


def expedientes_bandeja_pago_finanzas():
    return Expediente.objects.filter(estado__in=ESTADOS_BANDEJA_PAGO_FINANZAS)
