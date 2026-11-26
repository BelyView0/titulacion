"""Verificación de configuración inicial SIGET para el panel de administración."""
from django.urls import reverse

from administracion.models import (
    ConfiguracionInstitucional,
    Departamento,
    Carrera,
    Usuario,
    JefeDepartamento,
    roles_oficina_titulacion,
    roles_jefe_academia,
)
from expediente.models import PlanEstudios, Modalidad, TipoDocumento
from titulacion.db_config import load_database_config


SETUP_ALLOWED_URL_NAMES = [
    'logout',
    'perfil',
    'perfil_verificar_enviar',
    'perfil_verificar_validar',
    'perfil_solicitar_correccion_control',
    'forzar_cambio_password',
    'administracion:dashboard',
    'administracion:configuracion',
    'administracion:configuracion_email',
    'administracion:configuracion_email_probar',
    'administracion:configuracion_email_revelar',
    'administracion:configuracion_database',
    'administracion:configuracion_completar',
    'administracion:configuracion_inicial',
]

SETUP_PATH_PREFIXES = [
    '/admin-sistema/configuracion',
    '/admin-sistema/departamentos',
    '/admin-sistema/planes',
    '/admin-sistema/modalidades',
    '/admin-sistema/documentos',
    '/admin-sistema/carreras',
    '/admin-sistema/usuarios',
    '/admin-sistema/jefes',
]


def ruta_permitida_durante_setup(path, allowed_paths):
    if path in ('/admin-sistema/', '/admin-sistema'):
        return True
    if path in allowed_paths:
        return True
    return any(path.startswith(prefix) for prefix in SETUP_PATH_PREFIXES)


def _paso(titulo, ok, url_name, descripcion='', accion='Configurar', critico=True):
    try:
        url = reverse(url_name)
    except Exception:
        url = '#'
    return {
        'titulo': titulo,
        'ok': ok,
        'url': url,
        'descripcion': descripcion,
        'accion': accion,
        'critico': critico,
        'tipo': 'success' if ok else ('danger' if critico else 'warning'),
        'icono': 'bi-check-circle-fill' if ok else 'bi-exclamation-circle-fill',
    }


def get_pasos_configuracion():
    config = ConfiguracionInstitucional.objects.first()
    datos_institucionales = bool(
        config
        and config.nombre_institucion
        and config.siglas
    )

    pasos = [
        _paso(
            'Base de datos',
            bool(load_database_config()),
            'administracion:configuracion_database',
            'Conexión a la base de datos del sistema.',
            'Configurar BD',
        ),
        _paso(
            'Servidor de correos (SMTP)',
            bool(config and config.smtp_listo()),
            'administracion:configuracion_email',
            'Credenciales para enviar notificaciones y códigos de verificación.',
            'Configurar SMTP',
        ),
        _paso(
            'Datos institucionales (nombre, siglas, branding)',
            datos_institucionales,
            'administracion:configuracion',
            'Nombre del plantel, siglas y logos del encabezado institucional.',
            'Configurar datos',
        ),
        _paso(
            'Departamentos',
            Departamento.objects.exists(),
            'administracion:departamentos',
            'Departamentos académicos para asignar jefes de proyecto.',
            'Gestionar departamentos',
            critico=False,
        ),
        _paso(
            'Planes de estudios y modalidades',
            PlanEstudios.objects.filter(activo=True).exists()
            and Modalidad.objects.filter(activa=True).exists(),
            'administracion:planes',
            'Al menos un plan de estudios activo y una modalidad de titulación.',
            'Configurar catálogos',
        ),
        _paso(
            'Tipos de documento por modalidad',
            TipoDocumento.objects.exists(),
            'administracion:documentos',
            'Documentos requeridos según la modalidad de titulación.',
            'Configurar documentos',
        ),
        _paso(
            'Carreras',
            Carrera.objects.filter(activa=True).exists(),
            'administracion:carreras',
            'Carreras activas para registrar alumnos y expedientes.',
            'Gestionar carreras',
            critico=False,
        ),
    ]

    roles_criticos = [
        (
            roles_oficina_titulacion(),
            'Oficina de Titulación',
            'Usuarios que antes eran Escolares o División. Validan expedientes y documentos.',
        ),
        (
            roles_jefe_academia(),
            'Jefe de Academia',
            'Usuario que antes era Jefe de Proyectos. Gestiona jurados y actos protocolarios.',
        ),
    ]
    for roles, rol_nombre, descripcion in roles_criticos:
        pasos.append(_paso(
            f'Usuario: {rol_nombre}',
            Usuario.objects.filter(rol__in=roles, is_active=True).exists(),
            'administracion:usuario_crear',
            descripcion,
            'Crear usuario',
        ))

    return pasos


def evaluar_configuracion_sistema():
    pasos = get_pasos_configuracion()
    completos = sum(1 for p in pasos if p['ok'])
    total = len(pasos)
    progreso = int(completos / total * 100) if total else 100
    pendientes = [p for p in pasos if not p['ok']]
    return {
        'pasos': pasos,
        'progreso': progreso,
        'pendiente': bool(pendientes),
        'pendientes': pendientes,
        'total': total,
        'completos': completos,
    }


def sincronizar_sistema_configurado():
    """Marca el sistema como listo cuando todos los pasos obligatorios están completos."""
    evaluacion = evaluar_configuracion_sistema()
    config = ConfiguracionInstitucional.objects.first()
    if not config:
        return evaluacion
    if not evaluacion['pendiente'] and not config.sistema_configurado:
        config.sistema_configurado = True
        config.save(update_fields=['sistema_configurado'])
    elif evaluacion['pendiente'] and config.sistema_configurado:
        config.sistema_configurado = False
        config.save(update_fields=['sistema_configurado'])
    return evaluacion


def get_alertas_informativas():
    """Alertas no bloqueantes para el dashboard operativo."""
    alertas = []
    if Departamento.objects.exists() and not JefeDepartamento.objects.exists():
        alertas.append({
            'tipo': 'info',
            'icono': 'bi-person-badge',
            'titulo': 'Sin jefes de departamento asignados',
            'mensaje': 'Registre jefes de departamento para firmar oficios de asignación de jurado.',
            'accion_url': reverse('administracion:jefe_crear'),
            'accion_texto': 'Asignar jefe',
        })
    return alertas
