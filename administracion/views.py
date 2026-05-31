"""
Vistas del módulo Administración.
- Admin: gestión de usuarios, carreras, configuración del sistema.
- Jefe de Proyecto (Administración): vista de expedientes de su carrera,
  asignación de jurado, y estadísticas de titulados.
"""
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, TemplateView, DetailView
)
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone

from expediente.mixins import AdminRequeridoMixin, JefeProyectoRequeridoMixin
from administracion.models import Carrera, Departamento, Usuario, Rol, ConfiguracionInstitucional, JefeDepartamento, SolicitudCambioJefe
from administracion.forms import UsuarioCreateForm, UsuarioUpdateForm, ConfiguracionInstitucionalForm, JefeDepartamentoForm
from expediente.models import (
    Expediente, Documento, AsignacionJurado,
    EstadoExpediente, EstadoDocumento, Modalidad, ActoProtocolario
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado

Usuario = get_user_model()


class ConfiguracionUpdateView(AdminRequeridoMixin, UpdateView):
    model = ConfiguracionInstitucional
    form_class = ConfiguracionInstitucionalForm
    template_name = 'administracion/configuracion.html'
    success_url = reverse_lazy('administracion:configuracion')

    def get_object(self, queryset=None):
        obj, created = ConfiguracionInstitucional.objects.get_or_create(id=1)
        return obj

    def form_valid(self, form):
        messages.success(self.request, 'Membretes institucionales actualizados correctamente.')
        return super().form_valid(form)


class ConfiguracionEmailUpdateView(AdminRequeridoMixin, UpdateView):
    model = ConfiguracionInstitucional
    from .forms import ConfiguracionEmailForm
    form_class = ConfiguracionEmailForm
    template_name = 'administracion/configuracion_email.html'
    success_url = reverse_lazy('administracion:configuracion_email')

    def get_object(self, queryset=None):
        obj, created = ConfiguracionInstitucional.objects.get_or_create(id=1)
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        from django.core.mail import send_mail
        from django.conf import settings
        
        user_email = self.request.user.email
        if user_email:
            try:
                send_mail(
                    subject='[ITA Titulación] Verificación de Configuración de Correo',
                    message='¡Hola! Si has recibido este correo, significa que la configuración SMTP ha sido guardada correctamente y el sistema ya puede enviar correos usando este servidor.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_email],
                    fail_silently=False
                )
                messages.success(self.request, 'Configuración guardada y correo de prueba enviado exitosamente a tu dirección.')
            except Exception as e:
                messages.error(self.request, f'Configuración guardada, pero falló el correo de prueba. Revisa tus credenciales o conexión: {str(e)}')
        else:
            messages.success(self.request, 'Configuración de correo actualizada correctamente (no se envió correo de prueba porque no tienes un email registrado).')
            
        return response


from django.http import JsonResponse
from django.views import View
from administracion.crypto import decrypt

class RevelarPasswordSMTPView(AdminRequeridoMixin, View):
    """Verifica la contraseña del admin actual para revelar la credencial SMTP"""
    def post(self, request, *args, **kwargs):
        admin_pass = request.POST.get('admin_password', '')
        if not request.user.check_password(admin_pass):
            return JsonResponse({'status': 'error', 'message': 'Contraseña de administrador incorrecta.'}, status=403)
        
        config = ConfiguracionInstitucional.objects.first()
        if config and config.email_password:
            decrypted = decrypt(config.email_password)
            return JsonResponse({'status': 'success', 'password': decrypted})
        
        return JsonResponse({'status': 'error', 'message': 'No hay contraseña guardada.'}, status=404)


# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA JEFES DE DEPARTAMENTO
# ═══════════════════════════════════════════════════════════════════════════════
class JefeDepartamentoListView(AdminRequeridoMixin, ListView):
    model = JefeDepartamento
    template_name = 'administracion/jefe_departamento_list.html'
    context_object_name = 'jefes'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departamentos_count'] = Departamento.objects.count()
        return ctx

class JefeDepartamentoCreateView(AdminRequeridoMixin, CreateView):
    model = JefeDepartamento
    form_class = JefeDepartamentoForm
    template_name = 'administracion/jefe_departamento_form.html'
    success_url = reverse_lazy('administracion:jefes')

    def dispatch(self, request, *args, **kwargs):
        if not Departamento.objects.exists():
            messages.error(request, 'No puedes asignar un Jefe porque no hay Departamentos registrados en el sistema. Por favor, crea un Departamento primero.')
            return redirect('administracion:jefes')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Jefe de Departamento creado correctamente.')
        return super().form_valid(form)

class JefeDepartamentoUpdateView(AdminRequeridoMixin, UpdateView):
    model = JefeDepartamento
    form_class = JefeDepartamentoForm
    template_name = 'administracion/jefe_departamento_form.html'
    success_url = reverse_lazy('administracion:jefes')

    def form_valid(self, form):
        messages.success(self.request, 'Jefe de Departamento actualizado correctamente.')
        return super().form_valid(form)

class JefeDepartamentoDeleteView(AdminRequeridoMixin, DeleteView):
    model = JefeDepartamento
    success_url = reverse_lazy('administracion:jefes')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Jefe de Departamento eliminado.')
        return super().delete(request, *args, **kwargs)

# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA ROL: ADMIN (gestión de sistema)
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardAdminView(AdminRequeridoMixin, TemplateView):
    template_name = 'administracion/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_alumnos'] = Usuario.objects.filter(rol='ALUMNO').count()
        ctx['total_expedientes'] = Expediente.objects.count()
        ctx['expedientes_activos'] = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = Expediente.objects.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()

        # Alumnos con búsqueda, filtros y paginación (LEFT JOIN a expediente)
        qs = Usuario.objects.filter(rol='ALUMNO').select_related(
            'carrera', 'expediente', 'expediente__modalidad'
        ).order_by('-date_joined')

        busqueda = self.request.GET.get('q', '').strip()
        carrera_id = self.request.GET.get('carrera', '')
        estado_filtro = self.request.GET.get('estado', '')

        if busqueda:
            qs = qs.filter(
                Q(first_name__unaccent__icontains=busqueda) |
                Q(last_name__unaccent__icontains=busqueda) |
                Q(username__unaccent__icontains=busqueda) |
                Q(numero_control__unaccent__icontains=busqueda)
            )
        if carrera_id:
            qs = qs.filter(carrera_id=carrera_id)
        if estado_filtro:
            if estado_filtro == 'SIN_EXPEDIENTE':
                qs = qs.filter(expediente__isnull=True)
            else:
                qs = qs.filter(expediente__estado=estado_filtro)

        ctx['busqueda'] = busqueda
        ctx['carrera_id'] = carrera_id
        ctx['estado_filtro'] = estado_filtro
        ctx['carreras_filter'] = Carrera.objects.filter(activa=True)
        ctx['estados_filter'] = EstadoExpediente.choices
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['alumnos_page'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()

        ctx['carreras'] = Carrera.objects.filter(activa=True).annotate(
            num_expedientes=Count('usuario__expediente')
        )

        # --- Alertas del sistema para el administrador ---
        alertas = []

        # Verificar roles criticos
        roles_criticos = [
            (Rol.JEFE_PROYECTO, 'Jefe de Proyecto / Administracion',
             'Este usuario gestiona la asignacion de jurados y programa actos protocolarios.'),
            (Rol.ACADEMICO, 'Jefe de Division de Estudios Profesionales',
             'Este usuario valida documentos y supervisa el proceso academico de titulacion.'),
            (Rol.ESCOLARES, 'Jefe de Servicios Escolares',
             'Este usuario gestiona el trámite DGP, la validación de cédulas profesionales y la entrega final.'),
        ]

        for rol_value, rol_nombre, descripcion in roles_criticos:
            if not Usuario.objects.filter(rol=rol_value, is_active=True).exists():
                alertas.append({
                    'tipo': 'danger',
                    'icono': 'bi-person-x-fill',
                    'titulo': f'Falta: {rol_nombre}',
                    'mensaje': f'No hay ningun usuario con el rol "{rol_nombre}" registrado en el sistema. {descripcion}',
                    'accion_url': reverse_lazy('administracion:usuario_crear'),
                    'accion_texto': 'Crear usuario',
                })

        # Verificar carreras
        if not Carrera.objects.filter(activa=True).exists():
            alertas.append({
                'tipo': 'warning',
                'icono': 'bi-mortarboard-fill',
                'titulo': 'Sin carreras registradas',
                'mensaje': 'No hay carreras activas en el sistema. Los alumnos no podran registrar expedientes sin una carrera asignada.',
                'accion_url': reverse_lazy('administracion:carrera_crear'),
                'accion_texto': 'Crear carrera',
            })

        # Verificar departamentos
        if not Departamento.objects.exists():
            alertas.append({
                'tipo': 'warning',
                'icono': 'bi-building',
                'titulo': 'Sin departamentos registrados',
                'mensaje': 'No hay departamentos en el sistema. Los departamentos son necesarios para asignar jefes de proyecto.',
                'accion_url': '/admin/administracion/departamento/add/',
                'accion_texto': 'Crear departamento',
            })

        # Verificar jefes de departamento (para oficios)
        if Departamento.objects.exists() and not JefeDepartamento.objects.exists():
            alertas.append({
                'tipo': 'info',
                'icono': 'bi-person-badge',
                'titulo': 'Sin jefes de departamento asignados',
                'mensaje': 'No se han registrado jefes de departamento. Son necesarios para firmar oficios de asignacion de jurado.',
                'accion_url': reverse_lazy('administracion:jefe_crear'),
                'accion_texto': 'Asignar jefe',
            })

        ctx['alertas_sistema'] = alertas
        return ctx


# ─── USUARIOS ────────────────────────────────────────────────
class UsuarioListView(AdminRequeridoMixin, ListView):
    model = Usuario
    template_name = 'administracion/usuarios/lista.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        qs = Usuario.objects.select_related('carrera').order_by('rol', 'last_name')
        rol = self.request.GET.get('rol')
        busqueda = self.request.GET.get('q')
        if rol:
            qs = qs.filter(rol=rol)
        if busqueda:
            qs = qs.filter(
                Q(first_name__unaccent__icontains=busqueda) |
                Q(last_name__unaccent__icontains=busqueda) |
                Q(username__unaccent__icontains=busqueda) |
                Q(email__unaccent__icontains=busqueda)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['rol_filtro'] = self.request.GET.get('rol', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        from administracion.models import Rol
        from expediente.models import PlanEstudios
        ctx['roles'] = Rol.choices
        ctx['carreras_count'] = Carrera.objects.count()
        ctx['planes_count'] = PlanEstudios.objects.count()
        return ctx


class UsuarioCreateView(AdminRequeridoMixin, CreateView):
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = 'administracion/usuarios/form.html'
    success_url = reverse_lazy('administracion:usuarios')

    def form_valid(self, form):
        usuario = form.save(commit=False)
        password_clear = form.cleaned_data['password']
        usuario.set_password(password_clear)
        usuario.debe_cambiar_password = True  # Forzar cambio de contraseña en su primer login por seguridad
        usuario.save()

        # Desactivar Jefe de Proyecto anterior automáticamente si aplica
        from administracion.models import Rol, Usuario as UserModel
        if usuario.rol == Rol.JEFE_PROYECTO and usuario.departamento and usuario.is_active:
            viejos = UserModel.objects.filter(
                rol=Rol.JEFE_PROYECTO, 
                departamento=usuario.departamento, 
                is_active=True
            ).exclude(pk=usuario.pk)
            for v in viejos:
                v.is_active = False
                v.save(update_fields=['is_active'])
            if viejos.exists():
                messages.info(self.request, f'El Jefe de Proyecto anterior para {usuario.departamento.nombre} ha sido desactivado automáticamente para mantener solo uno activo.')

        # Enviar correo de bienvenida y verificación
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings
        
        email = usuario.email
        if email:
            subject = "[ITA Titulación] Tu cuenta ha sido creada — Datos de Acceso"
            full_name = usuario.get_full_name() or usuario.numero_control
            
            context_data = {
                'full_name': full_name,
                'numero_control': usuario.numero_control,
                'password_clear': password_clear
            }
            from django.template.loader import render_to_string
            html_content = render_to_string('emails/nueva_cuenta.html', context_data)

            text_content = f"""Estimado(a) {full_name},

Te informamos que tu cuenta de acceso para la plataforma de titulación del Instituto Tecnológico de Apizaco ha sido creada.

Datos de Acceso:
- Número de control / empleado: {usuario.numero_control}
- Contraseña: {password_clear}

Puedes ingresar a la plataforma abriendo tu navegador web e introduciendo la dirección habitual de la institución.

IMPORTANTE: Por motivos de seguridad, el sistema te pedirá cambiar tu contraseña en tu primer inicio de sesión.

Instituto Tecnológico de Apizaco — TecNM.
"""
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=True)
            except Exception:
                pass

        messages.success(self.request, f'Usuario {usuario.get_full_name()} creado exitosamente y notificado por correo.')
        return redirect(self.success_url)


class UsuarioUpdateView(AdminRequeridoMixin, UpdateView):
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = 'administracion/usuarios/form.html'
    success_url = reverse_lazy('administracion:usuarios')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        usuario = self.object

        # ── Datos comunes ──
        ctx['usuario_rol'] = usuario.rol

        # ── ALUMNO: perfil, expediente, documentos, jurado, acto, historial ──
        if usuario.rol == Rol.ALUMNO:
            from alumnos.models import PerfilAlumno, Notificacion
            from administracion.forms import PerfilAlumnoAdminForm, ExpedienteAdminForm

            # Perfil extendido (form editable)
            try:
                perfil = usuario.perfil_alumno
                ctx['perfil_alumno'] = perfil
                if 'perfil_form' not in ctx:
                    ctx['perfil_form'] = PerfilAlumnoAdminForm(
                        instance=perfil, prefix='perfil'
                    )
            except PerfilAlumno.DoesNotExist:
                ctx['perfil_alumno'] = None
                ctx['perfil_form'] = None

            # Expediente y todo lo relacionado (form editable)
            try:
                expediente = usuario.expediente
                ctx['expediente'] = expediente
                if 'expediente_form' not in ctx:
                    ctx['expediente_form'] = ExpedienteAdminForm(
                        instance=expediente, prefix='exp'
                    )

                ctx['documentos'] = expediente.documentos.select_related(
                    'tipo_documento'
                ).prefetch_related('validaciones').order_by('tipo_documento__orden')

                # Jurado
                ctx['jurado'] = AsignacionJurado.objects.filter(
                    expediente=expediente
                ).select_related(
                    'presidente', 'secretario', 'vocal_propietario', 'vocal_suplente'
                ).first()

                # Acto protocolario
                try:
                    ctx['acto'] = expediente.acto_protocolario
                except ActoProtocolario.DoesNotExist:
                    ctx['acto'] = None

                # Empastado
                try:
                    ctx['empastado'] = expediente.empastado
                except Exception:
                    ctx['empastado'] = None

                # Historial
                ctx['historial'] = expediente.historial.select_related(
                    'realizado_por'
                ).order_by('-fecha')[:10]

            except Expediente.DoesNotExist:
                ctx['expediente'] = None
                ctx['expediente_form'] = None

            # Notificaciones recientes
            ctx['notificaciones'] = Notificacion.objects.filter(
                destinatario=usuario
            ).order_by('-fecha')[:5]

        # ── ESCOLARES / ACADEMICO / JEFE_PROYECTO: actividad relacionada ──
        elif usuario.rol in [Rol.ESCOLARES, Rol.ACADEMICO, Rol.JEFE_PROYECTO]:
            from expediente.models import (
                ValidacionDocumento, HistorialExpediente, RecepcionEmpastado
            )
            ctx['validaciones_realizadas'] = ValidacionDocumento.objects.filter(
                validado_por=usuario
            ).select_related('documento', 'documento__expediente').order_by('-fecha')[:10]

            ctx['cambios_realizados'] = HistorialExpediente.objects.filter(
                realizado_por=usuario
            ).select_related('expediente').order_by('-fecha')[:10]

            if usuario.rol == Rol.JEFE_PROYECTO:
                ctx['jurados_asignados'] = AsignacionJurado.objects.filter(
                    asignado_por=usuario
                ).select_related('expediente', 'presidente', 'secretario').order_by('-fecha_oficio')[:10]

            if usuario.rol == Rol.ACADEMICO:
                ctx['actos_programados'] = ActoProtocolario.objects.filter(
                    programado_por=usuario
                ).select_related('expediente').order_by('-fecha_acto')[:10]
                ctx['empastados_recibidos'] = RecepcionEmpastado.objects.filter(
                    recibido_por=usuario
                ).select_related('expediente').order_by('-fecha_recepcion')[:10]

        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form_type = request.POST.get('_form_type', 'usuario')

        if form_type == 'perfil':
            return self._save_perfil(request)
        elif form_type == 'expediente':
            return self._save_expediente(request)
        else:
            return super().post(request, *args, **kwargs)

    def _save_perfil(self, request):
        """Guarda el formulario de perfil académico del alumno."""
        from alumnos.models import PerfilAlumno
        from administracion.forms import PerfilAlumnoAdminForm

        edit_url = redirect('administracion:usuario_editar', pk=self.object.pk)

        try:
            perfil = self.object.perfil_alumno
        except PerfilAlumno.DoesNotExist:
            messages.error(request, 'Este alumno no tiene un perfil académico para editar.')
            return edit_url

        perfil_form = PerfilAlumnoAdminForm(
            request.POST, instance=perfil, prefix='perfil'
        )
        if perfil_form.is_valid():
            perfil_form.save()
            messages.success(request, 'Perfil académico actualizado exitosamente.')
        else:
            for field, errors in perfil_form.errors.items():
                label = perfil_form.fields[field].label if field in perfil_form.fields else field
                for error in errors:
                    messages.error(request, f'{label}: {error}')
        return edit_url

    def _save_expediente(self, request):
        """Guarda el formulario de expediente."""
        from administracion.forms import ExpedienteAdminForm

        edit_url = redirect('administracion:usuario_editar', pk=self.object.pk)

        try:
            expediente = self.object.expediente
        except Expediente.DoesNotExist:
            messages.error(request, 'Este alumno no tiene un expediente para editar.')
            return edit_url

        exp_form = ExpedienteAdminForm(
            request.POST, instance=expediente, prefix='exp'
        )
        if exp_form.is_valid():
            exp_form.save()
            messages.success(request, 'Expediente actualizado exitosamente.')
        else:
            for field, errors in exp_form.errors.items():
                label = exp_form.fields[field].label if field in exp_form.fields else field
                for error in errors:
                    messages.error(request, f'{label}: {error}')
        return edit_url

    def form_valid(self, form):
        usuario = form.save()
        
        # Desactivar Jefe de Proyecto anterior automáticamente si aplica
        from administracion.models import Rol, Usuario as UserModel
        if usuario.rol == Rol.JEFE_PROYECTO and usuario.departamento and usuario.is_active:
            viejos = UserModel.objects.filter(
                rol=Rol.JEFE_PROYECTO, 
                departamento=usuario.departamento, 
                is_active=True
            ).exclude(pk=usuario.pk)
            for v in viejos:
                v.is_active = False
                v.save(update_fields=['is_active'])
            if viejos.exists():
                messages.info(self.request, f'El Jefe de Proyecto anterior para {usuario.departamento.nombre} ha sido desactivado automáticamente para mantener solo uno activo.')

        messages.success(self.request, 'Datos del usuario actualizados exitosamente.')
        return redirect('administracion:usuario_editar', pk=self.object.pk)

    def get_success_url(self):
        return reverse_lazy('administracion:usuarios')

class UsuarioDeleteView(AdminRequeridoMixin, DeleteView):
    model = Usuario
    template_name = 'administracion/usuarios/eliminar.html'
    success_url = reverse_lazy('administracion:usuarios')

    def dispatch(self, request, *args, **kwargs):
        usuario = self.get_object()
        if usuario.pk == request.user.pk:
            messages.error(request, 'No puedes eliminar tu propia cuenta.')
            return redirect('administracion:usuarios')
            
        # Prevenir ir a la página de confirmación si tiene registros protegidos (Expediente)
        from expediente.models import Expediente
        if Expediente.objects.filter(alumno=usuario).exists():
            messages.error(request, 'No se puede eliminar este usuario porque tiene expedientes o registros protegidos vinculados en el sistema.')
            return redirect('administracion:usuarios')
            
        # Regla: Al menos un usuario de roles críticos / Jefe de Proyecto
        roles_criticos = [Rol.ADMINISTRADOR, Rol.ACADEMICO, Rol.ESCOLARES]
        if usuario.rol in roles_criticos and usuario.is_active:
            activos_count = Usuario.objects.filter(rol=usuario.rol, is_active=True).count()
            if activos_count <= 1:
                messages.error(request, f'No se puede eliminar al único usuario activo con el rol de {usuario.get_rol_display()}. Debe agregar alguien más con este rol antes de eliminar o desactivar al actual.')
                return redirect('administracion:usuarios')
                
        if usuario.rol == Rol.JEFE_PROYECTO and usuario.departamento and usuario.is_active:
            activos_count = Usuario.objects.filter(rol=Rol.JEFE_PROYECTO, departamento=usuario.departamento, is_active=True).count()
            if activos_count <= 1:
                messages.error(request, f'No se puede eliminar al único Jefe de Proyectos activo del departamento {usuario.departamento.nombre}. Asigne un nuevo Jefe de Proyecto primero (este se desactivará automáticamente al hacerlo).')
                return redirect('administracion:usuarios')

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        from django.http import Http404
        from django.db.models import ProtectedError
        try:
            return self.delete(request, *args, **kwargs)
        except Http404:
            messages.info(request, 'El usuario ya ha sido eliminado.')
            return redirect(self.success_url)
        except ProtectedError:
            messages.error(request, 'No se puede eliminar este usuario porque tiene expedientes o registros protegidos vinculados en el sistema.')
            return redirect(self.success_url)

    def delete(self, request, *args, **kwargs):
        usuario = self.get_object()
        
        # Validar contraseña del administrador
        admin_password = request.POST.get('admin_password', '')
        if not request.user.check_password(admin_password):
            messages.error(request, 'Contraseña de administrador incorrecta. No se pudo eliminar el usuario.')
            return redirect('administracion:usuarios')
            
        nombre_usuario = usuario.get_full_name() or usuario.username
        response = super().delete(request, *args, **kwargs)
        
        # Agregamos el mensaje de éxito solo si super().delete() no lanzó ninguna excepción
        messages.success(request, f'Usuario {nombre_usuario} eliminado exitosamente.')
        return response


# ─── CARRERAS ────────────────────────────────────────────────
class CarreraListView(AdminRequeridoMixin, ListView):
    model = Carrera
    template_name = 'administracion/carreras/lista.html'
    context_object_name = 'carreras'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departamentos_count'] = Departamento.objects.count()
        return ctx


class CarreraCreateView(AdminRequeridoMixin, CreateView):
    model = Carrera
    template_name = 'administracion/carreras/form.html'
    fields = ['nombre', 'clave', 'activa', 'departamento']
    success_url = reverse_lazy('administracion:carreras')

    def dispatch(self, request, *args, **kwargs):
        if not Departamento.objects.exists():
            messages.error(request, 'No puedes registrar una Carrera porque no hay Departamentos registrados en el sistema. Por favor, crea un Departamento primero.')
            return redirect('administracion:carreras')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Carrera creada exitosamente.')
        return super().form_valid(form)


class CarreraUpdateView(AdminRequeridoMixin, UpdateView):
    model = Carrera
    template_name = 'administracion/carreras/form.html'
    fields = ['nombre', 'clave', 'activa', 'departamento']
    success_url = reverse_lazy('administracion:carreras')

    def form_valid(self, form):
        messages.success(self.request, 'Carrera actualizada.')
        return super().form_valid(form)


# ═══════════════════════════════════════════════════════════════════════════════
# VISTAS PARA ROL: JEFE DE PROYECTO (Administración / Jefes de carrera)
# Pueden ver expedientes de SU carrera y generar asignación de jurado
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardJefeProyectoView(JefeProyectoRequeridoMixin, TemplateView):
    template_name = 'administracion/jefe/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        departamento = user.departamento

        # Expedientes de las carreras pertenecientes al departamento del jefe
        if departamento:
            expedientes_dept = Expediente.objects.filter(
                alumno__carrera__departamento=departamento
            )
        else:
            # Fallback a carrera si no hay departamento (compatibilidad)
            expedientes_dept = Expediente.objects.filter(
                alumno__carrera=user.carrera
            )
        
        expedientes_dept = expedientes_dept.select_related('alumno', 'modalidad', 'alumno__carrera')

        ctx['departamento'] = departamento
        ctx['carrera'] = user.carrera # Mantenemos carrera por compatibilidad en template
        ctx['total_expedientes'] = expedientes_dept.count()
        ctx['expedientes_activos'] = expedientes_dept.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = expedientes_dept.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()
        ctx['pendientes_jurado'] = expedientes_dept.filter(
            estado=EstadoExpediente.EMPASTADO_RECIBIDO
        ).count()

        # Búsqueda y paginación
        qs = expedientes_dept.order_by('-fecha_ultima_actualizacion')
        busqueda = self.request.GET.get('q', '').strip()
        carrera_id = self.request.GET.get('carrera', '')
        modalidad_id = self.request.GET.get('modalidad', '')

        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )
        if carrera_id:
            qs = qs.filter(alumno__carrera_id=carrera_id)
        if modalidad_id:
            qs = qs.filter(modalidad_id=modalidad_id)

        ctx['busqueda'] = busqueda
        ctx['carrera_id'] = carrera_id
        ctx['modalidad_id'] = modalidad_id

        if departamento:
            ctx['carreras_filter'] = Carrera.objects.filter(departamento=departamento, activa=True)
        else:
            ctx['carreras_filter'] = Carrera.objects.filter(id=user.carrera_id, activa=True) if user.carrera_id else Carrera.objects.none()
        ctx['modalidades_filter'] = Modalidad.objects.all()
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['expedientes_recientes'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()
        return ctx


class ExpedienteListaJefeView(JefeProyectoRequeridoMixin, ListView):
    """Lista de expedientes filtrados por la carrera del jefe de proyecto."""
    template_name = 'administracion/jefe/expedientes_lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        if user.departamento:
            qs = Expediente.objects.filter(alumno__carrera__departamento=user.departamento)
        else:
            qs = Expediente.objects.filter(alumno__carrera=user.carrera)

        qs = qs.select_related('alumno', 'modalidad').order_by('-fecha_ultima_actualizacion')

        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )

        carrera_id = self.request.GET.get('carrera', '')
        modalidad_id = self.request.GET.get('modalidad', '')

        if carrera_id:
            qs = qs.filter(alumno__carrera_id=carrera_id)
        if modalidad_id:
            qs = qs.filter(modalidad_id=modalidad_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['carrera'] = self.request.user.carrera
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        ctx['estados'] = EstadoExpediente.choices

        ctx['carrera_id'] = self.request.GET.get('carrera', '')
        ctx['modalidad_id'] = self.request.GET.get('modalidad', '')
        user = self.request.user
        if user.departamento:
            ctx['carreras_filter'] = Carrera.objects.filter(departamento=user.departamento, activa=True)
        else:
            ctx['carreras_filter'] = Carrera.objects.filter(id=user.carrera_id, activa=True) if user.carrera_id else Carrera.objects.none()
        ctx['modalidades_filter'] = Modalidad.objects.all()

        return ctx


class ExpedienteDetalleJefeView(JefeProyectoRequeridoMixin, DetailView):
    """Vista de detalle de un expediente (solo lectura) para jefe de proyecto."""
    model = Expediente
    template_name = 'administracion/jefe/expediente_detalle.html'
    context_object_name = 'expediente'

    def get_queryset(self):
        # Solo puede ver expedientes de su departamento
        user = self.request.user
        if user.departamento:
            return Expediente.objects.filter(
                alumno__carrera__departamento=user.departamento
            ).select_related('alumno', 'modalidad')
        return Expediente.objects.filter(
            alumno__carrera=user.carrera
        ).select_related('alumno', 'modalidad')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.object
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['jurado'] = AsignacionJurado.objects.filter(
            expediente=expediente
        ).select_related('presidente', 'secretario', 'vocal_propietario', 'vocal_suplente').first()
        
        # Visibilidad del acto para el Jefe
        try:
            acto = expediente.acto_protocolario
            ctx['acto'] = acto
            ctx['acto_expirado'] = acto.fecha_acto < timezone.now()
            ctx['confirmaciones_completas'] = acto.confirmaciones_completas()
        except:
            ctx['acto'] = None
            
        return ctx


class AsignacionJuradoJefeView(JefeProyectoRequeridoMixin, View):
    """
    El jefe de proyecto genera/actualiza la asignación de jurado
    para expedientes de su carrera.
    """

    def get(self, request, pk):
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)
        jurado = AsignacionJurado.objects.filter(expediente=expediente).first()

        # Obtener posibles sinodales desde el catálogo Profesor
        from administracion.models import Profesor
        sinodales = Profesor.objects.filter(activo=True).order_by('last_name', 'first_name')

        from django.template.loader import render_to_string
        from django.http import HttpResponse
        context = {
            'expediente': expediente,
            'jurado': jurado,
            'sinodales': sinodales,
        }
        return HttpResponse(render_to_string(
            'administracion/jefe/jurado_asignar.html', context, request
        ))

    def post(self, request, pk):
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)

        presidente_id = request.POST.get('presidente')
        secretario_id = request.POST.get('secretario')
        vocal_id = request.POST.get('vocal')
        suplente_id = request.POST.get('suplente')
        
        numero_oficio = request.POST.get('numero_oficio')
        fecha_acto = request.POST.get('fecha_acto')
        lugar_acto = request.POST.get('lugar_acto')

        if not all([presidente_id, secretario_id, vocal_id, suplente_id, numero_oficio, fecha_acto, lugar_acto]):
            messages.error(request, 'Debes llenar todos los campos (roles, oficio, fecha y lugar).')
            return redirect('administracion:jefe_jurado', pk=pk)

        if len({presidente_id, secretario_id, vocal_id, suplente_id}) < 4:
            messages.error(request, 'Los cuatro miembros del jurado deben ser personas diferentes.')
            return redirect('administracion:jefe_jurado', pk=pk)

        jurado, created = AsignacionJurado.objects.get_or_create(
            expediente=expediente,
            defaults={
                'presidente_id': presidente_id,
                'secretario_id': secretario_id,
                'vocal_propietario_id': vocal_id,
                'vocal_suplente_id': suplente_id,
                'numero_oficio': numero_oficio,
                'fecha_acto': fecha_acto,
                'lugar_acto': lugar_acto,
                'fecha_oficio': timezone.now().date(),
                'asignado_por': request.user,
            }
        )
        if not created:
            jurado.presidente_id = presidente_id
            jurado.secretario_id = secretario_id
            jurado.vocal_propietario_id = vocal_id
            jurado.vocal_suplente_id = suplente_id
            jurado.numero_oficio = numero_oficio
            jurado.fecha_acto = fecha_acto
            jurado.lugar_acto = lugar_acto
            jurado.fecha_oficio = timezone.now().date()
            jurado.asignado_por = request.user
            jurado.save()

        # Revisar si hay una solicitud de cambio de jefe pendiente (no mayor a 14 días)
        from administracion.models import SolicitudCambioJefe
        import datetime
        limite_fecha = timezone.now() - datetime.timedelta(days=14)
        
        solicitud_pendiente = SolicitudCambioJefe.objects.filter(
            departamento=request.user.departamento,
            estado='PENDIENTE',
            fecha_solicitud__gte=limite_fecha
        ).first()

        # Generar y guardar el PDF estático
        from administracion.pdf_oficio import generar_oficio_jurado_pdf
        from django.core.files.base import ContentFile
        
        pdf_bytes = generar_oficio_jurado_pdf(jurado, jefe_custom=solicitud_pendiente)
        filename = f'Oficio_Jurado_{expediente.alumno.username}.pdf'
        jurado.oficio_pdf.save(filename, ContentFile(pdf_bytes), save=False)
        
        if solicitud_pendiente:
            jurado.solicitud_jefe_usada = solicitud_pendiente
            
        jurado.save()

        messages.success(request, 'Asignación de jurado registrada exitosamente.')

        # Actualizar estado del expediente
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.JURADO_ASIGNADO,
            realizado_por=request.user,
            descripcion=f'Jurado asignado. Oficio {numero_oficio}. Acto: {fecha_acto} en {lugar_acto}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Jurado asignado para tu examen profesional',
            mensaje=f'Se ha asignado el jurado y fecha para tu acto protocolario. Fecha: {fecha_acto} en {lugar_acto}.',
        )

        # Enviar correos
        from django.core.mail import send_mail
        from django.conf import settings
        
        correos_destinos = [
            jurado.presidente.email,
            jurado.secretario.email,
            jurado.vocal_propietario.email,
            jurado.vocal_suplente.email,
            expediente.alumno.email
        ]
        correos_destinos = [c for c in correos_destinos if c]
        
        if correos_destinos:
            cuerpo = f'''Estimados Profesores y Alumno(a),

Se notifica que han sido designados como jurado para el acto de recepción profesional del alumno(a) {expediente.alumno.get_full_name()} ({expediente.alumno.carrera}).

Lugar: {lugar_acto}
Fecha y hora: {fecha_acto}

Jurado:
- Presidente: {jurado.presidente.get_nombre_con_titulo()}
- Secretario/a: {jurado.secretario.get_nombre_con_titulo()}
- Vocal Propietario/a: {jurado.vocal_propietario.get_nombre_con_titulo()}
- Vocal Suplente: {jurado.vocal_suplente.get_nombre_con_titulo()}

Instituto Tecnológico de Apizaco
'''
            send_mail(
                subject=f'{settings.EMAIL_SUBJECT_PREFIX}Oficio Asignación Jurado - {expediente.alumno.get_full_name()}',
                message=cuerpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=correos_destinos,
                fail_silently=True,
            )

        return redirect('administracion:jefe_detalle', pk=pk)


class DescargarOficioJuradoJefeView(JefeProyectoRequeridoMixin, View):
    """Descarga el PDF del Oficio de Asignación de Jurado."""
    def get(self, request, pk):
        user = request.user
        if user.departamento:
            filter_q = Q(alumno__carrera__departamento=user.departamento)
        else:
            filter_q = Q(alumno__carrera=user.carrera)

        expediente = get_object_or_404(Expediente, Q(pk=pk) & filter_q)
        asignacion = get_object_or_404(AsignacionJurado, expediente=expediente)

        if asignacion.oficio_pdf:
            response = HttpResponse(asignacion.oficio_pdf.read(), content_type='application/pdf')
        else:
            # Fallback en caso de que sea un registro viejo sin PDF generado
            from administracion.pdf_oficio import generar_oficio_jurado_pdf
            pdf_bytes = generar_oficio_jurado_pdf(asignacion)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            
        filename = f'Oficio_Jurado_{expediente.alumno.username}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class CalendarioJefeView(JefeProyectoRequeridoMixin, TemplateView):
    """Calendario de actos protocolarios para el Jefe de Proyecto."""
    template_name = 'administracion/jefe/calendario.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.departamento:
            ctx['carreras'] = Carrera.objects.filter(
                departamento=user.departamento, activa=True
            ).order_by('nombre')
        elif user.carrera:
            ctx['carreras'] = Carrera.objects.filter(
                pk=user.carrera_id, activa=True
            )
        else:
            ctx['carreras'] = Carrera.objects.filter(activa=True).order_by('nombre')
        return ctx


class EstadisticasJefeView(JefeProyectoRequeridoMixin, TemplateView):
    """
    Estadísticas de titulación para el Jefe de Proyecto (RE-01 a RE-07).
    Filtra por departamento del usuario.
    """
    template_name = 'administracion/jefe/estadisticas.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        departamento = user.departamento

        # ─── Base queryset por departamento ───────────────────────
        if departamento:
            qs_base = Expediente.objects.filter(
                alumno__carrera__departamento=departamento
            )
        else:
            qs_base = Expediente.objects.filter(
                alumno__carrera=user.carrera
            )

        qs = qs_base.select_related('alumno', 'modalidad')

        # ─── RE-01: Estudiantes que iniciaron proceso ──────────────
        total_expedientes = qs.count()

        # ─── RE-02: Estudiantes que concluyeron ────────────────────
        qs_concluidos = qs.filter(estado=EstadoExpediente.CONCLUIDO)
        total_concluidos = qs_concluidos.count()
        expedientes_activos = qs.exclude(
            estado__in=[EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO,
                        EstadoExpediente.BORRADOR]
        ).count()
        expedientes_cancelados = qs.filter(estado=EstadoExpediente.CANCELADO).count()

        porcentaje_titulados = round(
            (total_concluidos / total_expedientes * 100) if total_expedientes > 0 else 0, 1
        )

        # ─── RE-03: Estadísticas por género ───────────────────────
        # De todos los que iniciaron proceso
        iniciados_hombres = qs.filter(alumno__genero='M').count()
        iniciados_mujeres = qs.filter(alumno__genero='F').count()
        iniciados_sin_dato = total_expedientes - iniciados_hombres - iniciados_mujeres

        # De los titulados
        titulados_hombres = qs_concluidos.filter(alumno__genero='M').count()
        titulados_mujeres = qs_concluidos.filter(alumno__genero='F').count()
        titulados_sin_dato = total_concluidos - titulados_hombres - titulados_mujeres

        # ─── RE-04: Estadísticas por generación ───────────────────
        por_generacion = (
            qs.filter(alumno__generacion__isnull=False)
            .values('alumno__generacion')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
            )
            .order_by('-alumno__generacion')
        )

        # ─── RE-05: Por tipo de opción de titulación (modalidad) ──
        por_modalidad = (
            qs.filter(modalidad__isnull=False)
            .values('modalidad__nombre')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO))
            )
            .order_by('-total')
        )

        # ─── RE-06: Por carrera ────────────────────────────────────
        por_carrera = (
            qs.values('alumno__carrera__nombre')
            .annotate(
                total=Count('id'),
                concluidos=Count('id', filter=Q(estado=EstadoExpediente.CONCLUIDO)),
                hombres=Count('id', filter=Q(alumno__genero='M')),
                mujeres=Count('id', filter=Q(alumno__genero='F')),
            )
            .order_by('-total')
        )

        # ─── Distribución por estado (RE-07 apoyo decisiones) ─────
        estado_display = dict(EstadoExpediente.choices)
        expedientes_por_estado = [
            {
                'estado': estado_display.get(item['estado'], item['estado']),
                'total': item['total'],
                'clave': item['estado'],
            }
            for item in (
                qs.values('estado')
                .annotate(total=Count('id'))
                .order_by('-total')
            )
        ]

        ctx.update({
            'departamento': departamento,
            # RE-01
            'total_expedientes': total_expedientes,
            # RE-02
            'total_concluidos': total_concluidos,
            'expedientes_activos': expedientes_activos,
            'expedientes_cancelados': expedientes_cancelados,
            'porcentaje_titulados': porcentaje_titulados,
            # RE-03 género
            'iniciados_hombres': iniciados_hombres,
            'iniciados_mujeres': iniciados_mujeres,
            'iniciados_sin_dato': iniciados_sin_dato,
            'titulados_hombres': titulados_hombres,
            'titulados_mujeres': titulados_mujeres,
            'titulados_sin_dato': titulados_sin_dato,
            # RE-04 generación
            'por_generacion': por_generacion,
            # RE-05 modalidad
            'por_modalidad': por_modalidad,
            # RE-06 carrera
            'por_carrera': por_carrera,
            # RE-07 distribución
            'expedientes_por_estado': expedientes_por_estado,
        })
        return ctx


class ToggleConfirmacionJefeView(JefeProyectoRequeridoMixin, View):
    """POST — Jefe de proyecto confirma/quita confirmación de un miembro del jurado."""

    def post(self, request, pk):
        from expediente.models import ConfirmacionActo
        from expediente.views_confirmacion import (
            _enviar_correo_confirmacion_recibida,
            _enviar_correo_acto_confirmado,
        )
        from django.contrib import messages
        from django.utils import timezone

        confirmacion = get_object_or_404(ConfirmacionActo, pk=pk)
        acto = confirmacion.acto
        expediente = acto.expediente

        if not confirmacion.confirmado:
            confirmacion.confirmado = True
            confirmacion.fecha_confirmacion = timezone.now()
            confirmacion.save()
            messages.success(request, f'Asistencia de {confirmacion.nombre_participante} confirmada.')

            _enviar_correo_confirmacion_recibida(confirmacion, acto)

            # Si el Jefe de Proyectos confirma al alumno por él, se envían invitaciones al jurado
            if confirmacion.rol == 'ALUMNO':
                from expediente.views_confirmacion import _enviar_correos_invitacion_jurado
                _enviar_correos_invitacion_jurado(acto, request)
                messages.info(request, 'Al confirmar al alumno, se enviaron automáticamente las invitaciones al jurado.')

            if acto.confirmaciones_completas():
                _enviar_correo_acto_confirmado(acto)
                messages.info(request, '¡Todas las confirmaciones completas! Se envió correo final a todos.')
        else:
            confirmacion.confirmado = False
            confirmacion.fecha_confirmacion = None
            confirmacion.save()
            messages.warning(request, f'Se quitó la confirmación de {confirmacion.nombre_participante}.')

        return redirect('administracion:jefe_detalle', pk=expediente.pk)

class ActoProtocolarioView(JefeProyectoRequeridoMixin, CreateView):
    model = ActoProtocolario
    template_name = 'administracion/acto/programar.html'
    fields = ['fecha_acto', 'lugar', 'observaciones']

    def get_initial(self):
        initial = super().get_initial()
        initial['fecha_acto'] = timezone.now().date()
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        expediente = self.get_expediente()
        acto = ActoProtocolario.objects.filter(expediente=expediente).first()
        if acto:
            kwargs['instance'] = acto
        return kwargs

    def get_expediente(self):
        user = self.request.user
        queryset = Expediente.objects.filter(pk=self.kwargs['pk'])
        
        # Permitir a superusuarios ver cualquier expediente
        if not user.is_superuser:
            if user.departamento:
                queryset = queryset.filter(alumno__carrera__departamento=user.departamento)
            elif user.carrera:
                queryset = queryset.filter(alumno__carrera=user.carrera)
            # Si no tiene ni carrera ni depto y no es superuser, la consulta fallará (correcto)

        expediente = get_object_or_404(queryset)
        
        # Validar estado por separado para dar un mensaje más claro si falla
        if expediente.estado != EstadoExpediente.JURADO_ASIGNADO:
             # Esto lanzará 404 pero al menos sabemos que el expediente existe
             pass 
             
        return expediente


    def form_valid(self, form):
        from django.utils import timezone
        from datetime import timedelta
        fecha = form.cleaned_data.get('fecha_acto')
        if fecha and fecha < timezone.now() + timedelta(days=2):
            form.add_error('fecha_acto', 'El acto debe programarse con al menos 2 días de antelación.')
            return self.form_invalid(form)

        expediente = self.get_expediente()
        acto = form.save(commit=False)
        acto.expediente = expediente
        acto.jurado = expediente.jurado
        acto.resultado = 'PENDIENTE'
        acto.programado_por = self.request.user
        acto.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.ACTO_PROGRAMADO,
            realizado_por=self.request.user,
            descripcion=f'Acto protocolario programado para el {acto.fecha_acto} en {acto.lugar}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='¡Tu examen profesional está programado!',
            mensaje=f'Tu acto protocolario ha sido programado para el {acto.fecha_acto.strftime("%d/%m/%Y a las %H:%M")} en {acto.lugar}.',
        )

        # Crear confirmaciones y enviar correo SOLO al alumno inicialmente
        jurado = expediente.jurado
        if jurado:
            import secrets
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            from expediente.models import ConfirmacionActo

            participantes = [
                ('PRESIDENTE', jurado.presidente.get_nombre_corto(), jurado.presidente.email),
                ('SECRETARIO', jurado.secretario.get_nombre_corto(), jurado.secretario.email),
            ]
            if jurado.vocal_propietario:
                participantes.append(('VOCAL_PROPIETARIO', jurado.vocal_propietario.get_nombre_corto(), jurado.vocal_propietario.email))
            if jurado.vocal_suplente:
                participantes.append(('VOCAL_SUPLENTE', jurado.vocal_suplente.get_nombre_corto(), jurado.vocal_suplente.email))
            participantes.append(('ALUMNO', expediente.alumno.get_full_name(), expediente.alumno.email))

            fecha_fmt = acto.fecha_acto.strftime('%d de %B de %Y a las %H:%M')
            base_url = self.request.build_absolute_uri('/')[:-1]

            for rol, nombre, email in participantes:
                if not email:
                    continue
                token = secrets.token_urlsafe(48)
                ConfirmacionActo.objects.update_or_create(
                    acto=acto, rol=rol,
                    defaults={
                        'nombre_participante': nombre,
                        'email': email,
                        'token': token,
                        'confirmado': False,
                    }
                )
                
                # SOLO notificar al alumno en esta fase
                if rol == 'ALUMNO':
                    confirm_url = f'{base_url}/confirmar/{token}/'
                    html_body = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f8;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#0057B8,#003d82);border-radius:12px 12px 0 0;padding:30px;text-align:center;">
    <div style="font-size:36px;color:#fff;">&#x1F393;</div>
    <h2 style="color:#fff;margin:10px 0 5px;font-size:20px;">Acto Protocolario Programado</h2>
    <p style="color:rgba(255,255,255,.8);margin:0;font-size:13px;">Instituto Tecnol&oacute;gico de Apizaco &mdash; TecNM</p>
  </div>
  <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;color:#333;">Estimado(a) <strong>{nombre}</strong>,</p>
    <p style="font-size:14px;color:#555;">Se le informa que se ha asignado <strong style="color:#0057B8;">fecha y lugar</strong> para su acto de recepci&oacute;n profesional.</p>

    <div style="background:linear-gradient(135deg,#f0f7ff,#f3e8ff);border-radius:8px;padding:20px;margin:20px 0;text-align:center;">
      <div style="font-size:12px;color:#6c757d;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Fecha y lugar probable</div>
      <div style="font-size:20px;font-weight:700;color:#7c3aed;margin:8px 0;">{fecha_fmt}</div>
      <div style="font-size:14px;color:#555;">&#128205; {acto.lugar}</div>
    </div>

    <div style="background:#dbeafe;border-radius:8px;padding:20px;margin:20px 0;text-align:center;">
      <div style="font-size:14px;color:#1e40af;font-weight:700;margin-bottom:8px;">&#128232; Confirme su asistencia</div>
      <p style="font-size:13px;color:#333;margin:0;">
        Debe confirmar su asistencia con al menos <strong>24 horas de anticipaci&oacute;n</strong>. Ingrese a la Plataforma de Titulaci&oacute;n:
      </p>
      <a href="{confirm_url}" style="display:inline-block;margin-top:15px;padding:10px 20px;background:#0057B8;color:#fff;text-decoration:none;border-radius:5px;font-weight:bold;">Confirmar Asistencia</a>
    </div>

    <div style="background:#fef3c7;border-radius:8px;padding:12px 16px;font-size:12px;color:#92400e;">
      <strong>&#9888;&#65039; Importante:</strong> Si no confirma a tiempo, el acto no se notificar&aacute; al jurado y ser&aacute; cancelado/reprogramado.
    </div>
  </div>
</div>
</body></html>'''

                    text_body = (
                        f'Estimado(a) {nombre},\n\n'
                        f'Se le ha asignado fecha para su acto de recepción profesional.\n'
                        f'Fecha probable: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
                        f'ATENCIÓN: Debe confirmar su asistencia al menos 24 horas antes en el siguiente enlace:\n'
                        f'{confirm_url}\n\n'
                        f'Instituto Tecnológico de Apizaco — TecNM'
                    )

                    try:
                        msg = EmailMultiAlternatives(
                            subject=f'[ITA Titulación] Requiere Confirmación — Acto Protocolario',
                            body=text_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[email],
                        )
                        msg.attach_alternative(html_body, "text/html")
                        msg.send(fail_silently=True)
                    except Exception:
                        pass

        messages.success(self.request, 'Acto protocolario programado. Se ha enviado el correo de confirmación al alumno (El jurado será notificado cuando el alumno confirme).')
        return redirect('administracion:jefe_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expediente'] = self.get_expediente()
        return ctx


class ReprogramarActoView(JefeProyectoRequeridoMixin, View):
    """
    POST — Reprograma el acto protocolario cuando la fecha ya pasó
    y las confirmaciones de asistencia NO se completaron.
    """

    def post(self, request, pk):
        from expediente.models import ConfirmacionActo
        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings
        from django.http import Http404

        try:
            acto = get_object_or_404(ActoProtocolario, pk=pk)
            expediente = acto.expediente
        except Http404:
            # Si el acto no existe (quizás ya se borró), intentamos redirigir al dashboard
            messages.info(request, 'El acto ya no existe o ya fue reprogramado.')
            return redirect('administracion:jefe_dashboard')

        user = request.user
        
        # Security check
        if user.departamento:
            if expediente.alumno.carrera.departamento != user.departamento:
                messages.error(request, 'No tienes permiso para modificar este expediente.')
                return redirect('administracion:jefe_dashboard')
        elif expediente.alumno.carrera != user.carrera:
            messages.error(request, 'No tienes permiso para modificar este expediente.')
            return redirect('administracion:jefe_dashboard')


        if acto.fecha_acto > timezone.now():
            messages.error(request, 'No puedes reprogramar un acto cuya fecha aún no ha pasado.')
            return redirect('administracion:jefe_detalle', pk=expediente.pk)

        if acto.confirmaciones_completas():
            messages.error(request, 'No puedes reprogramar: todas las confirmaciones están completas. Registra el resultado.')
            return redirect('administracion:jefe_detalle', pk=expediente.pk)

        # Guardar datos para los correos antes de borrar
        fecha_anterior = acto.fecha_acto.strftime('%d/%m/%Y a las %H:%M')
        lugar_anterior = acto.lugar
        alumno_nombre = expediente.alumno.get_full_name()
        motivo = request.POST.get('motivo', 'No se completaron las confirmaciones de asistencia.')

        # Recopilar destinatarios
        destinatarios = []
        for conf in acto.confirmaciones.all():
            if conf.email:
                destinatarios.append((conf.nombre_participante, conf.email, conf.get_rol_display()))

        # Eliminar el acto (esto elimina en cascada las confirmaciones)
        acto.delete()

        # Regresar estado del expediente
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.JURADO_ASIGNADO,
            realizado_por=request.user,
            descripcion=f'Acto protocolario reprogramado. Motivo: {motivo}. Fecha anterior: {fecha_anterior}.'
        )

        notificar_alumno(
            expediente=expediente,
            tipo='INFO',
            titulo='Tu acto protocolario ha sido reprogramado',
            mensaje=f'El acto protocolario programado para el {fecha_anterior} en {lugar_anterior} ha sido reprogramado. Motivo: {motivo}. Recibirás una nueva notificación cuando se asigne la nueva fecha.',
        )

        # Enviar correos
        for nombre, email, rol_display in destinatarios:
            html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f8;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#dc3545,#b02a37);border-radius:12px 12px 0 0;padding:30px;text-align:center;">
    <div style="font-size:42px;color:#fff;">&#x1F504;</div>
    <h2 style="color:#fff;margin:10px 0 5px;font-size:20px;">Acto Protocolario Reprogramado</h2>
    <p style="color:rgba(255,255,255,.8);margin:0;font-size:13px;">Instituto Tecnol&oacute;gico de Apizaco &mdash; TecNM</p>
  </div>
  <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;color:#333;">Estimado(a) <strong>{nombre}</strong>,</p>
    <p style="font-size:14px;color:#555;">Le informamos que el acto protocolario en el que participar&iacute;a como
    <strong style="color:#dc3545;">{rol_display}</strong> ha sido <strong>reprogramado</strong>.</p>

    <div style="background:#fef2f2;border-radius:8px;padding:16px;margin:20px 0;border-left:4px solid #dc3545;">
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Alumno(a)</td>
            <td style="padding:6px 12px;font-size:14px;font-weight:700;">{alumno_nombre}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Fecha anterior</td>
            <td style="padding:6px 12px;font-size:14px;text-decoration:line-through;color:#dc3545;">{fecha_anterior}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Lugar anterior</td>
            <td style="padding:6px 12px;font-size:14px;">{lugar_anterior}</td></tr>
      </table>
    </div>

    <div style="background:#fff3cd;border-radius:8px;padding:14px 16px;font-size:13px;color:#856404;margin:20px 0;">
      <strong>&#9888;&#65039; Motivo:</strong> {motivo}
    </div>

    <p style="font-size:14px;color:#555;">
      Se le notificar&aacute; oportunamente cuando se asigne una <strong>nueva fecha y lugar</strong> para el acto protocolario.
    </p>
  </div>
  <p style="text-align:center;font-size:11px;color:#999;margin-top:16px;">
    Sistema de Gesti&oacute;n de Titulaci&oacute;n &mdash; TecNM / Instituto Tecnol&oacute;gico de Apizaco
  </p>
</div>
</body></html>"""

            text_body = (
                f'Estimado(a) {nombre},\n\n'
                f'El acto protocolario del alumno(a) {alumno_nombre} ha sido reprogramado.\n\n'
                f'Fecha anterior: {fecha_anterior}\n'
                f'Lugar: {lugar_anterior}\n'
                f'Motivo: {motivo}\n\n'
                f'Se le notificará cuando se asigne la nueva fecha.\n\n'
                f'Instituto Tecnológico de Apizaco — TecNM'
            )

            try:
                msg = EmailMultiAlternatives(
                    subject=f'[ITA Titulación] Acto Protocolario Reprogramado — {alumno_nombre}',
                    body=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=True)
            except Exception:
                pass

        messages.success(request, f'Acto protocolario reprogramado. Se notificó a {len(destinatarios)} participantes por correo.')
        return redirect('administracion:jefe_detalle', pk=expediente.pk)


class ConfirmarActoLlevadoAcaboJefeView(JefeProyectoRequeridoMixin, View):
    """Jefe de Proyecto confirma que el acto protocolario se llevó a cabo."""
    def post(self, request, pk):
        acto = get_object_or_404(ActoProtocolario, pk=pk)
        expediente = acto.expediente

        # Cambiar el resultado a APROBADO para indicar que ya se llevó a cabo
        acto.resultado = 'APROBADO'
        acto.save(update_fields=['resultado'])

        # Registrar el cambio en el historial
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion='El Jefe de Proyecto confirmó que el acto protocolario se llevó a cabo.'
        )

        # Notificar al alumno
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Acto Protocolario Concluido',
            mensaje='El Jefe de Proyecto ha confirmado la realización de tu acto protocolario. Tu expediente pasa a cargo de Servicios Escolares para continuar con el trámite.'
        )

        messages.success(request, 'Se ha confirmado la realización del acto protocolario. Servicios Escolares ya puede continuar con el trámite.')
        return redirect('administracion:jefe_detalle', pk=expediente.pk)



class SolicitarCambioJefeView(JefeProyectoRequeridoMixin, CreateView):
    model = SolicitudCambioJefe
    template_name = 'administracion/jefe_proyecto/solicitar_cambio.html'
    fields = ['titulo_academico_nuevo', 'nombre_nuevo', 'apellido_paterno_nuevo', 'apellido_materno_nuevo', 'genero_nuevo', 'motivo']
    success_url = reverse_lazy('administracion:jefe_dashboard')

    def form_valid(self, form):
        form.instance.departamento = self.request.user.departamento
        form.instance.solicitante = self.request.user
        messages.success(self.request, 'Solicitud de cambio de Jefe enviada al administrador. Se utilizarán estos datos para documentos urgentes mientras se revisa.')
        return super().form_valid(form)
