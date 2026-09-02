from django import forms
from expediente.models import Expediente, Modalidad, PlanEstudios
from administracion.models import Profesor
from expediente.constants import FORMATO_DOCUMENTO_CHOICES, DEFAULT_FORMATOS


class ExpedienteForm(forms.ModelForm):
    plan_estudios = forms.ModelChoiceField(
        queryset=PlanEstudios.objects.filter(activo=True),
        label='Plan de estudios',
        empty_label='— Selecciona tu plan de estudios —',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_plan_estudios'}),
    )

    class Meta:
        model = Expediente
        fields = [
            'plan_estudios', 'modalidad', 'asesor',
            'titulo_trabajo', 'nombre_empresa',
        ]
        widgets = {
            'modalidad': forms.Select(attrs={'class': 'form-select', 'id': 'id_modalidad'}),
            'asesor': forms.Select(attrs={'class': 'form-select'}),
            'titulo_trabajo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre del proyecto / trabajo de titulación',
            }),
            'nombre_empresa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Empresa u organización (si aplica)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modalidad'].empty_label = '— Primero selecciona plan de estudios —'
        self.fields['modalidad'].queryset = Modalidad.objects.none()
        self.fields['asesor'].queryset = Profesor.objects.filter(activo=True)
        self.fields['asesor'].empty_label = '— Selecciona tu asesor —'
        self.fields['asesor'].required = True
        self.fields['titulo_trabajo'].required = True
        self.fields['nombre_empresa'].required = True

        plan_id = None
        if self.data.get('plan_estudios'):
            plan_id = self.data.get('plan_estudios')
        elif self.instance and self.instance.plan_estudios_id:
            plan_id = self.instance.plan_estudios_id
            self.fields['plan_estudios'].initial = plan_id

        if plan_id:
            self.fields['modalidad'].queryset = Modalidad.objects.filter(
                plan_estudios_id=plan_id, activa=True
            )

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get('plan_estudios')
        modalidad = cleaned.get('modalidad')
        if plan and modalidad and modalidad.plan_estudios_id != plan.id:
            self.add_error('modalidad', 'La modalidad no corresponde al plan seleccionado.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.modalidad and not instance.plan_estudios_id:
            instance.plan_estudios = instance.modalidad.plan_estudios
        if commit:
            instance.save()
        return instance
