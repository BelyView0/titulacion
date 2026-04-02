from django.contrib import admin
from .models import (
    PlanEstudios, Modalidad, TipoDocumento,
    Expediente, Documento, ValidacionDocumento,
    EnvioCDMX, RecepcionEmpastado,
    AsignacionJurado, ActoProtocolario,
    HistorialExpediente, HistorialDocumento
)


@admin.register(PlanEstudios)
class PlanEstudiosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo')
    list_filter = ('activo',)


class TipoDocumentoInline(admin.TabularInline):
    model = TipoDocumento
    extra = 1
    fields = ('nombre', 'es_obligatorio', 'orden', 'valida_division', 'valida_escolares', 'es_fotografia')


@admin.register(Modalidad)
class ModalidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'clave', 'plan_estudios', 'activa')
    list_filter = ('plan_estudios', 'activa')
    inlines = [TipoDocumentoInline]


@admin.register(TipoDocumento)
class TipoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'modalidad', 'es_obligatorio', 'valida_division', 'valida_escolares', 'orden')
    list_filter = ('modalidad', 'es_obligatorio', 'valida_division', 'valida_escolares')
    ordering = ('modalidad', 'orden')


class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    fields = ('tipo_documento', 'estado', 'archivo', 'version')
    readonly_fields = ('version',)


class HistorialExpedienteInline(admin.TabularInline):
    model = HistorialExpediente
    extra = 0
    readonly_fields = ('estado_anterior', 'estado_nuevo', 'realizado_por', 'descripcion', 'fecha')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'modalidad', 'estado', 'fecha_apertura')
    list_filter = ('estado', 'modalidad__plan_estudios', 'modalidad')
    search_fields = ('alumno__first_name', 'alumno__last_name', 'alumno__username')
    readonly_fields = ('fecha_apertura', 'fecha_ultima_actualizacion')
    inlines = [DocumentoInline, HistorialExpedienteInline]


class ValidacionInline(admin.TabularInline):
    model = ValidacionDocumento
    extra = 0
    readonly_fields = ('fecha',)


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('tipo_documento', 'expediente', 'estado', 'version', 'fecha_carga')
    list_filter = ('estado',)
    inlines = [ValidacionInline]


@admin.register(EnvioCDMX)
class EnvioCDMXAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'numero_oficio', 'fecha_envio', 'estado', 'fecha_respuesta')
    list_filter = ('estado',)


@admin.register(RecepcionEmpastado)
class RecepcionEmpastadoAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'fecha_recepcion', 'recibido_por', 'estado')


@admin.register(AsignacionJurado)
class AsignacionJuradoAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'presidente', 'secretario', 'vocal', 'fecha_carta')


@admin.register(ActoProtocolario)
class ActoProtocolarioAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'fecha_acto', 'lugar', 'resultado')
    list_filter = ('resultado',)


@admin.register(HistorialExpediente)
class HistorialExpedienteAdmin(admin.ModelAdmin):
    list_display = ('expediente', 'estado_anterior', 'estado_nuevo', 'realizado_por', 'fecha')
    list_filter = ('estado_nuevo',)
    readonly_fields = ('expediente', 'estado_anterior', 'estado_nuevo', 'realizado_por', 'descripcion', 'fecha')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
