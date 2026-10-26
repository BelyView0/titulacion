from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse


def service_worker(request):
    """Publica el service worker en la raíz del sitio para la PWA."""
    sw_path = Path(settings.BASE_DIR) / "static" / "sw.js"

    if not sw_path.is_file():
        raise Http404("Service worker no encontrado")

    response = HttpResponse(
        sw_path.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )

    # Permite que el service worker controle las rutas de todo el sitio.
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"

    return response
