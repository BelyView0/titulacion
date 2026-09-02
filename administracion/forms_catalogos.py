from django import forms
from expediente.models import PlanEstudios, Modalidad, TipoDocumento
from expediente.constants import FORMATO_DOCUMENTO_CHOICES, DEFAULT_FORMATOS, DEFAULT_TAMANO_MAX_MB


class PlanEstudiosForm(forms.ModelForm):
    class Meta:
        model = PlanEstudios
        fields = ['nombre', 'descripcion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2024'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class ModalidadForm(forms.ModelForm):
    class Meta:
        model = Modalidad
        fields = ['plan_estudios', 'nombre', 'clave', 'descripcion', 'activa']
        widgets = {
            'plan_estudios': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'clave': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: RESIDENCIA'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }


class TipoDocumentoForm(forms.ModelForm):
    formatos = forms.MultipleChoiceField(
        choices=FORMATO_DOCUMENTO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Formatos admitidos',
        initial=DEFAULT_FORMATOS,
    )

    class Meta:
        model = TipoDocumento
        fields = [
            'modalidad', 'nombre', 'descripcion_ayuda', 'es_obligatorio',
            'formatos', 'tamano_max_mb',
        ]
        widgets = {
            'modalidad': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_ayuda': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'es_obligatorio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tamano_max_mb': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.formatos_admitidos:
            self.fields['formatos'].initial = self.instance.formatos_admitidos
        self.fields['tamano_max_mb'].initial = self.fields['tamano_max_mb'].initial or DEFAULT_TAMANO_MAX_MB

    def clean(self):
        cleaned = super().clean()
        formatos = cleaned.get('formatos')
        if not formatos:
            raise forms.ValidationError('Seleccione al menos un formato admitido.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.formatos_admitidos = self.cleaned_data.get('formatos', DEFAULT_FORMATOS)
        if not instance.pk:
            from django.db.models import Max
            max_orden = TipoDocumento.objects.filter(modalidad=instance.modalidad).aggregate(
                Max('orden')
            )['orden__max']
            instance.orden = (max_orden or 0) + 1
        if commit:
            instance.save()
        return instance
