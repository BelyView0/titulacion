from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Carrera, Departamento, ConfiguracionInstitucional


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'departamento', 'activa')
    search_fields = ('nombre', 'clave')
    list_filter = ('activa', 'departamento')


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'rol_responsable')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'rol', 'departamento', 'carrera', 'is_active')
    list_filter = ('rol', 'departamento', 'carrera', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del Sistema de Titulación', {
            'fields': ('rol', 'departamento', 'carrera', 'numero_control', 'telefono', 'foto_perfil')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos del Sistema', {
            'fields': ('rol', 'departamento', 'first_name', 'last_name', 'apellido_materno', 'email', 'carrera')
        }),
    )

@admin.register(ConfiguracionInstitucional)
class ConfiguracionInstitucionalAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'anio_en_curso')
    
    def has_add_permission(self, request):
        if ConfiguracionInstitucional.objects.exists():
            return False
        return super().has_add_permission(request)
