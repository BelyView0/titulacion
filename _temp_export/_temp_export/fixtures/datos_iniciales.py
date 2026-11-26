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
from administracion.models import Carrera, Departamento

print("=== Iniciando carga de datos del ITA ===\n")
departamentos_data = [
    ('CIERRA', 'Ciencias de la Tierra'),
    ('METAL', 'Metal Mecánica'),
    ('ECON_ADM', 'Ciencias Económico-Administrativas'),
    ('INDUSTRIAL', 'Ingeniería Industrial'),
    ('ELEC_ELEC', 'Ingeniería Eléctrica y Electrónica'),
    ('SISTEMAS', 'Sistemas y Computación'),
]

departamentos = {}
for clave, nombre in departamentos_data:
    dept, created = Departamento.objects.get_or_create(clave=clave, defaults={'nombre': nombre})
    departamentos[clave] = dept
    if created:
        print(f"  [OK] Departamento: {nombre}")

# --- CARRERAS -----------------------------------------------------------------
# (Clave, Nombre, Clave_Departamento)
carreras_data = [
    # Ciencias de la Tierra
    ('ICI', 'Ingeniera Civil', 'CIERRA'),
    
    # Metal Mecánica
    ('IEM', 'Ingenieria Electromecanica', 'METAL'),
    ('IME', 'Ingenieria Mecatronica', 'METAL'),
    ('MIM', 'Maestria en Ingenieria Mecatronica', 'METAL'),
    
    # Ciencias Económico-Administrativas
    ('IAD', 'Ingenieria en Administracion', 'ECON_ADM'),
    ('IGE', 'Ingenieria en Gestion Empresarial', 'ECON_ADM'),
    ('MIA', 'Maestria en Ingenieria Administrativa', 'ECON_ADM'),
    
    # Ingeniería Industrial
    ('IID', 'Ingenieria Industrial', 'INDUSTRIAL'),
    
    # Ingeniería Eléctrica y Electrónica
    ('IEL', 'Ingenieria Electronica', 'ELEC_ELEC'),
    ('ISC', 'Ingenieria en Semiconductores', 'ELEC_ELEC'),
    ('ISA', 'Ingenieria en Sistemas Automotrices', 'ELEC_ELEC'),
    
    # Sistemas y Computación
    ('IIN', 'Ingenieria Informatica', 'SISTEMAS'),
    ('ITC', 'Ingenieria en Tecnologias de la Informacion y Comunicaciones', 'SISTEMAS'),
    ('IIA', 'Ingenieria en Inteligencia Artificial', 'SISTEMAS'),
    ('MSC', 'Maestria en Sistemas Computacionales', 'SISTEMAS'),
    ('DCI', 'Doctorado en Ciencias de la Ingenieria', 'SISTEMAS'),
]

for clave, nombre, dept_clave in carreras_data:
    carrera, created = Carrera.objects.update_or_create(
        clave=clave, 
        defaults={
            'nombre': nombre,
            'departamento': departamentos[dept_clave]
        }
    )
    if created:
        print(f"  [OK] Carrera: {nombre}")

print(f"\n  -> {Carrera.objects.count()} carreras vinculadas a {Departamento.objects.count()} departamentos.\n")

# --- PLANES DE ESTUDIO --------------------------------------------------------
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
        print(f"  [OK] Plan de Estudios: {nombre}")

# --- MODALIDADES --------------------------------------------------------------
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
        print(f"  [OK] Modalidad: {nombre}")

# --- TIPOS DE DOCUMENTOS --- Plan 2009-2010 -----------------------------------
# Documentos para Residencia Profesional (Plan 2009-2010)
# Orden, Nombre, Descripción, Obligatorio, ValidaDiv, ValidaEsc, EsFoto
docs_residencia = [
    (1, 'Solicitud del Estudiante 2009-2010',
     'Descargar del sitio oficial (https://www.apizaco.tecnm.mx/proceso-titulacion/), llenar en computadora. Nombre: NúmControl_solicitud_estudiante.pdf',
     True, True, False, False),
    (2, 'Solicitud de Acto de Recepción Profesional',
     'Descargar del sitio oficial, llenar en computadora. Nombre: NúmControl_solicitud_acto.pdf',
     True, True, True, False),
    (3, 'Solicitud de Opción de Titulación',
     'Formato para Servicios Escolares. Llenar en computadora con datos correctos. Nombre: NúmControl_solicitud_opcion.pdf',
     True, True, True, False),
    (4, 'Acta de Nacimiento',
     'Original escaneado por ambos lados. Vigencia: debe ser del mismo mes en el que se abre el expediente. Nombre: NúmControl_acta_nacimiento.pdf',
     True, False, True, False),
    (5, 'CURP',
     'Descargada del portal oficial de internet (en el mes que se abre el expediente). Nombre: NúmControl_curp.pdf',
     True, False, True, False),
    (6, 'Certificado de Estudios de Bachillerato',
     'Original escaneado por ambos lados. Nombre: NúmControl_certificado_bachillerato.pdf',
     True, False, True, False),
    (7, 'Certificado de Estudios de Licenciatura',
     'Original escaneado por ambos lados. Nombre: NúmControl_certificado_licenciatura.pdf',
     True, True, True, False),
    (8, 'Liberación de Servicio Social',
     'Original escaneado. Nombre: NúmControl_liberacion_servicio_social.pdf',
     True, False, True, False),
    (9, 'Liberación de Residencia Profesional',
     'Emitido por la División de Estudios Profesionales al concluir tu residencia aprobada. Nombre: NúmControl_liberacion_residencia.pdf',
     True, True, True, False),
    (10, 'Acreditación del Idioma Inglés',
     'Emitido por la Coordinación de Lenguas Extranjeras del ITA. Nombre: NúmControl_acreditacion_ingles.pdf',
     True, True, True, False),
    (11, 'Equivalencia, Revalidación o Convalidación',
     'Original escaneado (solo en caso de que aplique). Nombre: NúmControl_equivalencia.pdf',
     False, False, True, False),
    (12, 'Constancia de No Adeudos',
     'Original escaneado, solicitado en División de Estudios Profesionales. Nombre: NúmControl_no_adeudos.pdf',
     True, False, True, False),
    (13, 'Constancia de No Inconveniencia (Empresa)',
     'Emitida por la empresa/organismo. En papel membretado, firmada y sellada, dirigida al Director del ITA. Nombre: NúmControl_no_inconveniencia.pdf',
     True, True, True, False),
    (14, 'Oficio de Autorización de Publicación',
     'Documento entregado por División de Estudios Profesionales. Nombre: NúmControl_autorizacion_publicacion.pdf',
     True, False, True, False),
    (15, 'Oficio de Liberación de Proyecto para Titulación Integral',
     'Emitido por el departamento académico correspondiente. Nombre: NúmControl_liberacion_proyecto.pdf',
     True, True, True, False),
    (16, 'Fotografía óvalo en blanco y negro con adhesivo',
     'Fotografía óvalo en blanco y negro con pega. Se entrega físicamente en División de Estudios y Servicios Escolares. Cargar aquí versión digital.',
     True, True, True, True),
]

for orden, nombre, desc, obligatorio, val_div, val_esc, es_foto in docs_residencia:
    TipoDocumento.objects.update_or_create(
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
print(f"  [OK] 16 Documentos para Residencia Profesional 2009-2010 actualizados.")

for orden, nombre, desc, obligatorio, val_div, val_esc, es_foto in docs_residencia:
    nombre_final = nombre
    desc_final = desc
    if nombre == 'Oficio de Liberación de Proyecto para Titulación Integral':
        desc_final = 'Emitido por el departamento académico una vez que la tesis esté concluida y aprobada.'

    TipoDocumento.objects.update_or_create(
        modalidad=modalidades['TESIS'],
        nombre=nombre_final,
        defaults={
            'descripcion_ayuda': desc_final,
            'es_obligatorio': obligatorio,
            'orden': orden,
            'valida_division': val_div,
            'valida_escolares': val_esc,
            'es_fotografia': es_foto,
        }
    )
print(f"  [OK] 16 Documentos para Tesis 2009-2010 actualizados.")

print(f"\n=== Carga completada ===")
print(f"  * Carreras: {Carrera.objects.count()}")
print(f"  * Planes de estudio: {PlanEstudios.objects.count()}")
print(f"  * Modalidades: {Modalidad.objects.count()}")
print(f"  * Tipos de documentos: {TipoDocumento.objects.count()}")
