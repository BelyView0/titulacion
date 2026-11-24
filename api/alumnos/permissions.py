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