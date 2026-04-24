"""
Formularios del módulo de Administración.
"""
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
            'username', 'first_name', 'last_name', 'apellido_materno',
            'email', 'rol', 'carrera', 'departamento',
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

        return cleaned_data


class UsuarioUpdateForm(forms.ModelForm):
    """Formulario para editar un usuario existente."""

    class Meta:
        model = Usuario
        fields = [
            'first_name', 'last_name', 'apellido_materno',
            'email', 'rol', 'carrera', 'departamento',
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

        return cleaned_data


class ConfiguracionInstitucionalForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionInstitucional
        fields = ['imagen_encabezado', 'imagen_pie_pagina']
        widgets = {
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
