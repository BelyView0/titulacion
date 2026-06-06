import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "titulacion.settings")
django.setup()

from administracion.models import Usuario, Rol, Departamento, Carrera, JefeDepartamento, ConfiguracionInstitucional
from expediente.models import PlanEstudios, Modalidad, TipoDocumento

obj, created = ConfiguracionInstitucional.objects.get_or_create(
    id=1,
    defaults={anio_en_curso=2026, dominio_institucional='apizaco.tecnm.mx', imagen_encabezado=<ImageFieldFile: configuracion/Captura_de_pantalla_2026-04-23_171510.png>, imagen_pie_pagina=<ImageFieldFile: configuracion/Captura_de_pantalla_2026-04-23_180505.png>, ultima_actualizacion=1780533250.854532, permitir_jefe_proyectos_cambiar_jefe_departamento=False, nombre_institucion='Instituto Tecnológico de Apizaco', siglas='ITApizaco', logo_sistema=<ImageFieldFile: configuracion/tec_ita_RzhzJ5t.png>, mostrar_cintillo=True, imagen_cintillo=<ImageFieldFile: None>, color_header='#1b396a', color_menu='#003b73', color_botones='#0057b8', color_cintillo='#611232', email_host='smtp.gmail.com', email_port=587, email_use_tls=True, email_remitente='belyersua24@gmail.com', email_password='gAAAAABqG451IGHe56hquOkCO1FocuDB2qqd1YE6VGrw_lEkPVzBAOvTv359EY20739qr7GGmMMGi4CxwI0Pz0YsTjrEikpehgLr_BI6F3XPMgmstjU6de0='}
)

obj, created = Departamento.objects.get_or_create(
    clave='METAL',
    defaults={nombre='Metal Mecánica'}
)

obj, created = Departamento.objects.get_or_create(
    clave='ECON_ADM',
    defaults={nombre='Ciencias Económico-Administrativas'}
)

obj, created = Departamento.objects.get_or_create(
    clave='INDUSTRIAL',
    defaults={nombre='Ingeniería Industrial'}
)

obj, created = Departamento.objects.get_or_create(
    clave='ELEC_ELEC',
    defaults={nombre='Ingeniería Eléctrica y Electrónica'}
)

obj, created = Departamento.objects.get_or_create(
    clave='SISTEMAS',
    defaults={nombre='Sistemas y Computación'}
)

obj, created = Departamento.objects.get_or_create(
    clave='CIERRA',
    defaults={nombre='Ciencias de la Tierra'}
)

obj, created = Carrera.objects.get_or_create(
    clave='DCI',
    defaults={nombre='Doctorado en Ciencias de la Ingenieria', activa=True, departamento_id=6}
)

obj, created = Carrera.objects.get_or_create(
    clave='ICI',
    defaults={nombre='Ingeniera Civil', activa=True, departamento_id=1}
)

obj, created = Carrera.objects.get_or_create(
    clave='IEM',
    defaults={nombre='Ingenieria Electromecanica', activa=True, departamento_id=2}
)

obj, created = Carrera.objects.get_or_create(
    clave='IEL',
    defaults={nombre='Ingenieria Electronica', activa=True, departamento_id=5}
)

obj, created = Carrera.objects.get_or_create(
    clave='IAD',
    defaults={nombre='Ingenieria en Administracion', activa=True, departamento_id=3}
)

obj, created = Carrera.objects.get_or_create(
    clave='IGE',
    defaults={nombre='Ingenieria en Gestion Empresarial', activa=True, departamento_id=3}
)

obj, created = Carrera.objects.get_or_create(
    clave='IIA',
    defaults={nombre='Ingenieria en Inteligencia Artificial', activa=True, departamento_id=6}
)

obj, created = Carrera.objects.get_or_create(
    clave='ISC',
    defaults={nombre='Ingenieria en Semiconductores', activa=True, departamento_id=5}
)

obj, created = Carrera.objects.get_or_create(
    clave='ISA',
    defaults={nombre='Ingenieria en Sistemas Automotrices', activa=True, departamento_id=5}
)

obj, created = Carrera.objects.get_or_create(
    clave='ITC',
    defaults={nombre='Ingenieria en Tecnologias de la Informacion y Comunicaciones', activa=True, departamento_id=6}
)

obj, created = Carrera.objects.get_or_create(
    clave='IID',
    defaults={nombre='Ingenieria Industrial', activa=True, departamento_id=4}
)

obj, created = Carrera.objects.get_or_create(
    clave='IIN',
    defaults={nombre='Ingenieria Informatica', activa=True, departamento_id=6}
)

obj, created = Carrera.objects.get_or_create(
    clave='IME',
    defaults={nombre='Ingenieria Mecatronica', activa=True, departamento_id=2}
)

obj, created = Carrera.objects.get_or_create(
    clave='MIA',
    defaults={nombre='Maestria en Ingenieria Administrativa', activa=True, departamento_id=3}
)

obj, created = Carrera.objects.get_or_create(
    clave='MIM',
    defaults={nombre='Maestria en Ingenieria Mecatronica', activa=True, departamento_id=2}
)

obj, created = Carrera.objects.get_or_create(
    clave='MSC',
    defaults={nombre='Maestria en Sistemas Computacionales', activa=True, departamento_id=6}
)

obj, created = Usuario.objects.get_or_create(
    username='escolares',
    defaults={email='belyersua24@gmail.com', rol='ESCOLARES', numero_control='escolares', telefono='2411721355', genero='M', generacion=2017, foto_perfil=<ImageFieldFile: None>, first_name='Marcos Manuel', last_name='Díaz', apellido_materno='Meza', debe_cambiar_password=False, correo_institucional='l21370903@apizaco.tecnm.mx', correo_institucional_verificado=False, email_verificado=True}
)
if created: obj.set_password('Temporal123!'); obj.save()

obj, created = Usuario.objects.get_or_create(
    username='academico',
    defaults={email='belyersua24@gmail.com', rol='ACADEMICO', numero_control='academico', telefono='2411721355', genero='M', generacion=2021, foto_perfil=<ImageFieldFile: None>, first_name='Roberto', last_name='Torres', apellido_materno='Marquéz', debe_cambiar_password=False, correo_institucional='l21370903@apizaco.tecnm.mx', correo_institucional_verificado=False, email_verificado=False}
)
if created: obj.set_password('Temporal123!'); obj.save()

obj, created = Usuario.objects.get_or_create(
    username='jefe_proy',
    defaults={email='belyersua24@gmail.com', rol='JEFE_PROYECTO', numero_control='jefe_proy', telefono='2411721355', genero='F', generacion=2021, foto_perfil=<ImageFieldFile: None>, first_name='María del Rocio', last_name='Ojeda', apellido_materno='Lopéz', departamento_id=6, debe_cambiar_password=False, correo_institucional='l21370903@apizaco.tecnm.mx', correo_institucional_verificado=True, email_verificado=False}
)
if created: obj.set_password('Temporal123!'); obj.save()

obj, created = PlanEstudios.objects.get_or_create(
    nombre='Plan 2010',
    defaults={descripcion='', activo=True}
)

obj, created = PlanEstudios.objects.get_or_create(
    nombre='2009-2010',
    defaults={descripcion='', activo=True}
)

obj, created = PlanEstudios.objects.get_or_create(
    nombre='2004',
    defaults={descripcion='', activo=True}
)

obj, created = PlanEstudios.objects.get_or_create(
    nombre='1993',
    defaults={descripcion='', activo=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='',
    defaults={plan_estudios_id=13, nombre='Tesis', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='PROYECTO',
    defaults={plan_estudios_id=1, nombre='Proyecto de Investigacion', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='TESIS',
    defaults={plan_estudios_id=1, nombre='Tesis Profesional', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='RESIDENCIA',
    defaults={plan_estudios_id=1, nombre='Titulacion Integral - Residencia Profesional', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='EGEL',
    defaults={plan_estudios_id=1, nombre='Titulacion Integral por EGEL', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='EGEL_2004',
    defaults={plan_estudios_id=2, nombre='EGAC Plan 2004', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='PROMEDIO_2004',
    defaults={plan_estudios_id=2, nombre='Escolaridad por Promedio Plan 2004', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='PROYECTO_2004',
    defaults={plan_estudios_id=2, nombre='Proyecto de Investigacion Plan 2004', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='RESIDENCIA_2004',
    defaults={plan_estudios_id=2, nombre='Residencia Profesional Plan 2004', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='TESIS_2004',
    defaults={plan_estudios_id=2, nombre='Tesis Profesional Plan 2004', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='DISENO_1993',
    defaults={plan_estudios_id=3, nombre='Diseño o Rediseño de Equipo, Aparato o Maquinaria (Plan 1993)', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='PROMEDIO_1993',
    defaults={plan_estudios_id=3, nombre='Escolaridad por Promedio Plan 1993', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='EGAL_1993',
    defaults={plan_estudios_id=3, nombre='Examen Global por Áreas de Conocimiento (Plan 1993)', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='LIBRO_1993',
    defaults={plan_estudios_id=3, nombre='Libros de Texto o Prototipos Didácticos (Plan 1993)', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='MEMORIA_1993',
    defaults={plan_estudios_id=3, nombre='Memoria de Experiencia Profesional (Plan 1993)', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='PROYECTO_1993',
    defaults={plan_estudios_id=3, nombre='Proyecto de Investigación (Plan 1993)', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='RESIDENCIA_1993',
    defaults={plan_estudios_id=3, nombre='Residencia Profesional Plan 1993', descripcion='', activa=True}
)

obj, created = Modalidad.objects.get_or_create(
    clave='TESIS_1993',
    defaults={plan_estudios_id=3, nombre='Tesis Profesional Plan 1993', descripcion='', activa=True}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud del Estudiante',
    defaults={modalidad_id=2, descripcion_ayuda='Descargar y llenar en computadora.', es_obligatorio=True, orden=1, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud de Acto de Recepción Profesional',
    defaults={modalidad_id=2, descripcion_ayuda='Descargar del sitio oficial, llenar en computadora. Nombre: NúmControl_solicitud_acto.pdf', es_obligatorio=True, orden=2, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud de Opción de Titulación',
    defaults={modalidad_id=2, descripcion_ayuda='Formato para Servicios Escolares. Llenar en computadora con datos correctos. Nombre: NúmControl_solicitud_opcion.pdf', es_obligatorio=True, orden=3, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Acta de Nacimiento',
    defaults={modalidad_id=2, descripcion_ayuda='Original escaneado por ambos lados. Vigencia: debe ser del mismo mes en el que se abre el expediente. Nombre: NúmControl_acta_nacimiento.pdf', es_obligatorio=True, orden=4, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberacion de Residencia Profesional',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por Division de Estudios.', es_obligatorio=True, orden=5, valida_division=True, valida_escolares=False, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Acreditacion del Idioma Ingles',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por Coordinacion de Lenguas del ITA.', es_obligatorio=True, orden=6, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberacion de Proyecto para Titulacion Integral',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por depto academico una vez aprobada la tesis.', es_obligatorio=True, orden=7, valida_division=True, valida_escolares=False, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberación de Servicio Social',
    defaults={modalidad_id=2, descripcion_ayuda='Original escaneado. Nombre: NúmControl_liberacion_servicio_social.pdf', es_obligatorio=True, orden=8, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberación de Residencia Profesional',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por la División de Estudios Profesionales al concluir tu residencia aprobada. Nombre: NúmControl_liberacion_residencia.pdf', es_obligatorio=True, orden=9, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Acreditación del Idioma Inglés',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por la Coordinación de Lenguas Extranjeras del ITA. Nombre: NúmControl_acreditacion_ingles.pdf', es_obligatorio=True, orden=10, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Equivalencia, Revalidación o Convalidación',
    defaults={modalidad_id=2, descripcion_ayuda='Original escaneado (solo en caso de que aplique). Nombre: NúmControl_equivalencia.pdf', es_obligatorio=False, orden=11, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Constancia de No Adeudos',
    defaults={modalidad_id=2, descripcion_ayuda='Original escaneado, solicitado en División de Estudios Profesionales. Nombre: NúmControl_no_adeudos.pdf', es_obligatorio=True, orden=12, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Constancia de No Inconveniencia (Empresa)',
    defaults={modalidad_id=2, descripcion_ayuda='Emitida por la empresa/organismo. En papel membretado, firmada y sellada, dirigida al Director del ITA. Nombre: NúmControl_no_inconveniencia.pdf', es_obligatorio=True, orden=13, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Oficio de Autorización de Publicación',
    defaults={modalidad_id=2, descripcion_ayuda='Documento entregado por División de Estudios Profesionales. Nombre: NúmControl_autorizacion_publicacion.pdf', es_obligatorio=True, orden=14, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Oficio de Liberación de Proyecto para Titulación Integral',
    defaults={modalidad_id=2, descripcion_ayuda='Emitido por el departamento académico una vez que la tesis esté concluida y aprobada.', es_obligatorio=True, orden=15, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Fotografía óvalo en blanco y negro con adhesivo',
    defaults={modalidad_id=2, descripcion_ayuda='Fotografía óvalo en blanco y negro con pega. Se entrega físicamente en División de Estudios y Servicios Escolares. Cargar aquí versión digital.', es_obligatorio=True, orden=16, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=True}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud del Estudiante 2009-2010',
    defaults={modalidad_id=1, descripcion_ayuda='Descargar del sitio oficial (https://www.apizaco.tecnm.mx/proceso-titulacion/), llenar en computadora. Nombre: NúmControl_solicitud_estudiante.pdf', es_obligatorio=True, orden=1, valida_division=True, valida_escolares=False, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud de Acto de Recepción Profesional',
    defaults={modalidad_id=1, descripcion_ayuda='Descargar del sitio oficial, llenar en computadora. Nombre: NúmControl_solicitud_acto.pdf', es_obligatorio=True, orden=2, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Solicitud de Opción de Titulación',
    defaults={modalidad_id=1, descripcion_ayuda='Formato para Servicios Escolares. Llenar en computadora con datos correctos. Nombre: NúmControl_solicitud_opcion.pdf', es_obligatorio=True, orden=3, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Acta de Nacimiento',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado por ambos lados. Vigencia: debe ser del mismo mes en el que se abre el expediente. Nombre: NúmControl_acta_nacimiento.pdf', es_obligatorio=True, orden=4, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='CURP',
    defaults={modalidad_id=1, descripcion_ayuda='Descargada del portal oficial de internet (en el mes que se abre el expediente). Nombre: NúmControl_curp.pdf', es_obligatorio=True, orden=5, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Certificado de Estudios de Bachillerato',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado por ambos lados. Nombre: NúmControl_certificado_bachillerato.pdf', es_obligatorio=True, orden=6, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Certificado de Estudios de Licenciatura',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado por ambos lados. Nombre: NúmControl_certificado_licenciatura.pdf', es_obligatorio=True, orden=7, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberación de Servicio Social',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado. Nombre: NúmControl_liberacion_servicio_social.pdf', es_obligatorio=True, orden=8, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Liberación de Residencia Profesional',
    defaults={modalidad_id=1, descripcion_ayuda='Emitido por la División de Estudios Profesionales al concluir tu residencia aprobada. Nombre: NúmControl_liberacion_residencia.pdf', es_obligatorio=True, orden=9, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Acreditación del Idioma Inglés',
    defaults={modalidad_id=1, descripcion_ayuda='Emitido por la Coordinación de Lenguas Extranjeras del ITA. Nombre: NúmControl_acreditacion_ingles.pdf', es_obligatorio=True, orden=10, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Equivalencia, Revalidación o Convalidación',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado (solo en caso de que aplique). Nombre: NúmControl_equivalencia.pdf', es_obligatorio=False, orden=11, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Constancia de No Adeudos',
    defaults={modalidad_id=1, descripcion_ayuda='Original escaneado, solicitado en División de Estudios Profesionales. Nombre: NúmControl_no_adeudos.pdf', es_obligatorio=True, orden=12, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Constancia de No Inconveniencia (Empresa)',
    defaults={modalidad_id=1, descripcion_ayuda='Emitida por la empresa/organismo. En papel membretado, firmada y sellada, dirigida al Director del ITA. Nombre: NúmControl_no_inconveniencia.pdf', es_obligatorio=True, orden=13, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Oficio de Autorización de Publicación',
    defaults={modalidad_id=1, descripcion_ayuda='Documento entregado por División de Estudios Profesionales. Nombre: NúmControl_autorizacion_publicacion.pdf', es_obligatorio=True, orden=14, valida_division=False, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Oficio de Liberación de Proyecto para Titulación Integral',
    defaults={modalidad_id=1, descripcion_ayuda='Emitido por el departamento académico correspondiente. Nombre: NúmControl_liberacion_proyecto.pdf', es_obligatorio=True, orden=15, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=False}
)

obj, created = TipoDocumento.objects.get_or_create(
    nombre='Fotografía óvalo en blanco y negro con adhesivo',
    defaults={modalidad_id=1, descripcion_ayuda='Fotografía óvalo en blanco y negro con pega. Se entrega físicamente en División de Estudios y Servicios Escolares. Cargar aquí versión digital.', es_obligatorio=True, orden=16, valida_division=True, valida_escolares=True, acepta_solo_pdf=True, es_fotografia=True}
)

print('Datos importados correctamente. Las contraseñas de los usuarios nuevos son Temporal123!')
