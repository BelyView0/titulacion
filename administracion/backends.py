from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class DynamicEmailBackend(SMTPEmailBackend):
    """
    Backend SMTP que lee credenciales desde ConfiguracionInstitucional en cada envío.
    """
    def _aplicar_configuracion(self):
        try:
            from administracion.crypto import decrypt
            from administracion.models import ConfiguracionInstitucional

            config = ConfiguracionInstitucional.objects.first()
            if config and config.email_remitente and config.email_password:
                self.host = config.email_host or 'smtp.gmail.com'
                self.port = config.email_port or 587
                self.username = config.email_remitente
                self.password = decrypt(config.email_password)
                self.use_tls = config.email_use_tls
                self.use_ssl = False if config.email_use_tls else (config.email_port == 465)
                return True
        except Exception:
            pass
        return False

    def open(self):
        self._aplicar_configuracion()
        return super().open()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        self._aplicar_configuracion()
        # Cerrar conexión previa para forzar credenciales actualizadas
        if self.connection:
            try:
                self.close()
            except Exception:
                pass

        try:
            from administracion.models import ConfiguracionInstitucional
            config = ConfiguracionInstitucional.objects.first()
            custom_from = None
            if config and config.email_remitente:
                custom_from = f'Sistema de Titulación ITA <{config.email_remitente}>'

            if custom_from:
                for msg in email_messages:
                    if not msg.from_email or msg.from_email == settings.DEFAULT_FROM_EMAIL:
                        msg.from_email = custom_from
        except Exception:
            pass

        return super().send_messages(email_messages)
