import re

with open('administracion/export_views.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace JefeProyectoRequeridoMixin with OficinaTitulacionRequeridoMixin
code = code.replace('JefeProyectoRequeridoMixin', 'OficinaTitulacionRequeridoMixin')
code = code.replace('ExportarEstadisticasExcelView', 'ExportarEstadisticasExcelOficinaView')
code = code.replace('ExportarEstadisticasPPTXView', 'ExportarEstadisticasPPTXOficinaView')

# Now adapt get_estadisticas_data to get_estadisticas_data_oficina
code = code.replace('def get_estadisticas_data(user):', 'def get_estadisticas_data_oficina():')
code = code.replace('stats = get_estadisticas_data(request.user)', 'stats = get_estadisticas_data_oficina()')

# Inside get_estadisticas_data_oficina, replace the filter
pattern = r'    departamento = user\.departamento\n    if departamento:\n        qs_base = Expediente\.objects\.filter\(alumno__carrera__departamento=departamento\)\n    else:\n        qs_base = Expediente\.objects\.filter\(alumno__carrera=user\.carrera\)'
code = re.sub(pattern, '    qs_base = Expediente.objects.all()', code)

pattern2 = r"'departamento': departamento\.nombre if departamento else \(user\.carrera\.nombre if user\.carrera else 'Global'\),"
code = re.sub(pattern2, "'departamento': 'Global (Oficina de Titulación)',", code)

start_func = code.find('def get_estadisticas_data_oficina():')
extracted = code[start_func:]

imports = '''
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import PieChart, BarChart, Reference
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
'''

with open('oficina_titulacion/views.py', 'a', encoding='utf-8') as f:
    f.write('\n' + imports + '\n' + extracted)
