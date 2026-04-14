from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Carrera, Departamento


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'activa')
    search_fields = ('nombre', 'clave')
    list_filter = ('activa',)


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'rol_responsable')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'rol', 'carrera', 'is_active')
    list_filter = ('rol', 'carrera', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del Sistema de Titulación', {
            'fields': ('rol', 'numero_empleado', 'carrera', 'telefono', 'foto_perfil')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos del Sistema', {
            'fields': ('rol', 'first_name', 'last_name', 'email', 'carrera')
        }),
    )
