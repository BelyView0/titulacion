"""
Modelos del Núcleo del Sistema de Titulación (App Expediente)
Incluye todos los modelos del proceso:
- PlanEstudios, Modalidad, TipoDocumento (catálogos)
- Expediente, Documento, ValidacionDocumento
- EnvioCDMX, RecepcionEmpastado
- AsignacionJurado, ActoProtocolario
- HistorialExpediente, HistorialDocumento
"""
from django.db import models
from django.conf import settings
from django.utils import timezone

from expediente.constants import DEFAULT_FORMATOS, DEFAULT_TAMANO_MAX_MB


# ─────────────────────────────────────────────────────────────
# CATÁLOGOS ADMINISTRABLES
# ─────────────────────────────────────────────────────────────

class PlanEstudios(models.Model):
    nombre = models.CharField(max_length=20, unique=True, verbose_name='Plan de Estudios')
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Plan de Estudios'
        verbose_name_plural = 'Planes de Estudios'
        ordering = ['-nombre']

    def __str__(self):
        return f'Plan {self.nombre}'


class Modalidad(models.Model):
    """Modalidades de titulación por plan de estudios."""
    plan_estudios = models.ForeignKey(
        PlanEstudios, on_delete=models.CASCADE,
        related_name='modalidades',
        verbose_name='Plan de Estudios'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre de la modalidad')
    clave = models.CharField(max_length=30, verbose_name='Clave (ej: RESIDENCIA, TESIS)')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Modalidad de Titulación'
        verbose_name_plural = 'Modalidades de Titulación'
        ordering = ['plan_estudios', 'nombre']

    def __str__(self):
        return f'{self.nombre} — {self.plan_estudios}'


class TipoDocumento(models.Model):
    """
    Catálogo de documentos requeridos por modalidad.
    El administrador configura qué documentos pide cada modalidad.
    """
    modalidad = models.ForeignKey(
        Modalidad, on_delete=models.CASCADE,
        related_name='tipos_documento',
        verbose_name='Modalidad'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del documento')
    descripcion_ayuda = models.TextField(
        verbose_name='Instrucciones para el alumno',
        help_text='Describe cómo debe ser el documento (formato, requisitos, etc.)'
    )
    es_obligatorio = models.BooleanField(default=True, verbose_name='¿Es obligatorio?')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden de presentación')
    formatos_admitidos = models.JSONField(
        default=list,
        verbose_name='Formatos admitidos',
        help_text='Lista de formatos: pdf, jpg, png, webp'
    )
    tamano_max_mb = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=DEFAULT_TAMANO_MAX_MB,
        verbose_name='Tamaño máximo (MB)'
    )
    # Campos legados (se eliminan en migración)
    valida_division = models.BooleanField(default=True, verbose_name='Valida División (legado)')
    valida_escolares = models.BooleanField(default=True, verbose_name='Valida Escolares (legado)')
    acepta_solo_pdf = models.BooleanField(default=True, verbose_name='Solo PDF (legado)')
    es_fotografia = models.BooleanField(default=False, verbose_name='Es fotografía (legado)')

    class Meta:
        verbose_name = 'Tipo de Documento Requerido'
        verbose_name_plural = 'Tipos de Documentos Requeridos'
        ordering = ['modalidad', 'orden']

    def __str__(self):
        return f'{self.nombre} ({self.modalidad.nombre})'

    def save(self, *args, **kwargs):
        if not self.formatos_admitidos:
            if self.es_fotografia:
                self.formatos_admitidos = ['jpg', 'png']
            elif self.acepta_solo_pdf:
                self.formatos_admitidos = ['pdf']
            else:
                self.formatos_admitidos = list(DEFAULT_FORMATOS)
        super().save(*args, **kwargs)

    def get_formatos_display(self):
        return ', '.join(f.upper() for f in (self.formatos_admitidos or DEFAULT_FORMATOS))

    def admite_extension(self, filename):
        from expediente.constants import FORMATO_EXTENSION_MAP
        ext = ('.' + filename.rsplit('.', 1)[-1].lower()) if '.' in filename else ''
        for fmt in (self.formatos_admitidos or DEFAULT_FORMATOS):
            if ext in FORMATO_EXTENSION_MAP.get(fmt, []):
                return True
        return False

    @property
    def es_documento_imagen(self):
        formatos = self.formatos_admitidos or []
        return bool(formatos) and all(f in ('jpg', 'png', 'webp') for f in formatos)

    @property
    def requiere_validacion_oficina(self):
        """SIGET: unifica valida_division y valida_escolares en Oficina de Titulación."""
        return self.valida_division or self.valida_escolares


# ─────────────────────────────────────────────────────────────
# ESTADOS DEL PROCESO
# ─────────────────────────────────────────────────────────────

class EstadoExpediente(models.TextChoices):
    # SIGET — flujo principal
    DATOS_EXPEDIENTE = 'DATOS_EXPEDIENTE', 'Datos del expediente'
    CERTIFICADO_PENDIENTE_CITA = 'CERTIFICADO_PENDIENTE_CITA', 'Certificado — pendiente de cita'
    CERTIFICADO_CITA_PROGRAMADA = 'CERTIFICADO_CITA_PROGRAMADA', 'Certificado — cita programada'
    CERTIFICADO_FIRMADO = 'CERTIFICADO_FIRMADO', 'Certificado firmado'
    CARGA_DOCUMENTOS = 'CARGA_DOCUMENTOS', 'Carga de documentos'
    EN_REVISION = 'EN_REVISION', 'En revisión — Oficina de Titulación'
    EN_CORRECCION = 'EN_CORRECCION', 'En corrección por el alumno'
    EXPEDIENTE_APROBADO = 'EXPEDIENTE_APROBADO', 'Expediente aprobado'
    OFICIO_GENERADO = 'OFICIO_GENERADO', 'Oficio de publicación generado'
    OFICIO_CITA_PROGRAMADA = 'OFICIO_CITA_PROGRAMADA', 'Oficio — cita programada'
    OFICIO_FIRMADO = 'OFICIO_FIRMADO', 'Oficio firmado y cargado'
    PAGO_PENDIENTE = 'PAGO_PENDIENTE', 'Pago pendiente'
    PAGO_VALIDADO = 'PAGO_VALIDADO', 'Pago validado'
    ADEUDOS_EN_REVISION = 'ADEUDOS_EN_REVISION', 'Confirmación de no adeudos'
    DOCUMENTOS_OFICIALES_LISTOS = 'DOCUMENTOS_OFICIALES_LISTOS', 'Documentos oficiales listos'
    JURADO_ASIGNADO = 'JURADO_ASIGNADO', 'Jurado asignado'
    PROTOCOLO_PROGRAMADO = 'PROTOCOLO_PROGRAMADO', 'Protocolo programado'
    ACTO_REALIZADO = 'ACTO_REALIZADO', 'Acto protocolario realizado'
    CONCLUIDO = 'CONCLUIDO', 'Proceso concluido'
    CANCELADO = 'CANCELADO', 'Cancelado'
    # Estados legados (migración)
    BORRADOR = 'BORRADOR', 'Borrador (legado)'
    EN_REVISION_ACADEMICO = 'EN_REVISION_ACADEMICO', 'Revisión académica (legado)'
    RECHAZADO_ACADEMICO = 'RECHAZADO_ACADEMICO', 'Rechazado académico (legado)'
    DOCUMENTOS_PENDIENTES = 'DOCUMENTOS_PENDIENTES', 'Documentos pendientes (legado)'
    EN_REVISION_DOCUMENTOS = 'EN_REVISION_DOCUMENTOS', 'Revisión documentos (legado)'
    LISTO_INTEGRACION = 'LISTO_INTEGRACION', 'Listo integración (legado)'
    PAGO_EN_REVISION = 'PAGO_EN_REVISION', 'Pago en revisión (legado)'
    INTEGRADO = 'INTEGRADO', 'Integrado (legado)'
    EMPASTADO_PENDIENTE = 'EMPASTADO_PENDIENTE', 'Empastado pendiente (legado)'
    EMPASTADO_RECIBIDO = 'EMPASTADO_RECIBIDO', 'Empastado recibido (legado)'
    ACTO_PROGRAMADO = 'ACTO_PROGRAMADO', 'Acto programado (legado)'
    ACTA_EXENCION = 'ACTA_EXENCION', 'Acta exención (legado)'


ESTADOS_ACTIVOS_SIGET = [
    EstadoExpediente.DATOS_EXPEDIENTE,
    EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
    EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
    EstadoExpediente.CERTIFICADO_FIRMADO,
    EstadoExpediente.CARGA_DOCUMENTOS,
    EstadoExpediente.EN_REVISION,
    EstadoExpediente.EN_CORRECCION,
    EstadoExpediente.EXPEDIENTE_APROBADO,
    EstadoExpediente.OFICIO_GENERADO,
    EstadoExpediente.OFICIO_CITA_PROGRAMADA,
    EstadoExpediente.OFICIO_FIRMADO,
    EstadoExpediente.PAGO_PENDIENTE,
    EstadoExpediente.PAGO_VALIDADO,
    EstadoExpediente.ADEUDOS_EN_REVISION,
    EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
    EstadoExpediente.JURADO_ASIGNADO,
    EstadoExpediente.PROTOCOLO_PROGRAMADO,
    EstadoExpediente.ACTO_REALIZADO,
]

ESTADOS_INTEGRADOS = [
    EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
    EstadoExpediente.JURADO_ASIGNADO,
    EstadoExpediente.PROTOCOLO_PROGRAMADO,
    EstadoExpediente.ACTO_REALIZADO,
    EstadoExpediente.CONCLUIDO,
]

COLORES_ESTADO = {
    # SIGET
    EstadoExpediente.DATOS_EXPEDIENTE: 'secondary',
    EstadoExpediente.CERTIFICADO_PENDIENTE_CITA: 'warning',
    EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA: 'info',
    EstadoExpediente.CERTIFICADO_FIRMADO: 'success',
    EstadoExpediente.CARGA_DOCUMENTOS: 'warning',
    EstadoExpediente.EN_REVISION: 'info',
    EstadoExpediente.EN_CORRECCION: 'warning',
    EstadoExpediente.EXPEDIENTE_APROBADO: 'success',
    EstadoExpediente.OFICIO_GENERADO: 'primary',
    EstadoExpediente.OFICIO_CITA_PROGRAMADA: 'info',
    EstadoExpediente.OFICIO_FIRMADO: 'success',
    EstadoExpediente.PAGO_PENDIENTE: 'warning',
    EstadoExpediente.PAGO_VALIDADO: 'success',
    EstadoExpediente.ADEUDOS_EN_REVISION: 'info',
    EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS: 'primary',
    EstadoExpediente.JURADO_ASIGNADO: 'primary',
    EstadoExpediente.PROTOCOLO_PROGRAMADO: 'primary',
    EstadoExpediente.ACTO_REALIZADO: 'success',
    EstadoExpediente.CONCLUIDO: 'success',
    EstadoExpediente.CANCELADO: 'danger',
    # Legados (pueden existir en BD)
    EstadoExpediente.BORRADOR: 'secondary',
    EstadoExpediente.EN_REVISION_ACADEMICO: 'info',
    EstadoExpediente.RECHAZADO_ACADEMICO: 'danger',
    EstadoExpediente.DOCUMENTOS_PENDIENTES: 'warning',
    EstadoExpediente.EN_REVISION_DOCUMENTOS: 'info',
    EstadoExpediente.LISTO_INTEGRACION: 'primary',
    EstadoExpediente.PAGO_EN_REVISION: 'info',
    EstadoExpediente.INTEGRADO: 'primary',
    EstadoExpediente.EMPASTADO_PENDIENTE: 'warning',
    EstadoExpediente.EMPASTADO_RECIBIDO: 'success',
    EstadoExpediente.ACTO_PROGRAMADO: 'primary',
    EstadoExpediente.ACTA_EXENCION: 'info',
    'ESPERANDO_CONSTANCIA': 'warning',
    'CONSTANCIA_EN_REVISION': 'info',
    'RECIBI_PAPEL_ORIGINAL': 'primary',
    'TRAMITE_DGP': 'info',
    'CEDULA_EN_REVISION': 'warning',
    'CEDULA_RECHAZADA': 'danger',
    'CITA_ENTREGA': 'success',
    'ENVIADO_CDMX': 'info',
    'RECHAZADO_CDMX': 'danger',
    'APROBADO_CDMX': 'success',
}

ETAPAS_PROGRESO_SIGET = [
    EstadoExpediente.DATOS_EXPEDIENTE,
    EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
    EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
    EstadoExpediente.CERTIFICADO_FIRMADO,
    EstadoExpediente.CARGA_DOCUMENTOS,
    EstadoExpediente.EN_REVISION,
    EstadoExpediente.EXPEDIENTE_APROBADO,
    EstadoExpediente.OFICIO_GENERADO,
    EstadoExpediente.OFICIO_CITA_PROGRAMADA,
    EstadoExpediente.OFICIO_FIRMADO,
    EstadoExpediente.PAGO_PENDIENTE,
    EstadoExpediente.PAGO_VALIDADO,
    EstadoExpediente.ADEUDOS_EN_REVISION,
    EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
    EstadoExpediente.JURADO_ASIGNADO,
    EstadoExpediente.PROTOCOLO_PROGRAMADO,
    EstadoExpediente.ACTO_REALIZADO,
    EstadoExpediente.CONCLUIDO,
]

ESTADOS_SLA_ACTIVOS = {
    EstadoExpediente.EN_REVISION,
    EstadoExpediente.EN_CORRECCION,
    EstadoExpediente.PAGO_PENDIENTE,
    EstadoExpediente.ADEUDOS_EN_REVISION,
    EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
    EstadoExpediente.OFICIO_CITA_PROGRAMADA,
    EstadoExpediente.EN_REVISION_ACADEMICO,
    EstadoExpediente.EN_REVISION_DOCUMENTOS,
    EstadoExpediente.PAGO_EN_REVISION,
    'CONSTANCIA_EN_REVISION',
    'CEDULA_EN_REVISION',
    EstadoExpediente.LISTO_INTEGRACION,
}


class EstadoDocumento(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente de carga'
    CARGADO = 'CARGADO', 'Cargado — Sin Revisar'
    EN_REVISION = 'EN_REVISION', 'En Revisión'
    APROBADO = 'APROBADO', 'Aprobado'
    RECHAZADO = 'RECHAZADO', 'Rechazado'
    REQUIERE_CORRECCION = 'REQUIERE_CORRECCION', 'Requiere Corrección'


class EstadoValidacion(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APROBADO = 'APROBADO', 'Aprobado'
    RECHAZADO = 'RECHAZADO', 'Rechazado'
    REQUIERE_CORRECCION = 'REQUIERE_CORRECCION', 'Requiere Corrección'


# ─────────────────────────────────────────────────────────────
# EXPEDIENTE
# ─────────────────────────────────────────────────────────────

class Expediente(models.Model):
    """
    Expediente de titulación del alumno.
    Existe uno por alumno. Centraliza todo el proceso.
    """
    alumno = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expediente',
        limit_choices_to={'rol': 'ALUMNO'},
        verbose_name='Alumno'
    )
    modalidad = models.ForeignKey(
        Modalidad, on_delete=models.PROTECT,
        verbose_name='Modalidad de Titulación',
        null=True, blank=True
    )
    estado = models.CharField(
        max_length=40,
        choices=EstadoExpediente.choices,
        default=EstadoExpediente.DATOS_EXPEDIENTE,
        verbose_name='Estado del proceso'
    )
    plan_estudios = models.ForeignKey(
        'PlanEstudios', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='expedientes',
        verbose_name='Plan de estudios'
    )
    asesor = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='alumnos_asesorados',
        verbose_name='Asesor'
    )
    certificado_digital = models.FileField(
        upload_to='certificados/%Y/',
        null=True, blank=True,
        verbose_name='Certificado digitalizado'
    )
    oficio_publicacion_pdf = models.FileField(
        upload_to='oficios_publicacion/%Y/',
        null=True, blank=True,
        verbose_name='Oficio de autorización de publicación'
    )
    oficio_publicacion_escaneado = models.FileField(
        upload_to='oficios_publicacion_escaneados/%Y/',
        null=True, blank=True,
        verbose_name='Oficio de publicación escaneado (firmado)'
    )
    constancia_no_adeudos = models.FileField(
        upload_to='constancias_adeudos/%Y/',
        null=True, blank=True,
        verbose_name='Constancia de no adeudos'
    )
    certificacion_final_pdf = models.FileField(
        upload_to='certificaciones/%Y/',
        null=True, blank=True,
        verbose_name='Certificación de exención'
    )
    # Datos del trabajo terminal
    titulo_trabajo = models.CharField(
        max_length=500, blank=True,
        verbose_name='Título del trabajo / proyecto'
    )
    nombre_empresa = models.CharField(
        max_length=300, blank=True,
        verbose_name='Empresa / Organización (para residencia)'
    )
    # Fotografía del alumno (digital)
    fotografia_digital = models.ImageField(
        upload_to='fotografias/%Y/',
        null=True, blank=True,
        verbose_name='Fotografía óvalo (digital)'
    )
    # Fotografía física (entrega independiente por departamento)
    foto_fisica_division = models.BooleanField(
        default=False,
        verbose_name='¿Foto física entregada en División de Estudios Profesionales?'
    )
    foto_fisica_escolares = models.BooleanField(
        default=False,
        verbose_name='¿Foto física entregada en Servicios Escolares?'
    )
    # Campos de Pago
    comprobante_pago = models.FileField(
        upload_to='comprobantes_pago/%Y/',
        null=True, blank=True,
        verbose_name='Comprobante de Pago (PDF)'
    )
    pago_validado = models.CharField(
        max_length=20,
        choices=[
            ('PENDIENTE', 'Pendiente de Carga'),
            ('CARGADO', 'Comprobante Cargado'),
            ('APROBADO', 'Aprobado'),
            ('RECHAZADO', 'Rechazado')
        ],
        default='PENDIENTE',
        verbose_name='Estado de Validación del Pago'
    )
    pago_observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones de Validación del Pago'
    )
    fecha_subida_pago = models.DateTimeField(null=True, blank=True)
    fecha_validacion_pago = models.DateTimeField(null=True, blank=True)
    # Constancia de No Inconveniencia (automática tras confirmar no adeudos)
    constancia_no_inconveniencia = models.FileField(
        upload_to='constancias/%Y/',
        null=True, blank=True,
        verbose_name='Constancia de No Inconveniencia (PDF firmado)'
    )
    fecha_constancia = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de carga de la constancia')

    # Gestión de Cédula y Cita de Entrega
    cedula_profesional_pdf = models.FileField(
        upload_to='cedulas/%Y/',
        null=True, blank=True,
        verbose_name='Cédula Profesional (PDF)'
    )
    fecha_subida_cedula = models.DateTimeField(null=True, blank=True)
    observaciones_cedula = models.TextField(blank=True, verbose_name='Observaciones de revisión de cédula')
    
    fecha_cita_entrega = models.DateTimeField(null=True, blank=True, verbose_name='Fecha y Hora de Cita para Entrega')
    instrucciones_cita = models.TextField(blank=True, verbose_name='Instrucciones para la Cita')

    # Fechas clave
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de apertura')
    fecha_ultima_actualizacion = models.DateTimeField(auto_now=True)
    fecha_conclusion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de conclusión')
    fecha_ultimo_recordatorio = models.DateTimeField(null=True, blank=True, verbose_name='Fecha del último recordatorio')

    # Campos para el flujo de Acta de Exención y DGP
    notificacion_dgp_enviada = models.BooleanField(
        default=False, 
        verbose_name='Notificación DGP enviada'
    )
    datos_dgp_confirmados = models.BooleanField(
        default=False,
        verbose_name='Datos DGP confirmados por el alumno'
    )
    acta_exencion_pdf = models.FileField(
        upload_to='actas_exencion/', 
        null=True, blank=True,
        verbose_name='Acta de Exención / Examen (PDF)'
    )

    # Observaciones generales de División de Estudios Profesionales
    observaciones_division = models.TextField(
        blank=True,
        verbose_name='Observaciones de División de Estudios Profesionales'
    )

    class Meta:
        verbose_name = 'Expediente de Titulación'
        verbose_name_plural = 'Expedientes de Titulación'
        ordering = ['-fecha_apertura']

    def __str__(self):
        return f'Expediente #{self.pk} — {self.alumno.get_full_name()}'

    def get_estado_display_color(self):
        return COLORES_ESTADO.get(self.estado, 'secondary')

    def porcentaje_progreso(self):
        """Calcula el porcentaje de avance del proceso para la barra de progreso."""
        estado = self.estado
        if estado == EstadoExpediente.EN_CORRECCION:
            estado = EstadoExpediente.CARGA_DOCUMENTOS
        if estado in ETAPAS_PROGRESO_SIGET:
            idx = ETAPAS_PROGRESO_SIGET.index(estado)
            return round((idx / (len(ETAPAS_PROGRESO_SIGET) - 1)) * 100)
        return 0

    @property
    def dias_en_estado_actual(self):
        """Retorna el número de días que lleva el expediente en su estado actual."""
        ultimo_cambio = self.historial.filter(estado_nuevo=self.estado).order_by('-fecha').first()
        if ultimo_cambio:
            delta = timezone.now() - ultimo_cambio.fecha
        else:
            delta = timezone.now() - self.fecha_apertura
        return delta.days

    @property
    def semaforo_sla(self):
        """Retorna la clase CSS del color del semáforo SLA basado en los días en el estado actual."""
        if self.estado not in ESTADOS_SLA_ACTIVOS:
            return 'secondary'

        dias = self.dias_en_estado_actual
        if dias < 3:
            return 'success'    # Verde: SLA a tiempo
        elif dias <= 5:
            return 'warning'    # Amarillo: En riesgo
        else:
            return 'danger'     # Rojo: Retrasado

    def documentos_aprobados(self):
        return self.documentos.filter(estado=EstadoDocumento.APROBADO).count()

    def documentos_total(self):
        return self.documentos.count()

    def documentos_pendientes(self):
        return self.documentos.exclude(estado=EstadoDocumento.APROBADO).count()

    def todos_documentos_aprobados(self):
        """Return True only if all *obligatory* documents are approved."""
        docs = self.documentos.filter(tipo_documento__es_obligatorio=True)
        if not docs.exists():
            return False
        return all(d.estado == EstadoDocumento.APROBADO for d in docs)

    @property
    def get_documento_fotografia(self):
        """Retorna el objeto documento que es de tipo fotografía."""
        return self.documentos.filter(tipo_documento__es_fotografia=True).first()


# ─────────────────────────────────────────────────────────────
# DOCUMENTOS
# ─────────────────────────────────────────────────────────────

def upload_documento_path(instance, filename):
    return (
        f'documentos/{instance.expediente.alumno.pk}/'
        f'{instance.tipo_documento.pk}/{filename}'
    )


class Documento(models.Model):
    """
    Documento individual dentro del expediente.
    Cada documento tiene su propio estado y puede ser validado por
    División de Estudios y Servicios Escolares de forma independiente.
    """
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Expediente'
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT,
        verbose_name='Tipo de documento'
    )
    archivo = models.FileField(
        upload_to=upload_documento_path,
        null=True, blank=True,
        verbose_name='Archivo'
    )
    estado = models.CharField(
        max_length=25,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.PENDIENTE,
        verbose_name='Estado'
    )
    version = models.PositiveIntegerField(default=1, verbose_name='Versión')
    fecha_carga = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de carga')
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    notas_alumno = models.TextField(blank=True, verbose_name='Notas del alumno')
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='documentos_revisados',
        verbose_name='Revisado por'
    )
    observaciones_revision = models.TextField(blank=True, verbose_name='Observaciones de revisión')
    fecha_revision = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de revisión')

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['tipo_documento__orden']

    def __str__(self):
        return f'{self.tipo_documento.nombre} — {self.expediente.alumno.get_full_name()}'

    def get_estado_color(self):
        colores = {
            EstadoDocumento.PENDIENTE: 'secondary',
            EstadoDocumento.CARGADO: 'info',
            EstadoDocumento.EN_REVISION: 'warning',
            EstadoDocumento.APROBADO: 'success',
            EstadoDocumento.RECHAZADO: 'danger',
            EstadoDocumento.REQUIERE_CORRECCION: 'warning',
        }
        return colores.get(self.estado, 'secondary')

    @property
    def validacion_oficina(self):
        try:
            return self.validacion
        except ValidacionDocumento.DoesNotExist:
            return None

    def puede_revisar_oficina(self):
        return self.archivo and self.estado != EstadoDocumento.APROBADO


class ValidacionDocumento(models.Model):
    """
    Registro único de validación de un documento por Oficina de Titulación.
    """
    documento = models.OneToOneField(
        Documento, on_delete=models.CASCADE,
        related_name='validacion',
        verbose_name='Documento'
    )
    departamento = models.CharField(
        max_length=15,
        default='OFICINA',
        verbose_name='Departamento validador (legado)'
    )
    estado = models.CharField(
        max_length=25,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.PENDIENTE,
        verbose_name='Estado de validación'
    )
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='validaciones_realizadas',
        verbose_name='Validado por'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones / Motivo de rechazo'
    )
    fecha = models.DateTimeField(auto_now=True, verbose_name='Fecha de última acción')
    fecha_primera_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Validación de Documento'
        verbose_name_plural = 'Validaciones de Documentos'

    def __str__(self):
        return f'Validación — {self.documento} — {self.get_estado_display()}'


# ─────────────────────────────────────────────────────────────
# CITAS FÍSICAS Y LOTES
# ─────────────────────────────────────────────────────────────

class LoteCitacion(models.Model):
    criterio = models.CharField(max_length=200, verbose_name='Criterio del lote')
    tipo = models.CharField(
        max_length=30,
        choices=[('CERTIFICADO', 'Certificado'), ('OFICIO_PUBLICACION', 'Oficio publicación')],
        default='CERTIFICADO',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='lotes_citacion'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Lote de citación'
        verbose_name_plural = 'Lotes de citación'

    def __str__(self):
        return f'Lote {self.pk} — {self.criterio}'


class CitaDocumentoFisico(models.Model):
    class TipoCita(models.TextChoices):
        CERTIFICADO = 'CERTIFICADO', 'Certificado'
        OFICIO_PUBLICACION = 'OFICIO_PUBLICACION', 'Oficio de publicación'

    class EstadoCita(models.TextChoices):
        PROGRAMADA = 'PROGRAMADA', 'Programada'
        CONFIRMADA_ALUMNO = 'CONFIRMADA_ALUMNO', 'Confirmada por alumno'
        REPROGRAMACION_SOLICITADA = 'REPROGRAMACION_SOLICITADA', 'Reprogramación solicitada'
        COMPLETADA = 'COMPLETADA', 'Completada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='citas_fisicas',
        verbose_name='Expediente'
    )
    tipo = models.CharField(max_length=30, choices=TipoCita.choices)
    fecha_hora = models.DateTimeField(verbose_name='Fecha y hora')
    lugar = models.CharField(max_length=300, verbose_name='Lugar')
    estado = models.CharField(
        max_length=30, choices=EstadoCita.choices,
        default=EstadoCita.PROGRAMADA
    )
    notas = models.TextField(blank=True)
    propuesta_alumno_fecha = models.DateTimeField(null=True, blank=True)
    propuesta_alumno_notas = models.TextField(blank=True)
    lote = models.ForeignKey(
        LoteCitacion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='citas'
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='citas_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cita documento físico'
        verbose_name_plural = 'Citas documentos físicos'
        ordering = ['fecha_hora']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.expediente}'


class ReferenciaPago(models.Model):
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='referencias_pago'
    )
    folio = models.CharField(max_length=50, unique=True)
    referencia_bancaria = models.CharField(
        max_length=30, blank=True,
        verbose_name='Referencia alfanumérica bancaria',
    )
    concepto = models.CharField(
        max_length=200,
        default='TRÁMITE DE TITULACIÓN NIVEL LICENCIATURA',
        verbose_name='Concepto de pago',
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    vigencia = models.DateField(null=True, blank=True)
    pdf_referencia = models.FileField(upload_to='referencias_pago/%Y/', null=True, blank=True)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='referencias_generadas'
    )
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Referencia de pago'
        ordering = ['-fecha_generacion']

    def __str__(self):
        return self.referencia_bancaria or f'Ref. {self.folio}'


class ConfirmacionAdeudo(models.Model):
    class Area(models.TextChoices):
        FINANZAS = 'FINANZAS', 'Finanzas'
        CENTRO_COMPUTO = 'CENTRO_COMPUTO', 'Centro de Cómputo'
        CENTRO_INFORMACION = 'CENTRO_INFORMACION', 'Centro de Información'

    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='confirmaciones_adeudo'
    )
    area = models.CharField(max_length=20, choices=Area.choices)
    sin_adeudos = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='adeudos_confirmados'
    )
    fecha = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Confirmación de adeudo'
        unique_together = [['expediente', 'area']]

    def __str__(self):
        estado = 'Sin adeudos' if self.sin_adeudos else 'Con adeudos'
        return f'{self.expediente} — {self.get_area_display()} — {estado}'


class GrupoProtocolo(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre del grupo')
    criterio = models.CharField(max_length=300, blank=True, verbose_name='Criterio')
    fecha = models.DateField(verbose_name='Fecha del acto')
    hora_inicio = models.TimeField(verbose_name='Hora de inicio')
    lugar = models.CharField(max_length=300, verbose_name='Lugar')
    es_egel = models.BooleanField(default=False, verbose_name='¿Es EGEL? (horarios escalonados)')
    intervalo_minutos = models.PositiveIntegerField(default=30, verbose_name='Intervalo entre alumnos (min)')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='grupos_protocolo'
    )

    class Meta:
        verbose_name = 'Grupo de protocolo'
        ordering = ['-fecha']

    def __str__(self):
        return self.nombre


# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# RECEPCIÓN DE EMPASTADO
# ─────────────────────────────────────────────────────────────

class RecepcionEmpastado(models.Model):
    """
    Registro de la recepción física del trabajo empastado por División de Estudios.
    El alumno entrega físicamente; el sistema registra la recepción.
    """
    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='empastado',
        verbose_name='Expediente'
    )
    fecha_recepcion = models.DateField(verbose_name='Fecha de recepción')
    recibido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='empastados_recibidos',
        verbose_name='Recibido por'
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ('REVISADO', 'Revisado y Aceptado'),
            ('OBSERVACIONES', 'Con Observaciones'),
            ('RECHAZADO', 'Rechazado'),
        ],
        default='REVISADO',
        verbose_name='Estado de revisión física'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Recepción de Empastado'
        verbose_name_plural = 'Recepciones de Empastado'

    def __str__(self):
        return f'Empastado — {self.expediente.alumno.get_full_name()} — {self.fecha_recepcion}'


# ─────────────────────────────────────────────────────────────
# JURADO Y ACTO PROTOCOLARIO
# ─────────────────────────────────────────────────────────────

class AsignacionJurado(models.Model):
    """
    Oficio de asignación del jurado para el acto protocolario.
    Los miembros del jurado son instancias de Profesor (catálogo institucional).
    """
    from administracion.models import Profesor

    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='jurado',
        verbose_name='Expediente'
    )
    # ── Miembros del jurado ──────────────────────────────────────
    presidente = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        related_name='jurado_presidente',
        verbose_name='Presidente del jurado'
    )
    secretario = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        related_name='jurado_secretario',
        verbose_name='Secretario/a del jurado'
    )
    vocal_propietario = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='jurado_vocal_prop',
        verbose_name='Vocal Propietario/a'
    )
    vocal_suplente = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='jurado_vocal_sup',
        verbose_name='Vocal Suplente'
    )
    # ── Datos del oficio ─────────────────────────────────────────
    numero_oficio = models.CharField(
        max_length=50, blank=True,
        verbose_name='Número de oficio',
        help_text='Ej: S.C./OPV/0099/2026'
    )
    fecha_oficio = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha del oficio'
    )
    oficio_pdf = models.FileField(
        upload_to='oficios_jurado/',
        null=True, blank=True,
        verbose_name='PDF del Oficio de Jurado'
    )
    # ── Acto protocolario ────────────────────────────────────────
    fecha_acto = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha y hora del acto protocolario'
    )
    lugar_acto = models.CharField(
        max_length=300, blank=True,
        verbose_name='Lugar del acto',
        help_text='Ej: SALA MAGNA (edificio T)'
    )
    # ── Auditoría ────────────────────────────────────────────────
    asignado_por = models.ForeignKey(
        'administracion.Usuario',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jurados_asignados'
    )
    solicitud_jefe_usada = models.ForeignKey(
        'administracion.SolicitudCambioJefe',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asignaciones_jurado',
        verbose_name='Solicitud de Jefe Usada'
    )

    class Meta:
        verbose_name = 'Asignación de Jurado'
        verbose_name_plural = 'Asignaciones de Jurado'

    def __str__(self):
        return f'Jurado — {self.expediente.alumno.get_full_name()}'


class ActoProtocolario(models.Model):
    """
    Fecha y datos del acto protocolario / examen profesional.
    """
    RESULTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),

        ('SUSPENDIDO', 'Suspendido'),
        ('NO_PRESENTADO', 'No se presentó'),
    ]

    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='acto_protocolario',
        verbose_name='Expediente'
    )
    grupo = models.ForeignKey(
        GrupoProtocolo, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='actos',
        verbose_name='Grupo de protocolo'
    )
    hora_escalonada = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Hora escalonada (EGEL)'
    )
    jurado = models.ForeignKey(
        AsignacionJurado, on_delete=models.PROTECT,
        verbose_name='Jurado asignado'
    )
    fecha_acto = models.DateTimeField(verbose_name='Fecha y hora del acto')
    lugar = models.CharField(max_length=300, verbose_name='Lugar / Sala')
    resultado = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
        default='PENDIENTE',
        verbose_name='Resultado'
    )
    calificacion = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        verbose_name='Calificación (si aplica)'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    programado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='actos_programados',
        verbose_name='Programado por'
    )

    class Meta:
        verbose_name = 'Acto Protocolario'
        verbose_name_plural = 'Actos Protocolarios'
        ordering = ['fecha_acto']

    def __str__(self):
        return f'Acto — {self.expediente.alumno.get_full_name()} — {self.fecha_acto}'

    def confirmaciones_completas(self):
        """
        Verifica si todas las confirmaciones necesarias están completas.
        Requiere: presidente, secretario, vocal (propietario O suplente), alumno.
        """
        confirmaciones = {c.rol: c.confirmado for c in self.confirmaciones.all()}
        presidente_ok = confirmaciones.get('PRESIDENTE', False)
        secretario_ok = confirmaciones.get('SECRETARIO', False)
        alumno_ok = confirmaciones.get('ALUMNO', False)
        vocal_prop_ok = confirmaciones.get('VOCAL_PROPIETARIO', False)
        vocal_sup_ok = confirmaciones.get('VOCAL_SUPLENTE', False)
        vocal_ok = vocal_prop_ok or vocal_sup_ok
        return all([presidente_ok, secretario_ok, vocal_ok, alumno_ok])

    def get_vocal_confirmado(self):
        """Retorna quién confirma como vocal: propietario o suplente."""
        for c in self.confirmaciones.filter(rol__in=['VOCAL_PROPIETARIO', 'VOCAL_SUPLENTE']):
            if c.confirmado:
                return c
        return None

    def resumen_confirmaciones(self):
        """Retorna dict con estado de cada confirmación."""
        confirmaciones = {c.rol: c for c in self.confirmaciones.all()}
        return confirmaciones


class ConfirmacionActo(models.Model):
    """
    Confirmación de asistencia de cada participante del acto protocolario.
    """
    ROL_CHOICES = [
        ('PRESIDENTE', 'Presidente'),
        ('SECRETARIO', 'Secretario/a'),
        ('VOCAL_PROPIETARIO', 'Vocal Propietario/a'),
        ('VOCAL_SUPLENTE', 'Vocal Suplente'),
        ('ALUMNO', 'Alumno/a'),
    ]

    acto = models.ForeignKey(
        ActoProtocolario, on_delete=models.CASCADE,
        related_name='confirmaciones',
        verbose_name='Acto Protocolario'
    )
    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        verbose_name='Rol en el jurado'
    )
    nombre_participante = models.CharField(
        max_length=300,
        verbose_name='Nombre del participante'
    )
    email = models.EmailField(verbose_name='Correo electrónico')
    token = models.CharField(
        max_length=64, unique=True,
        verbose_name='Token de confirmación'
    )
    confirmado = models.BooleanField(default=False, verbose_name='¿Confirmado?')
    fecha_confirmacion = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de confirmación'
    )
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de envío')

    class Meta:
        verbose_name = 'Confirmación de Asistencia'
        verbose_name_plural = 'Confirmaciones de Asistencia'
        unique_together = [['acto', 'rol']]

    def __str__(self):
        estado = '✓' if self.confirmado else '✗'
        return f'{estado} {self.get_rol_display()} — {self.nombre_participante}'


# ─────────────────────────────────────────────────────────────
# HISTORIAL (AUDITORÍA)
# ─────────────────────────────────────────────────────────────

class HistorialExpediente(models.Model):
    """
    Registro inmutable de todos los cambios de estado del expediente.
    Proporciona auditoría completa del proceso.
    """
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Expediente'
    )
    estado_anterior = models.CharField(max_length=40, blank=True, verbose_name='Estado anterior')
    estado_nuevo = models.CharField(max_length=40, verbose_name='Estado nuevo')
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='cambios_realizados',
        verbose_name='Realizado por'
    )
    descripcion = models.TextField(verbose_name='Descripción del cambio')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')

    class Meta:
        verbose_name = 'Historial del Expediente'
        verbose_name_plural = 'Historial de Expedientes'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.expediente} → {self.estado_nuevo} ({self.fecha})'

    def get_estado_nuevo_display(self):
        return dict(EstadoExpediente.choices).get(self.estado_nuevo, self.estado_nuevo)

    def get_estado_anterior_display(self):
        return dict(EstadoExpediente.choices).get(self.estado_anterior, self.estado_anterior)

    def get_estado_nuevo_color(self):
        """Color for timeline badges."""
        return COLORES_ESTADO.get(self.estado_nuevo, 'secondary')


class HistorialDocumento(models.Model):
    """Auditoría de cambios en documentos individuales."""
    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Documento'
    )
    accion = models.CharField(max_length=100, verbose_name='Acción realizada')
    departamento = models.CharField(max_length=15, blank=True, verbose_name='Departamento')
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='historial_documentos',
        verbose_name='Realizado por'
    )
    observaciones = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historial de Documento'
        verbose_name_plural = 'Historial de Documentos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.documento} — {self.accion}'
