from rest_framework import serializers

from administracion.models import Usuario
from alumnos.models import PerfilAlumno, Notificacion
from expediente.models import Expediente, Documento



class PerfilAlumnoSerializer(serializers.ModelSerializer):
    """
    Serializer para consultar y actualizar el perfil del alumno.
    Utiliza los campos existentes del modelo Usuario.
    """

    nombre = serializers.CharField(
        source='get_full_name',
        read_only=True
    )

    numero_control = serializers.CharField(
        read_only=True
    )

    carrera = serializers.SerializerMethodField()
    genero = serializers.SerializerMethodField()
    periodo_inicio = serializers.SerializerMethodField()
    periodo_egreso = serializers.SerializerMethodField()

    class Meta:
        model = Usuario

        fields = [
            'id',
            'nombre',
            'first_name',
            'last_name',
            'apellido_materno',
            'numero_control',
            'carrera',
            'telefono',
            'genero',
            'periodo_inicio',
            'periodo_egreso',
            'semestres_cursados',
            'email',
            'email_verificado',
            'correo_institucional',
            'correo_institucional_verificado',
            'foto_perfil',
        ]

        read_only_fields = [
            'id',
            'nombre',
            'numero_control',
            'carrera',
            'genero',
            'periodo_inicio',
            'periodo_egreso',
            'semestres_cursados',
            'email_verificado',
            'correo_institucional',
            'correo_institucional_verificado',
        ]

    def get_carrera(self, obj):
        if obj.carrera:
            return obj.carrera.nombre

        return None

    def get_genero(self, obj):
        if obj.genero:
            return obj.get_genero_display()

        return None

    def get_periodo_inicio(self, obj):
        return obj.periodo_inicio_display

    def get_periodo_egreso(self, obj):
        return obj.periodo_egreso_display

    def update(self, instance, validated_data):
        old_email = instance.email

        if 'email' in validated_data:
            instance.email = validated_data['email']

        if 'telefono' in validated_data:
            instance.telefono = validated_data['telefono']

        if 'foto_perfil' in validated_data:
            instance.foto_perfil = validated_data['foto_perfil']

        if instance.email != old_email:
            instance.email_verificado = False

        instance.save()

        return instance



class NotificacionDashboardSerializer(serializers.ModelSerializer):
    """
    Serializer de las notificaciones que aparecen en el dashboard.
    """

    class Meta:
        model = Notificacion
        fields = [
            'id',
            'tipo',
            'titulo',
            'mensaje',
            'leida',
            'fecha',
            'url_relacionada',
        ]


class DashboardAlumnoSerializer(serializers.Serializer):
    """
    Serializer del dashboard del alumno.
    """

    alumno = PerfilAlumnoSerializer(read_only=True)

    expediente = serializers.SerializerMethodField()

    notificaciones_no_leidas = serializers.IntegerField(
        read_only=True
    )

    notificaciones_recientes = NotificacionDashboardSerializer(
        many=True,
        read_only=True
    )

    def get_expediente(self, usuario):
        """
        Obtiene la información principal del expediente
        perteneciente al alumno autenticado.
        """

        try:
            expediente = usuario.expediente
        except Expediente.DoesNotExist:
            return None

        return {
            'id': expediente.id,
            'estado': expediente.estado,
            'estado_display': expediente.get_estado_display(),
            'modalidad': (
                expediente.modalidad.nombre
                if expediente.modalidad
                else None
            ),
            'titulo_trabajo': expediente.titulo_trabajo,
            'nombre_empresa': expediente.nombre_empresa,
        }
        
        
class DocumentoAlumnoSerializer(serializers.ModelSerializer):
    """
    Información de los documentos del expediente del alumno.
    """

    tipo_documento = serializers.SerializerMethodField()
    estado_display = serializers.CharField(
        source='get_estado_display',
        read_only=True
    )
    archivo = serializers.SerializerMethodField()
    validacion_oficina = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            'id',
            'tipo_documento',
            'archivo',
            'estado',
            'estado_display',
            'version',
            'fecha_carga',
            'fecha_actualizacion',
            'notas_alumno',
            'observaciones_revision',
            'fecha_revision',
            'validacion_oficina',
        ]

    def get_tipo_documento(self, obj):
        tipo = obj.tipo_documento

        return {
            'id': tipo.id,
            'nombre': tipo.nombre,
            'descripcion_ayuda': tipo.descripcion_ayuda,
            'es_obligatorio': tipo.es_obligatorio,
            'solo_mas_de_12_semestres': tipo.solo_mas_de_12_semestres,
            'orden': tipo.orden,
            'formatos_admitidos': tipo.formatos_admitidos,
            'tamano_max_mb': tipo.tamano_max_mb,
        }

    def get_archivo(self, obj):
        if not obj.archivo:
            return None

        request = self.context.get('request')
        url = obj.archivo.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_validacion_oficina(self, obj):
        validacion = obj.validacion_oficina

        if not validacion:
            return None

        return {
            'estado': validacion.estado,
            'estado_display': validacion.get_estado_display(),
            'observaciones': validacion.observaciones,
            'fecha': validacion.fecha,
        }
