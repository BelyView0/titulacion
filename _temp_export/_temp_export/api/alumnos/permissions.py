from rest_framework.permissions import BasePermission


class IsAlumno(BasePermission):
    """
    Permite el acceso únicamente a usuarios con rol de alumno.
    """

    message = "Esta operación está disponible únicamente para alumnos."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.rol == "ALUMNO"
        )
        
class IsCorreoVerificado(BasePermission):
    """
    Permite acceder únicamente a alumnos que hayan verificado
    al menos uno de sus correos electrónicos.
    """

    message = (
        'Debes verificar tu correo personal o institucional '
        'para acceder a esta sección.'
    )

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not hasattr(user, 'requiere_verificacion_correo'):
            return False

        return not user.requiere_verificacion_correo()        