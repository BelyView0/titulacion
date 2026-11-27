from django.urls import path

from .views import (
    PerfilAlumnoView,
    DashboardAlumnoView,
    DocumentosAlumnoView,
    CargarDocumentoAlumnoView,
    EnviarVerificacionCorreoAPIView,
    ValidarVerificacionCorreoAPIView,
    SolicitarCorreccionControlAPIView,
)
from .expediente_api import (
    CatalogoExpedienteAPIView,
    ExpedienteCrearAPIView,
    ConfirmarAsistenciaAPIView,
    ExpedienteDetalleAPIView,
    EnviarDocumentosAPIView,
    HistorialExpedienteAPIView,
    SeguimientoAPIView,
)
from .expediente_etapas import (
    ConfirmarCitaAPIView,
    SolicitarReprogramacionCitaAPIView,
    SubirComprobantePagoAPIView,
    PrefichaPagoEnlaceAPIView,
    PrefichaPagoDescargaView,
    SubirActaExencionAPIView,
    DocumentosProtocoloEnlaceAPIView,
    DocumentosProtocoloDescargaView,
)

app_name = 'alumnos'

urlpatterns = [
    path(
        'perfil/',
        PerfilAlumnoView.as_view(),
        name='perfil'
    ),

    path(
        'perfil/verificar/<str:tipo>/enviar/',
        EnviarVerificacionCorreoAPIView.as_view(),
        name='enviar-verificacion-correo'
    ),

    path(
        'perfil/verificar/<str:tipo>/validar/',
        ValidarVerificacionCorreoAPIView.as_view(),
        name='validar-verificacion-correo'
    ),

    path(
        'dashboard/',
        DashboardAlumnoView.as_view(),
        name='dashboard'
    ),

    path(
        'documentos/',
        DocumentosAlumnoView.as_view(),
        name='documentos'
    ),

    path(
        'documentos/<int:pk>/cargar/',
        CargarDocumentoAlumnoView.as_view(),
        name='cargar-documento'
    ),
    
    path(
        'perfil/solicitar-correccion-control/',
        SolicitarCorreccionControlAPIView.as_view(),
        name='solicitar-correccion-control'
    ),
    
    path(
        'catalogos/expediente/',
        CatalogoExpedienteAPIView.as_view(),
        name='catalogo-expediente'
    ),

    path(
        'expediente/',
        ExpedienteDetalleAPIView.as_view(),
        name='expediente'
    ),

    path(
        'expediente/enviar-documentos/',
        EnviarDocumentosAPIView.as_view(),
        name='enviar-documentos'
    ),

    path(
        'expediente/crear/',
        ExpedienteCrearAPIView.as_view(),
        name='crear-expediente'
    ),

    path(
        'confirmar-asistencia/',
        ConfirmarAsistenciaAPIView.as_view(),
        name='confirmar-asistencia'
    ),
    
    path(
        'expediente/historial/',
        HistorialExpedienteAPIView.as_view(),
        name='historial-expediente'
    ),

    path(
        'seguimiento/',
        SeguimientoAPIView.as_view(),
        name='seguimiento'
    ),

    path(
        'citas/<int:pk>/confirmar/',
        ConfirmarCitaAPIView.as_view(),
        name='confirmar-cita'
    ),

    path(
        'citas/<int:pk>/reprogramar/',
        SolicitarReprogramacionCitaAPIView.as_view(),
        name='reprogramar-cita'
    ),

    path(
        'expediente/subir-pago/',
        SubirComprobantePagoAPIView.as_view(),
        name='subir-pago'
    ),

    path(
        'expediente/preficha-pago/',
        PrefichaPagoEnlaceAPIView.as_view(),
        name='preficha-enlace'
    ),

    path(
        'expediente/preficha-pago/descargar/<str:token>/',
        PrefichaPagoDescargaView.as_view(),
        name='preficha-descarga'
    ),

    path(
        'expediente/subir-acta-exencion/',
        SubirActaExencionAPIView.as_view(),
        name='subir-acta-exencion'
    ),

    path(
        'expediente/documentos-protocolo/',
        DocumentosProtocoloEnlaceAPIView.as_view(),
        name='protocolo-enlace'
    ),

    path(
        'expediente/documentos-protocolo/descargar/<str:token>/',
        DocumentosProtocoloDescargaView.as_view(),
        name='protocolo-descarga'
    ),
]