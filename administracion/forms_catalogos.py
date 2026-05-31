from django import forms
from expediente.models import PlanEstudios, Modalidad, TipoDocumento

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
    class Meta:
        model = TipoDocumento
        fields = [
            'modalidad', 'nombre', 'descripcion_ayuda', 'es_obligatorio',
            'valida_division', 'valida_escolares', 'acepta_solo_pdf', 'es_fotografia'
        ]
        widgets = {
            'modalidad': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_ayuda': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'es_obligatorio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'valida_division': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'valida_escolares': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'acepta_solo_pdf': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_fotografia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        valida_division = cleaned_data.get('valida_division')
        valida_escolares = cleaned_data.get('valida_escolares')
        acepta_solo_pdf = cleaned_data.get('acepta_solo_pdf')
        es_fotografia = cleaned_data.get('es_fotografia')

        # 1. Al menos una validación necesaria
        if not valida_division and not valida_escolares:
            raise forms.ValidationError("El documento debe ser validado por al menos un departamento (División o Escolares).")

        # 2. Mutuamente excluyentes y obligatorios: PDF o Fotografía
        if not acepta_solo_pdf and not es_fotografia:
            raise forms.ValidationError("El documento debe configurarse como 'Solo acepta PDF' o 'Es fotografía'.")
        if acepta_solo_pdf and es_fotografia:
            raise forms.ValidationError("Un documento no puede ser 'Solo acepta PDF' y 'Es fotografía' al mismo tiempo.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:  # Si es nuevo
            from django.db.models import Max
            max_orden = TipoDocumento.objects.filter(modalidad=instance.modalidad).aggregate(Max('orden'))['orden__max']
            instance.orden = (max_orden or 0) + 1
        if commit:
            instance.save()
        return instance
