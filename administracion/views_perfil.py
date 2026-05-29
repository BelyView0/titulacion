from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django import forms
from administracion.models import Rol, Usuario, EmailVerificationOTP
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from expediente.models import Expediente, Documento
from alumnos.forms import ExpedienteForm

from administracion.forms import UsuarioPerfilBasicoForm

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
        
        # Formulario base para TODOS los roles
        context['perfil_basico_form'] = UsuarioPerfilBasicoForm(instance=user)

        return render(request, self.template_name, context)

    def post(self, request):
        user = request.user
        
        # Hay dos posibles formularios: perfil_basico o expediente (solo alumnos)
        if 'perfil_basico' in request.POST:
            old_email = user.email
            old_institucional = user.correo_institucional
            perfil_basico_form = UsuarioPerfilBasicoForm(request.POST, request.FILES, instance=user)
            
            if perfil_basico_form.is_valid():
                user_instance = perfil_basico_form.save(commit=False)
                
                # Check for changes in emails to trigger verification
                if user_instance.email != old_email:
                    user_instance.email_verificado = False
                    # Aquí enviaremos el OTP más adelante
                
                if user_instance.correo_institucional != old_institucional:
                    user_instance.correo_institucional_verificado = False
                    # Aquí enviaremos el OTP más adelante

                user_instance.save()
                messages.success(request, 'Perfil actualizado correctamente. Si cambiaste tu correo, por favor verifícalo.')
                return redirect('perfil')
            
            context = {
                'usuario': user,
                'perfil_basico_form': perfil_basico_form,
            }
            if user.rol == Rol.ALUMNO and getattr(user, 'tiene_expediente', False):
                context['expediente'] = user.expediente
                context['form'] = ExpedienteForm(instance=user.expediente)
                context['foto_doc'] = Documento.objects.filter(expediente=user.expediente, tipo_documento__es_fotografia=True).first()

            messages.error(request, 'Por favor corrige los errores del formulario de perfil.')
            return render(request, self.template_name, context)

        # Manejo del formulario de expediente (Solo Alumnos)
        if user.rol != Rol.ALUMNO:
            return redirect('perfil')

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

class EnviarVerificacionEmailView(LoginRequiredMixin, View):
    def get(self, request, tipo):
        user = request.user
        
        if tipo not in ['personal', 'institucional']:
            messages.error(request, 'Tipo de correo inválido.')
            return redirect('perfil')

        correo_destino = user.email if tipo == 'personal' else user.correo_institucional

        if not correo_destino:
            messages.error(request, 'No tienes registrado este tipo de correo.')
            return redirect('perfil')

        # Invalidate old OTPs for this user and type
        EmailVerificationOTP.objects.filter(usuario=user, tipo=tipo, utilizado=False).update(utilizado=True)

        # Create new OTP
        codigo = get_random_string(length=6, allowed_chars='0123456789')
        EmailVerificationOTP.objects.create(
            usuario=user,
            tipo=tipo,
            codigo=codigo
        )

        # Send email
        subject = f"Código de Verificación para Correo {tipo.capitalize()}"
        message = f"Tu código de verificación es: {codigo}\nEste código expirará en 15 minutos."
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [correo_destino],
                fail_silently=False,
            )
            messages.success(request, f'Se ha enviado un código de verificación a {correo_destino}.')
        except Exception as e:
            messages.error(request, f'Error al enviar el correo: {e}')

        return redirect('perfil_verificar_validar', tipo=tipo)

class ValidarVerificacionEmailView(LoginRequiredMixin, View):
    template_name = 'auth/email_verification.html'

    def get(self, request, tipo):
        if tipo not in ['personal', 'institucional']:
            return redirect('perfil')
            
        context = {
            'tipo': tipo,
            'correo': request.user.email if tipo == 'personal' else request.user.correo_institucional
        }
        return render(request, self.template_name, context)

    def post(self, request, tipo):
        if tipo not in ['personal', 'institucional']:
            return redirect('perfil')

        codigo = request.POST.get('otp', '').strip()
        user = request.user

        otp_obj = EmailVerificationOTP.objects.filter(
            usuario=user,
            tipo=tipo,
            codigo=codigo,
            utilizado=False
        ).first()

        if not otp_obj:
            messages.error(request, 'El código ingresado es incorrecto o ya fue utilizado.')
            return redirect('perfil_verificar_validar', tipo=tipo)

        if not otp_obj.is_valid():
            messages.error(request, 'El código ingresado ha expirado. Por favor, solicita uno nuevo.')
            return redirect('perfil')

        # Mark as used and verify email
        otp_obj.utilizado = True
        otp_obj.save()

        if tipo == 'personal':
            user.email_verificado = True
        else:
            user.correo_institucional_verificado = True
            
        user.save()

        messages.success(request, f'Tu correo {tipo} ha sido verificado exitosamente.')
        return redirect('perfil')
