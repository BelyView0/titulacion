"""
Script de datos iniciales (fixtures) para el sistema.
Crea: Planes de Estudios, Modalidades, Tipos de Documentos, Carreras.
Basado en la información oficial del ITA: https://www.apizaco.tecnm.mx/proceso-titulacion/

Uso: python manage.py shell < fixtures/datos_iniciales.py
  o: python fixtures/datos_iniciales.py (si se ejecuta en el shell)
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'titulacion.settings')
django.setup()

from expediente.models import PlanEstudios, Modalidad, TipoDocumento
from administracion.models import Carrera

print("=== Iniciando carga de datos del ITA ===\n")

# ─── CARRERAS ─────────────────────────────────────────────────────────────────
carreras_data = [
    ('ICI', 'Ingeniería Civil'),
    ('IEM', 'Ingeniería Electromecánica'),
    ('IEL', 'Ingeniería Electrónica'),
    ('IAD', 'Ingeniería en Administración'),
    ('IGE', 'Ingeniería en Gestión Empresarial'),
    ('IIN', 'Ingeniería Informática'),
    ('ITC', 'Ingeniería en Tecnologías de la Información y Comunicaciones'),
    ('IID', 'Ingeniería Industrial'),
    ('IME', 'Ingeniería Mecatrónica'),
    ('ISA', 'Ingeniería en Sistemas Automotrices'),
    ('IIA', 'Ingeniería en Inteligencia Artificial'),
    ('ISC', 'Ingeniería en Semiconductores'),
    ('MIA', 'Maestría en Ingeniería Administrativa'),
    ('MSC', 'Maestría en Sistemas Computacionales'),
    ('MIM', 'Maestría en Ingeniería Mecatrónica'),
    ('DCI', 'Doctorado en Ciencias de la Ingeniería'),
]

for clave, nombre in carreras_data:
    carrera, created = Carrera.objects.get_or_create(clave=clave, defaults={'nombre': nombre})
    if created:
        print(f"  ✓ Carrera: {nombre}")

print(f"\n  → {Carrera.objects.count()} carreras cargadas.\n")

# ─── PLANES DE ESTUDIO ────────────────────────────────────────────────────────
planes_data = [
    ('2009-2010', 'Plan vigente para nuevas generaciones (2009-2010)'),
    ('2004', 'Plan 2004'),
    ('1993', 'Plan 1993'),
    ('POSGRADO', 'Plan Posgrado (Maestría / Doctorado)'),
]

planes = {}
for nombre, desc in planes_data:
    plan, created = PlanEstudios.objects.get_or_create(
        nombre=nombre, defaults={'descripcion': desc}
    )
    planes[nombre] = plan
    if created:
        print(f"  ✓ Plan de Estudios: {nombre}")

# ─── MODALIDADES ─────────────────────────────────────────────────────────────
modalidades_data = [
    # Plan 2009-2010
    ('2009-2010', 'RESIDENCIA', 'Titulación Integral — Informe de Residencia Profesional'),
    ('2009-2010', 'TESIS', 'Tesis Profesional'),
    ('2009-2010', 'PROYECTO', 'Proyecto de Investigación'),
    ('2009-2010', 'EGEL', 'Titulación Integral por EGEL (CENEVAL)'),
    # Plan 2004
    ('2004', 'TESIS_2004', 'Tesis Profesional (Plan 2004)'),
    ('2004', 'PROYECTO_2004', 'Proyecto de Investigación (Plan 2004)'),
    ('2004', 'EGEL_2004', 'Examen Global por Áreas de Conocimiento EGAC (Plan 2004)'),
    ('2004', 'PROMEDIO_2004', 'Escolaridad por Promedio (Plan 2004)'),
    ('2004', 'RESIDENCIA_2004', 'Informe de Residencia Profesional (Plan 2004)'),
    # Plan 1993
    ('1993', 'TESIS_1993', 'Tesis Profesional (Plan 1993)'),
    ('1993', 'LIBRO_1993', 'Libros de Texto o Prototipos Didácticos (Plan 1993)'),
    ('1993', 'PROYECTO_1993', 'Proyecto de Investigación (Plan 1993)'),
    ('1993', 'DISENO_1993', 'Diseño o Rediseño de Equipo, Aparato o Maquinaria (Plan 1993)'),
    ('1993', 'EGAL_1993', 'Examen Global por Áreas de Conocimiento (Plan 1993)'),
    ('1993', 'MEMORIA_1993', 'Memoria de Experiencia Profesional (Plan 1993)'),
    ('1993', 'PROMEDIO_1993', 'Escolaridad por Promedio (Plan 1993)'),
    ('1993', 'POSGRADO_1993', 'Escolaridad por Estudios de Posgrado (Plan 1993)'),
    ('1993', 'RESIDENCIA_1993', 'Memoria de Residencia Profesional (Plan 1993)'),
    # Posgrado
    ('POSGRADO', 'TESIS_POSGRADO', 'Tesis de Posgrado (Maestría/Doctorado)'),
]

modalidades = {}
for plan_nombre, clave, nombre in modalidades_data:
    modal, created = Modalidad.objects.get_or_create(
        clave=clave,
        defaults={'plan_estudios': planes[plan_nombre], 'nombre': nombre}
    )
    modalidades[clave] = modal
    if created:
        print(f"  ✓ Modalidad: {nombre}")

# ─── TIPOS DE DOCUMENTOS — Plan 2009-2010 ─────────────────────────────────────
# Documentos para Residencia Profesional (Plan 2009-2010)
docs_residencia = [
    (1, 'Solicitud del Estudiante',
     'Descargar del sitio oficial, llenar en computadora con tinta negra. Nombre: NúmControl_solicitud_estudiante.pdf',
     True, True, True, False),
    (2, 'Solicitud de Acto de Recepción Profesional',
     'Descargar del sitio oficial, llenar en computadora. Nombre: NúmControl_solicitud_acto.pdf',
     True, True, True, False),
    (3, 'Constancia de No Inconveniencia',
     'Emitida por la empresa/organismo donde realizó la residencia. En papel membretado, firmada y sellada, dirigida al Director del ITA. '
     'Debe incluir: nombre completo, N° control, carrera, nombre del proyecto y período. Nombre: NúmControl_no_inconveniencia.pdf',
     True, True, True, False),
    (4, 'Oficio de Liberación de Proyecto para Titulación Integral',
     'Emitido por el departamento académico correspondiente. Solicitar en División de Estudios Profesionales.',
     True, True, True, False),
    (5, 'Certificado de Estudios de Licenciatura',
     'El certificado recibido con tu documentación oficial de egreso. Nombre: NúmControl_certificado_estudios.pdf',
     True, True, True, False),
    (6, 'Liberación de Residencia Profesional',
     'Emitido por la División de Estudios Profesionales al concluir tu residencia aprobada.',
     True, True, False, False),
    (7, 'Acreditación del Idioma Inglés',
     'Emitido por la Coordinación de Lenguas Extranjeras del ITA. Nombre: NúmControl_acreditacion_ingles.pdf',
     True, True, True, False),
    (8, 'Fotografía óvalo en blanco y negro con adhesivo',
     'Fotograf\u00eda \u00f3valo en blanco y negro con pega. Se entrega físicamente en División de Estudios. '
     'Cargar aquí la fotografía digital en formato JPG/PNG.',
     True, True, False, True),
]

for orden, nombre, desc, obligatorio, val_div, val_esc, es_foto in docs_residencia:
    TipoDocumento.objects.get_or_create(
        modalidad=modalidades['RESIDENCIA'],
        nombre=nombre,
        defaults={
            'descripcion_ayuda': desc,
            'es_obligatorio': obligatorio,
            'orden': orden,
            'valida_division': val_div,
            'valida_escolares': val_esc,
            'es_fotografia': es_foto,
        }
    )
print(f"  ✓ Documentos para Residencia Profesional 2009-2010 cargados.")

# Documentos para Tesis (Plan 2009-2010)
docs_tesis = [
    (1, 'Solicitud del Estudiante', docs_residencia[0][2], True, True, True, False),
    (2, 'Solicitud de Acto de Recepción Profesional', docs_residencia[1][2], True, True, True, False),
    (3, 'Contenido del Proyecto de Tesis',
     'Debe incluir: portada, índice detallado, introducción, justificación y bibliografía. '
     'En formato PDF. Nombre: NúmControl_contenido_proyecto.pdf',
     True, True, False, False),
    (4, 'Certificado de Estudios de Licenciatura', docs_residencia[4][2], True, True, True, False),
    (5, 'Liberación de Residencia Profesional', docs_residencia[5][2], True, True, False, False),
    (6, 'Acreditación del Idioma Inglés', docs_residencia[6][2], True, True, True, False),
    (7, 'Liberación de Proyecto para Titulación Integral (Tesis)',
     'Emitido por el departamento académico una vez que la tesis esté concluida y aprobada.',
     True, True, False, False),
    (8, 'Fotografía óvalo en blanco y negro con adhesivo', docs_residencia[7][2], True, True, False, True),
]

for orden, nombre, desc, obligatorio, val_div, val_esc, es_foto in docs_tesis:
    TipoDocumento.objects.get_or_create(
        modalidad=modalidades['TESIS'],
        nombre=nombre,
        defaults={
            'descripcion_ayuda': desc,
            'es_obligatorio': obligatorio,
            'orden': orden,
            'valida_division': val_div,
            'valida_escolares': val_esc,
            'es_fotografia': es_foto,
        }
    )
print(f"  ✓ Documentos para Tesis 2009-2010 cargados.")

print(f"\n=== Carga completada ===")
print(f"  • Carreras: {Carrera.objects.count()}")
print(f"  • Planes de estudio: {PlanEstudios.objects.count()}")
print(f"  • Modalidades: {Modalidad.objects.count()}")
print(f"  • Tipos de documentos: {TipoDocumento.objects.count()}")
