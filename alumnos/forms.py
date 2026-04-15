from django import forms
from expediente.models import Expediente, Modalidad

class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ['modalidad', 'titulo_trabajo', 'nombre_empresa']
        widgets = {
            'modalidad': forms.Select(attrs={'class': 'form-select'}),
            'titulo_trabajo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título de tu trabajo de titulación'}),
            'nombre_empresa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la empresa (si aplica)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar modalidades activas
        self.fields['modalidad'].queryset = Modalidad.objects.filter(activa=True).select_related('plan_estudios')
        # Hacer campos obligatorios
        self.fields['modalidad'].empty_label = "— Selecciona una modalidad —"
        self.fields['modalidad'].required = True
        self.fields['titulo_trabajo'].required = True
        self.fields['nombre_empresa'].required = True
