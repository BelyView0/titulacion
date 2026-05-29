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
            'email', 'correo_institucional', 'rol', 'carrera', 'departamento',
            'numero_control', 'telefono', 'genero', 'generacion',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos siempre obligatorios
        for f in ['username', 'first_name', 'last_name', 'apellido_materno',
                  'email', 'rol', 'telefono', 'numero_control']:
            self.fields[f].required = True

        # carrera y departamento: opcionales en el form, la validación se hace en clean()
        self.fields['carrera'].required = False
        self.fields['departamento'].required = False
        self.fields['generacion'].required = False
        self.fields['genero'].required = False
        self.fields['correo_institucional'].required = False

        # Valor por defecto de generación: año actual - 4.5 años
        self.fields['generacion'].initial = int(datetime.now().year - 4.5)

        # Labels claros
        self.fields['first_name'].label = 'Nombre(s)'
        self.fields['last_name'].label = 'Apellido paterno'
        self.fields['apellido_materno'].label = 'Apellido materno'
        self.fields['username'].label = 'Nombre de usuario'
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
            'email', 'correo_institucional', 'rol', 'carrera', 'departamento',
            'numero_control', 'telefono', 'genero', 'generacion', 'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['first_name', 'last_name', 'apellido_materno', 'email', 'rol',
                  'telefono', 'numero_control']:
            self.fields[f].required = True

        self.fields['carrera'].required = False
        self.fields['departamento'].required = False
        self.fields['generacion'].required = False
        self.fields['genero'].required = False
        self.fields['correo_institucional'].required = False

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
