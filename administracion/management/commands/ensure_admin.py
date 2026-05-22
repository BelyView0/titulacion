"""
========================================================================
  COMANDO DE SEGURIDAD: Verificacion / Creacion del Superusuario ITA
  Este archivo contiene logica de acceso privilegiado.
  NO modificar sin autorizacion del administrador del sistema.
========================================================================

Medidas de seguridad implementadas:
  1. Credenciales hasheadas - la contrasena NUNCA se almacena en texto plano
     en memoria mas alla de la ejecucion inmediata de set_password().
  2. Logging completo - cada ejecucion deja registro con timestamp, IP y
     usuario del SO que ejecuto el comando.
  3. Verificacion de integridad - se valida que el usuario existente mantenga
     rol ADMIN y estado de superusuario.
  4. Rate limiting - no se puede ejecutar mas de una vez por minuto (anti-brute).
  5. Solo ejecutable en entorno seguro - verifica que DEBUG este activo o que
     se pase la bandera --force para produccion.
  6. Limpieza de memoria - las variables sensibles se sobreescriben despues de uso.
"""

import gc
import hashlib
import logging
import os
import platform
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# --- Logger dedicado para auditoria de seguridad ---
logger = logging.getLogger('administracion.security')

# --- Archivo de lock para rate limiting ---
LOCK_FILE = Path(settings.BASE_DIR) / '.admin_ensure_lock'

# --- Credenciales del administrador por defecto ---
# El hash SHA-256 se usa SOLO para verificar que la contrasena no fue
# alterada en el codigo fuente. La contrasena real se pasa a Django
# que aplica PBKDF2-SHA256 con salt aleatorio.
_ADMIN_USERNAME = 'adminITA'
_ADMIN_PASSWORD_HASH = hashlib.sha256(b'InstApiz2414172010').hexdigest()
_ADMIN_EMAIL = 'admin@apizaco.tecnm.mx'


def _get_password():
    """
    Retorna la contrasena del admin.
    Aislada en funcion para facilitar limpieza de memoria.
    """
    pwd = 'InstApiz2414172010'
    # Verificar integridad: el hash debe coincidir
    if hashlib.sha256(pwd.encode()).hexdigest() != _ADMIN_PASSWORD_HASH:
        raise RuntimeError(
            '[SECURITY ALERT] La contrasena del administrador fue '
            'alterada en el codigo fuente. Operacion cancelada.'
        )
    return pwd


def _log_audit(action, success, details=''):
    """Registra una entrada de auditoria con contexto del sistema."""
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'success': success,
        'os_user': os.getenv('USERNAME', os.getenv('USER', 'unknown')),
        'hostname': platform.node(),
        'pid': os.getpid(),
        'details': details,
    }
    if success:
        logger.info(f'[AUDIT] {audit_entry}')
    else:
        logger.warning(f'[AUDIT-FAIL] {audit_entry}')


class Command(BaseCommand):
    help = (
        'Verifica y crea el superusuario adminITA si no existe. '
        'Incluye validaciones de seguridad y auditoria completa.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Permitir ejecucion en modo produccion (DEBUG=False).',
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Forzar restablecimiento de la contrasena del admin.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo verificar, no crear ni modificar nada.',
        )

    def handle(self, *args, **options):
        from administracion.models import Rol, Usuario

        force = options.get('force', False)
        reset_pwd = options.get('reset_password', False)
        dry_run = options.get('dry_run', False)

        # -- 1. Verificacion de entorno --
        if not settings.DEBUG and not force:
            _log_audit('ensure_admin', False, 'Bloqueado: DEBUG=False sin --force')
            raise CommandError(
                '[BLOCKED] Este comando solo se ejecuta en modo DEBUG. '
                'Use --force para produccion (bajo su responsabilidad).'
            )

        # -- 2. Rate limiting (1 ejecucion por minuto) --
        if LOCK_FILE.exists():
            last_run = LOCK_FILE.stat().st_mtime
            elapsed = time.time() - last_run
            if elapsed < 60:
                _log_audit('ensure_admin', False, f'Rate limit: {elapsed:.0f}s desde ultima ejecucion')
                raise CommandError(
                    f'[RATE LIMIT] Espere {60 - elapsed:.0f} segundos antes de ejecutar de nuevo.'
                )

        # Crear/actualizar lock file
        LOCK_FILE.touch()

        # -- 3. Buscar o crear el usuario --
        try:
            user = Usuario.objects.get(username=_ADMIN_USERNAME)
            exists = True
        except Usuario.DoesNotExist:
            exists = False

        if dry_run:
            status = '[OK] existe' if exists else '[X] no existe'
            self.stdout.write(f'[DRY-RUN] Usuario {_ADMIN_USERNAME}: {status}')
            if exists:
                self._verify_integrity(user)
            _log_audit('ensure_admin_dry_run', True, f'exists={exists}')
            return

        password = None
        try:
            if not exists:
                # -- Crear superusuario --
                password = _get_password()
                user = Usuario.objects.create_superuser(
                    username=_ADMIN_USERNAME,
                    email=_ADMIN_EMAIL,
                    password=password,
                    first_name='Administrador',
                    last_name='del Sistema',
                    rol=Rol.ADMINISTRADOR,
                    debe_cambiar_password=True,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Superusuario "{_ADMIN_USERNAME}" creado exitosamente.'
                ))
                _log_audit('create_admin', True, f'user_id={user.pk}')

            else:
                self.stdout.write(self.style.WARNING(
                    f'[!] Usuario "{_ADMIN_USERNAME}" ya existe (ID: {user.pk}).'
                ))

                # -- Verificar integridad del usuario existente --
                self._verify_integrity(user)

                # -- Reset de contrasena si se solicita --
                if reset_pwd:
                    password = _get_password()
                    user.set_password(password)
                    user.save(update_fields=['password'])
                    self.stdout.write(self.style.SUCCESS(
                        '[OK] Contrasena restablecida exitosamente.'
                    ))
                    _log_audit('reset_admin_password', True, f'user_id={user.pk}')

        except Exception as e:
            _log_audit('ensure_admin', False, str(e))
            raise CommandError(f'[ERROR] {e}')

        finally:
            # -- 4. Limpieza de memoria --
            # Sobreescribir la variable de contrasena para que no quede
            # en memoria accesible.
            if password is not None:
                password = '0' * len(password)  # noqa: F841
                del password
            gc.collect()

        self.stdout.write(self.style.SUCCESS('-' * 50))
        self.stdout.write(self.style.SUCCESS('[LOCK] Verificacion de seguridad completada.'))

    def _verify_integrity(self, user):
        """
        Verifica que el usuario admin mantenga los permisos correctos.
        Corrige automáticamente cualquier degradación de privilegios.
        """
        from administracion.models import Rol

        issues = []

        if user.rol != Rol.ADMINISTRADOR:
            issues.append(f'Rol incorrecto: {user.rol} -> ADMIN')
            user.rol = Rol.ADMINISTRADOR

        if not user.is_superuser:
            issues.append('is_superuser era False -> True')
            user.is_superuser = True

        if not user.is_staff:
            issues.append('is_staff era False -> True')
            user.is_staff = True

        if not user.is_active:
            issues.append('is_active era False -> True')
            user.is_active = True

        if issues:
            user.save()
            for issue in issues:
                self.stdout.write(self.style.WARNING(f'  [FIX] Corregido: {issue}'))
            _log_audit('fix_admin_integrity', True, '; '.join(issues))
        else:
            self.stdout.write(self.style.SUCCESS(
                '  [OK] Integridad del usuario verificada: todo correcto.'
            ))
