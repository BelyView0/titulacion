"""
Formularios del módulo de Administración.
"""
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from .models import Usuario, Carrera, Departamento, Rol, ConfiguracionInstitucional, JefeDepartamento


class UsuarioCreateForm(forms.ModelForm):
    """Formulario para crear un nuevo usuario. Todos los campos son obligatorios."""
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        min_length=8,
        help_text='Mínimo 8 caracteres.'
    )
    password_confirm = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Usuario
        fields = [
            'email', 'correo_institucional', 'correo_institucional_verificado', 'rol', 'carrera', 'departamento',
            'numero_control', 'telefono', 'genero', 'generacion',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos siempre obligatorios
        for f in ['first_name', 'last_name', 'apellido_materno',
                  'correo_institucional', 'rol', 'telefono', 'numero_control']:
            self.fields[f].required = True

        # carrera y departamento: opcionales en el form, la validación se hace en clean()
        self.fields['carrera'].required = False
        self.fields['departamento'].required = False
        self.fields['generacion'].required = False
        self.fields['genero'].required = False
        self.fields['email'].required = False
        if 'correo_institucional_verificado' in self.fields:
            self.fields['correo_institucional_verificado'].required = True

        # Valor por defecto de generación: año actual - 4.5 años
        self.fields['generacion'].initial = int(datetime.now().year - 4.5)

        # Labels claros
        self.fields['first_name'].label = 'Nombre(s)'
        self.fields['last_name'].label = 'Apellido paterno'
        self.fields['apellido_materno'].label = 'Apellido materno'
        self.fields['carrera'].label = 'Carrera'
        self.fields['departamento'].label = 'Departamento'


    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        rol = cleaned_data.get('rol')
        carrera = cleaned_data.get('carrera')
        departamento = cleaned_data.get('departamento')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Las contraseñas no coinciden.')

        # Validación condicional por rol
        if rol == Rol.ALUMNO and not carrera:
            self.add_error('carrera', 'La carrera es obligatoria para los alumnos.')
        if rol == Rol.JEFE_PROYECTO and not departamento:
            self.add_error('departamento', 'El departamento es obligatorio para los Jefes de Proyecto.')

        correo_institucional = cleaned_data.get('correo_institucional')
        if correo_institucional:
            config = ConfiguracionInstitucional.objects.first()
            dominio = config.dominio_institucional if config else 'apizaco.tecnm.mx'
            if not correo_institucional.endswith(f'@{dominio}'):
                self.add_error('correo_institucional', f'El correo institucional debe terminar en @{dominio}')

        return cleaned_data


class UsuarioUpdateForm(forms.ModelForm):
    """Formulario para editar un usuario existente."""

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'apellido_materno',
            'email', 'correo_institucional', 'correo_institucional_verificado', 'rol', 'carrera', 'departamento',
            'numero_control', 'telefono', 'genero', 'generacion', 'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for f in ['first_name', 'last_name', 'apellido_materno',
                  'correo_institucional', 'rol', 'telefono', 'numero_control']:
            self.fields[f].required = True

        self.fields['carrera'].required = False
        self.fields['departamento'].required = False
        self.fields['generacion'].required = False
        self.fields['genero'].required = False
        self.fields['email'].required = False
        
        if 'correo_institucional_verificado' in self.fields:
            self.fields['correo_institucional_verificado'].required = True

        self.fields['first_name'].label = 'Nombre(s)'
        self.fields['last_name'].label = 'Apellido paterno'
        self.fields['apellido_materno'].label = 'Apellido materno'
        self.fields['carrera'].label = 'Carrera'
        self.fields['departamento'].label = 'Departamento'

    def clean(self):
        cleaned_data = super().clean()
        rol = cleaned_data.get('rol')
        carrera = cleaned_data.get('carrera')
        departamento = cleaned_data.get('departamento')

        if rol == Rol.ALUMNO and not carrera:
            self.add_error('carrera', 'La carrera es obligatoria para los alumnos.')
        if rol == Rol.JEFE_PROYECTO and not departamento:
            self.add_error('departamento', 'El departamento es obligatorio para los Jefes de Proyecto.')

        correo_institucional = cleaned_data.get('correo_institucional')
        if correo_institucional:
            config = ConfiguracionInstitucional.objects.first()
            dominio = config.dominio_institucional if config else 'apizaco.tecnm.mx'
            if not correo_institucional.endswith(f'@{dominio}'):
                self.add_error('correo_institucional', f'El correo institucional debe terminar en @{dominio}')

        return cleaned_data


class ConfiguracionInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionInstitucional
        fields = ['dominio_institucional', 'imagen_encabezado', 'imagen_pie_pagina']
        widgets = {
            'dominio_institucional': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: apizaco.tecnm.mx'}),
            'imagen_encabezado': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'imagen_pie_pagina': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class ConfiguracionEmailForm(forms.ModelForm):
    """Formulario para configurar el servidor SMTP y credenciales de correo."""
    class Meta:
        model = ConfiguracionInstitucional
        fields = ['email_host', 'email_port', 'email_use_tls', 'email_remitente', 'email_password']
        widgets = {
            'email_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: smtp.gmail.com'}),
            'email_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_remitente': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ej: mi_cuenta@gmail.com'}),
            'email_password': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña de aplicación de 16 caracteres'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.email_password:
            self.initial['email_password'] = '********'

    def clean_email_password(self):
        pwd = self.cleaned_data.get('email_password')
        if pwd and pwd != '********':
            # Removemos los espacios por si el usuario la pega con el formato "xxxx xxxx xxxx xxxx"
            pwd = pwd.replace(' ', '')
        return pwd

    def save(self, commit=True):
        from administracion.crypto import encrypt
        instance = super().save(commit=False)
        pwd = self.cleaned_data.get('email_password')
        
        if pwd and pwd != '********':
            instance.email_password = encrypt(pwd)
        elif pwd == '********':
            # No modificar la contraseña original si no cambió el valor oculto
            pass
            
        if commit:
            instance.save()
        return instance


class JefeDepartamentoForm(forms.ModelForm):
    class Meta:
        model = JefeDepartamento
        fields = ['departamento', 'titulo_academico', 'nombre', 'apellido_paterno', 'apellido_materno', 'genero']
        widgets = {
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'titulo_academico': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ing., M.C., Dra.'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido_paterno': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido_materno': forms.TextInput(attrs={'class': 'form-control'}),
            'genero': forms.Select(attrs={'class': 'form-select'}),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FORMULARIOS PARA EDICIÓN DE DATOS RELACIONADOS (vista de edición de usuario)
# ═══════════════════════════════════════════════════════════════════════════════

class PerfilAlumnoAdminForm(forms.ModelForm):
    """Formulario para editar el perfil académico del alumno desde el admin."""

    class Meta:
        from alumnos.models import PerfilAlumno
        model = PerfilAlumno
        fields = ['plan_estudios', 'semestre_egreso', 'promedio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plan_estudios'].required = False
        self.fields['semestre_egreso'].required = False
        self.fields['promedio'].required = False


class ExpedienteAdminForm(forms.ModelForm):
    """Formulario para editar campos del expediente desde el admin."""

    class Meta:
        from expediente.models import Expediente
        model = Expediente
        fields = [
            'estado', 'modalidad', 'titulo_trabajo', 'nombre_empresa',
            'pago_validado', 'pago_observaciones',
            'foto_fisica_division', 'foto_fisica_escolares',
            'observaciones_division', 'observaciones_cedula',
            'fecha_cita_entrega', 'instrucciones_cita',
        ]
        widgets = {
            'pago_observaciones': forms.Textarea(attrs={'rows': 2}),
            'observaciones_division': forms.Textarea(attrs={'rows': 2}),
            'observaciones_cedula': forms.Textarea(attrs={'rows': 2}),
            'instrucciones_cita': forms.Textarea(attrs={'rows': 2}),
            'fecha_cita_entrega': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo estado es requerido
        for name in self.fields:
            if name != 'estado':
                self.fields[name].required = False


class UsuarioPerfilBasicoForm(forms.ModelForm):
    """
    Formulario para la edición del perfil de usuario (mis datos).
    Maneja la edición de correos, teléfono y foto de perfil.
    """
    class Meta:
        model = Usuario
        fields = ['email', 'correo_institucional', 'telefono', 'foto_perfil']
        widgets = {
            'foto_perfil': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Correo Personal'
        self.fields['correo_institucional'].label = 'Correo Institucional'
        self.fields['telefono'].label = 'Teléfono'
        
        # Si ya tiene correo institucional, es de solo lectura (según la regla de negocio)
        if self.instance and self.instance.correo_institucional:
            self.fields['correo_institucional'].widget.attrs['readonly'] = True
            self.fields['correo_institucional'].help_text = 'No puedes modificar tu correo institucional una vez asignado. Contacta a Soporte/Admin en caso de error.'
        else:
            config = ConfiguracionInstitucional.objects.first()
            dominio = config.dominio_institucional if config else 'apizaco.tecnm.mx'
            self.fields['correo_institucional'].help_text = f'Debe terminar en @{dominio}'

    def clean(self):
        cleaned_data = super().clean()
        correo_institucional = cleaned_data.get('correo_institucional')
        
        # Validación de solo lectura
        if self.instance and self.instance.correo_institucional and correo_institucional != self.instance.correo_institucional:
            self.add_error('correo_institucional', 'No puedes modificar el correo institucional una vez asignado.')

        if correo_institucional and (not self.instance or not self.instance.correo_institucional):
            config = ConfiguracionInstitucional.objects.first()
            dominio = config.dominio_institucional if config else 'apizaco.tecnm.mx'
            if not correo_institucional.endswith(f'@{dominio}'):
                self.add_error('correo_institucional', f'El correo institucional debe terminar en @{dominio}')

        return cleaned_data


class ReprogramarActoForm(forms.Form):
    reasignar_jurado = forms.BooleanField(
        label='¿Reasignar Jurado?',
        required=False,
        help_text='Activa esta opción si necesitas modificar los integrantes del jurado. Esto cancelará la programación actual y te regresará al paso de asignación de jurado.'
    )
    fecha_acto = forms.DateTimeField(
        label='Nueva Fecha y Hora',
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    lugar = forms.CharField(
        label='Nuevo Lugar',
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Especifique el lugar...'})
    )
    motivo_reprogramacion = forms.CharField(
        label='Motivo de la Reprogramación',
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ej. No se completaron las confirmaciones de asistencia a tiempo.'}),
        initial='No se completaron las confirmaciones de asistencia a tiempo.'
    )

    def clean(self):
        cleaned_data = super().clean()
        reasignar = cleaned_data.get('reasignar_jurado')
        fecha_acto = cleaned_data.get('fecha_acto')
        lugar = cleaned_data.get('lugar')

        if not reasignar:
            if not fecha_acto:
                self.add_error('fecha_acto', 'Debes especificar una nueva fecha y hora si no vas a reasignar jurado.')
            else:
                from django.utils import timezone
                if fecha_acto <= timezone.now():
                    self.add_error('fecha_acto', 'La nueva fecha y hora debe ser posterior a la actual.')
            if not lugar:
                self.add_error('lugar', 'Debes especificar el nuevo lugar si no vas a reasignar jurado.')

        return cleaned_data
