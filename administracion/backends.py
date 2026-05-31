from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.conf import settings

class DynamicEmailBackend(SMTPEmailBackend):
    """
    Backend de correo personalizado que lee las credenciales SMTP de forma dinámica
    desde el modelo ConfiguracionInstitucional. Si no existen, usa las credenciales
    estáticas definidas en settings.py.
    """
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        
        try:
            from administracion.models import ConfiguracionInstitucional
            from administracion.crypto import decrypt
            config = ConfiguracionInstitucional.objects.first()
            if config and config.email_remitente and config.email_password:
                self.host = config.email_host
                self.port = config.email_port
                self.username = config.email_remitente
                self.password = decrypt(config.email_password)
                self.use_tls = config.email_use_tls
                self.use_ssl = False if config.email_use_tls else (config.email_port == 465)
        except Exception:
            # Excepción probable durante migraciones iniciales (antes de existir tablas)
            pass

    def send_messages(self, email_messages):
        """
        Reemplaza el DEFAULT_FROM_EMAIL por el remitente configurado antes de enviar.
        """
        if not email_messages:
            return 0
            
        try:
            from administracion.models import ConfiguracionInstitucional
            config = ConfiguracionInstitucional.objects.first()
            custom_from = None
            if config and config.email_remitente:
                custom_from = f'Sistema de Titulación ITA <{config.email_remitente}>'
                
            if custom_from:
                for msg in email_messages:
                    # Si usa el default, lo reemplazamos por el dinámico
                    if msg.from_email == settings.DEFAULT_FROM_EMAIL:
                        msg.from_email = custom_from
        except Exception:
            pass
            
        return super().send_messages(email_messages)
