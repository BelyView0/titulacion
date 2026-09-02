"""Formularios para configuración de base de datos."""
from django import forms


class DatabaseConfigForm(forms.Form):
    ENGINE_CHOICES = [
        ('sqlite', 'SQLite (desarrollo / instalación nueva)'),
        ('postgresql', 'PostgreSQL'),
    ]
    engine = forms.ChoiceField(choices=ENGINE_CHOICES, label='Motor de base de datos')
    name = forms.CharField(
        label='Nombre de BD / ruta SQLite',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    user = forms.CharField(
        label='Usuario', required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        label='Contraseña', required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
    )
    host = forms.CharField(
        label='Host', required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    port = forms.CharField(
        label='Puerto', required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def clean(self):
        data = super().clean()
        if data.get('engine') == 'postgresql':
            for field in ('name', 'user', 'host', 'port'):
                if not data.get(field):
                    self.add_error(field, 'Este campo es obligatorio para PostgreSQL.')
        return data
