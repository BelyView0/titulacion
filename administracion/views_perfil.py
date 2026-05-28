from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django import forms
from administracion.models import Rol, Usuario
from expediente.models import Expediente, Documento
from alumnos.forms import ExpedienteForm

class FotoPerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['foto_perfil']
        widgets = {
            'foto_perfil': forms.FileInput(attrs={'class': 'form-control form-control-sm', 'accept': 'image/*'})
        }

class PerfilView(LoginRequiredMixin, View):
    template_name = 'perfil.html'

    def get(self, request):
        user = request.user
        context = {
            'usuario': user,
        }

        if user.rol == Rol.ALUMNO:
            # Obtener expediente si existe
            try:
                expediente = user.expediente
                context['expediente'] = expediente
                
                # Obtener la foto ovalada
                foto_doc = Documento.objects.filter(
                    expediente=expediente, 
                    tipo_documento__es_fotografia=True
                ).first()
                context['foto_doc'] = foto_doc

                # Si es borrador, enviar el form para editar
                if expediente.estado == 'BORRADOR':
                    context['form'] = ExpedienteForm(instance=expediente)

            except Expediente.DoesNotExist:
                pass
        else:
            context['foto_form'] = FotoPerfilForm(instance=user)

        return render(request, self.template_name, context)

    def post(self, request):
        user = request.user
        
        if user.rol != Rol.ALUMNO:
            foto_form = FotoPerfilForm(request.POST, request.FILES, instance=user)
            if foto_form.is_valid():
                foto_form.save()
                messages.success(request, 'Foto de perfil actualizada correctamente.')
                return redirect('perfil')
            
            context = {
                'usuario': user,
                'foto_form': foto_form,
            }
            messages.error(request, 'Por favor corrige los errores del formulario.')
            return render(request, self.template_name, context)

        try:
            expediente = user.expediente
        except Expediente.DoesNotExist:
            messages.error(request, 'No se encontró tu expediente.')
            return redirect('perfil')

        if expediente.estado != 'BORRADOR':
            messages.error(request, 'El expediente no se encuentra en estado de borrador.')
            return redirect('perfil')

        form = ExpedienteForm(request.POST, instance=expediente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Datos del expediente actualizados correctamente.')
            return redirect('perfil')
        
        # If not valid, re-render
        context = {
            'usuario': user,
            'expediente': expediente,
            'form': form,
        }
        foto_doc = Documento.objects.filter(
            expediente=expediente, 
            tipo_documento__es_fotografia=True
        ).first()
        context['foto_doc'] = foto_doc
        
        messages.error(request, 'Por favor corrige los errores del formulario.')
        return render(request, self.template_name, context)
