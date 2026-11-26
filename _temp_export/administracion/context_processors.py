from .models import ConfiguracionInstitucional

def global_config(request):
    """
    Inyecta la configuración institucional global en todas las plantillas.
    Esto permite usar {{ institucion.nombre_institucion }}, colores, logo, etc.
    en base.html, login.html y otros.
    """
    try:
        config = ConfiguracionInstitucional.objects.first()
    except Exception:
        config = None

    return {
        'institucion': config
    }
