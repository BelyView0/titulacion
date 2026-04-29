"""
Vistas personalizadas para el sistema de seguridad basado en OTP (Códigos de 6 dígitos)
para recuperación y cambio de contraseñas.
"""
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
import random

from administracion.models import Usuario, PasswordResetOTP
from administracion.emails import enviar_codigo_otp, enviar_alerta_cambio_password

def generate_otp_for_user(user):
    """Genera un código de 6 dígitos y lo guarda en la base de datos."""
    codigo = f"{random.randint(0, 999999):06d}"
    # Invalida OTPs anteriores
    PasswordResetOTP.objects.filter(usuario=user, usado=False).update(usado=True)
    otp = PasswordResetOTP.objects.create(usuario=user, codigo=codigo)
    return otp

def is_otp_valid(user, codigo):
    """Verifica si un OTP es correcto y no tiene más de 5 minutos."""
    try:
        otp = PasswordResetOTP.objects.filter(usuario=user, codigo=codigo, usado=False).latest('creado_en')
        # Verificar expiración (5 minutos)
        if timezone.now() > otp.creado_en + timedelta(minutes=5):
            return False
        return otp
    except PasswordResetOTP.DoesNotExist:
        return False

# ─── RECUPERACIÓN DE CONTRASEÑA (Desde Login) ────────────────────────────────

class OTPPasswordResetRequestView(View):
    """Paso 1: Solicitar correo electrónico para recuperar."""
    def get(self, request):
        return render(request, 'auth/password_reset.html')

    def post(self, request):
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, 'Debes ingresar un correo electrónico.')
            return render(request, 'auth/password_reset.html')

        user = Usuario.objects.filter(email=email, is_active=True).first()
        if user:
            otp = generate_otp_for_user(user)
            enviar_codigo_otp(user, otp.codigo, context='reset')
            request.session['reset_user_id'] = user.id
            return redirect('password_reset_verify')
        else:
            # Por seguridad, no decimos si el correo existe o no, pero redirigimos a la misma vista de verificación
            # (Aunque no podrán pasar si no reciben el código)
            messages.error(request, 'Si el correo existe, te hemos enviado un código. Revisa tu bandeja de entrada.')
            return render(request, 'auth/password_reset.html')

class OTPPasswordResetVerifyView(View):
    """Paso 2: Ingresar código OTP y nueva contraseña."""
    def get(self, request):
        if 'reset_user_id' not in request.session:
            return redirect('password_reset')
        return render(request, 'auth/password_reset_confirm.html')

    def post(self, request):
        user_id = request.session.get('reset_user_id')
        if not user_id:
            return redirect('password_reset')

        user = Usuario.objects.filter(id=user_id).first()
        codigo = request.POST.get('otp', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not user:
            return redirect('password_reset')

        if password != password_confirm:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'auth/password_reset_confirm.html')

        if len(password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'auth/password_reset_confirm.html')

        otp_instance = is_otp_valid(user, codigo)
        if not otp_instance:
            messages.error(request, 'El código es incorrecto o ha expirado (límite de 5 minutos). Solicita uno nuevo.')
            return render(request, 'auth/password_reset_confirm.html')

        # Si todo es correcto, cambiar contraseña
        user.set_password(password)
        user.save()
        
        # Marcar OTP como usado
        otp_instance.usado = True
        otp_instance.save()

        # Limpiar sesión y enviar notificación
        del request.session['reset_user_id']
        enviar_alerta_cambio_password(user)

        return redirect('password_reset_complete')

class OTPPasswordResetCompleteView(View):
    """Paso 3: Éxito en recuperación."""
    def get(self, request):
        return render(request, 'auth/password_reset_complete.html')


# ─── CAMBIO DE CONTRASEÑA (Usuario Autenticado) ──────────────────────────────

class OTPPasswordChangeRequestView(LoginRequiredMixin, View):
    """Paso 1: Solicitar cambio desde la sesión (Genera OTP automáticamente)."""
    def get(self, request):
        # Generar código y enviar por correo al entrar a esta ruta
        otp = generate_otp_for_user(request.user)
        enviar_codigo_otp(request.user, otp.codigo, context='change')
        return redirect('password_change_verify')

class OTPPasswordChangeVerifyView(LoginRequiredMixin, View):
    """Paso 2: Ingresar OTP, contraseña actual y nueva."""
    def get(self, request):
        return render(request, 'auth/password_change.html')

    def post(self, request):
        codigo = request.POST.get('otp', '').strip()
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        new_password_confirm = request.POST.get('new_password_confirm', '')

        # Validar contraseña actual
        if not request.user.check_password(old_password):
            messages.error(request, 'Tu contraseña actual es incorrecta.')
            return render(request, 'auth/password_change.html')

        # Validar nueva contraseña
        if new_password != new_password_confirm:
            messages.error(request, 'Las nuevas contraseñas no coinciden.')
            return render(request, 'auth/password_change.html')

        if len(new_password) < 8:
            messages.error(request, 'La nueva contraseña debe tener al menos 8 caracteres.')
            return render(request, 'auth/password_change.html')

        # Validar OTP
        otp_instance = is_otp_valid(request.user, codigo)
        if not otp_instance:
            messages.error(request, 'El código es incorrecto o ha expirado (límite de 5 minutos). Da clic en "Reenviar código".')
            return render(request, 'auth/password_change.html')

        # Cambiar contraseña
        request.user.set_password(new_password)
        request.user.save()
        
        # Mantener la sesión activa después del cambio de contraseña
        update_session_auth_hash(request, request.user)

        otp_instance.usado = True
        otp_instance.save()

        enviar_alerta_cambio_password(request.user)

        return redirect('password_change_done')

class OTPPasswordChangeDoneView(LoginRequiredMixin, View):
    """Paso 3: Éxito en cambio."""
    def get(self, request):
        return render(request, 'auth/password_change_done.html')
