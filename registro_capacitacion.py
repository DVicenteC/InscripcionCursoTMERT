"""
Hoja imprimible "Registro": réplica del formulario IST "REGISTRO DE CAPACITACIÓN"
(COD 9016/074), con el mismo formato que genera
_Scripts/procesamiento_datos/Diagnostico_Integridad_capacitacionesTMERT.py.

Se llena todo lo que el sistema sabe; queda en blanco a propósito lo que sólo
existe en la sala (firma, edad, dependencia, horarios, relator, contenido) para
imprimirla, firmarla y adjuntarla con las fotos del evento.
"""

import base64
import io
import unicodedata

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from logo_ist import LOGO_IST_B64

NOMBRES_CURSO = {
    "460":  "PROTOCOLO VOTME - GENERALIDADES Y FACTORES DE RIESGO",
    "C461": "PROTOCOLO VOTME - CARACTERIZACIÓN DE PUESTO, DESCRIPCIÓN DE TAREAS",
    "C462": "PROTOCOLO VOTME - APLICACIÓN DE TABLAS DE IDENTIFICACIÓN",
}

# El impreso pide el rol como número. Lo no reconocido queda en blanco para
# completarlo a mano antes que arriesgar un código equivocado.
ROLES_REGISTRO = {
    "PROFESIONAL SST": 1, "PROFESIONAL IST": 1,
    "TRABAJADOR": 2,
    "MIEMBRO COMITE PARITARIO": 3, "MIEMBRO DE COMITE PARITARIO": 3, "MIEMBRO CPHS": 3,
    "MONITOR O DELEGADO": 4, "MONITOR": 4, "DELEGADO": 4,
    "DIRIGENTE SINDICAL": 5,
    "EMPLEADOR": 6,
}

REGISTRO_FILAS_MINIMAS = 20        # el talonario de papel trae 20
_REG_ANCHOS = [4.5, 34, 14, 18, 14, 26, 5.5, 5.5, 6.5, 6.5, 6.5, 6.5, 7.5]

_REG_ENCABEZADOS = [
    "N°", "NOMBRE Y APELLIDOS PARTICIPANTE", "RUT PARTICIPANTE", "FIRMA",
    "RUT EMPRESA", "RAZÓN SOCIAL", "Edad", "Sexo", "Nacion.",
    "Depend.", "Rol", "Lugar", "Califc.",
]
_REG_LEYENDAS = (
    "Dependencia:  1 Sala · 2 Auditorio · 3 Aire libre · 4 Sala móvil (bus) · "
    "5 Puesto de trabajo · 6 Otro     |     "
    "Rol del trabajador:  1 Profesional IST · 2 Trabajador · 3 Miembro CPHS · "
    "4 Monitor o delegado · 5 Dirigente sindical · 6 Empleador     |     "
    "Lugar de ejecución:  1 Sede de capacitación · 2 Sede empresa · 3 Virtual · "
    "4 Otro     |     Sexo: F / M     |     Nacionalidad: 1 chileno · 2 extranjero"
)


def _limpiar(v) -> str:
    if v is None:
        return ""
    s = str(v).replace("\x00", "").strip()
    return "" if s.lower() in ("nan", "none", "nat") else s


def _sin_tilde(v) -> str:
    s = unicodedata.normalize("NFD", _limpiar(v))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _reg_sexo(v) -> str:
    """El impreso pide F o M. Tomar la primera letra de 'Mujer' daría 'M'."""
    s = _sin_tilde(v).strip().upper()
    if s.startswith(("MUJER", "FEMENINO", "F")):
        return "F"
    if s.startswith(("HOMBRE", "MASCULINO", "M")):
        return "M"
    return ""


def _reg_nacionalidad(v):
    s = _sin_tilde(v).strip().upper()
    if not s:
        return ""
    return 1 if s.startswith("CHILE") else 2


def _reg_rol(v):
    return ROLES_REGISTRO.get(_sin_tilde(v).strip().upper(), "")


def modulo_de_sesion(sesion, num_sesiones) -> str:
    """Código del módulo que se dicta en esa sesión: 1 → 460, 2 → C461,
    la última → C462. Otra sesión (p. ej. la 3 de un curso de 4) → ''."""
    try:
        sesion, num_sesiones = int(sesion), int(num_sesiones)
    except (TypeError, ValueError):
        return ""
    if sesion == 1:
        return "460"
    if sesion == 2:
        return "C461"
    if sesion == num_sesiones:
        return "C462"
    return ""


def escribir_hoja_registro(ws, filas: list, meta: dict):
    """Dibuja el formulario 'REGISTRO DE CAPACITACIÓN' en `ws`.

    filas: dicts con las llaves de la plantilla del bot (Rut, Nombres, Apellido
    Paterno, Apellido Materno, Sexo, Nacionalidad, Rol Trabajador, Razón social,
    Rut empresa (Sin puntos, con guión) y, opcional, Nota).
    meta: curso, nombre_curso, fecha_txt, sede, region_txt, virtual (bool)."""
    morado, gris = "FF4F0B7B", "FF404040"
    f_etiq = Font(name="Calibri", bold=True, size=8, color=gris)
    f_valor = Font(name="Calibri", size=10)
    f_th = Font(name="Calibri", bold=True, size=8, color=gris)
    f_td = Font(name="Calibri", size=9)
    f_nota = Font(name="Calibri", size=7, color=gris)
    centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    izq = Alignment(horizontal="left", vertical="center", wrap_text=True)
    fill_lila = PatternFill("solid", fgColor="FFD9D2E9")
    fill_etiq = PatternFill("solid", fgColor="FFF2F2F2")
    s = Side(style="thin", color="FFB0B0B0")
    borde = Border(left=s, right=s, top=s, bottom=s)

    def bloque(rango, valor="", font=f_valor, align=izq, fill=None):
        """Combina y bordea TODAS las celdas del rango: si sólo se bordea la primera,
        al imprimir el recuadro sale abierto."""
        ws.merge_cells(rango)
        for fila in ws[rango]:
            for c in fila:
                c.border = borde
                if fill is not None:
                    c.fill = fill
        c0 = ws[rango.split(":")[0]]
        c0.value, c0.font, c0.alignment = valor, font, align

    def etiqueta(rango, texto):
        bloque(rango, texto, f_etiq, centro, fill_etiq)

    ws.sheet_view.showGridLines = False
    for i, w in enumerate(_REG_ANCHOS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ult = get_column_letter(len(_REG_ANCHOS))          # "M"

    ws.row_dimensions[1].height = 26
    bloque("A1:B1", "ORIGINAL IST", Font(name="Calibri", bold=True, size=9,
                                         color=morado), izq)
    bloque("C1:J1", "REGISTRO DE CAPACITACIÓN",
           Font(name="Calibri", bold=True, size=16, color=morado), centro)
    bloque("K1:" + ult + "1", "",
           Font(name="Calibri", bold=True, italic=True, size=9, color=morado), centro)
    try:
        from openpyxl.drawing.image import Image
        _logo = Image(io.BytesIO(base64.b64decode(LOGO_IST_B64)))
        _logo.height = 32
        _logo.width = 32
        ws.add_image(_logo, "K1")
    except Exception:
        # Sin Pillow (u otro error) se cae al texto.
        ws["K1"].value = "ist | la vida al centro"
    ws.row_dimensions[2].height = 5

    etiqueta("A3:A3", "Código")
    etiqueta("B3:D3", "Nombre de la Capacitación")
    etiqueta("E3:F3", "Fecha de actividad")
    etiqueta("G3:I3", "Misceláneo / Origen")
    etiqueta("J3:" + ult + "3", "Región")
    ws.row_dimensions[4].height = 20
    bloque("A4:A4", meta.get("curso", ""), f_valor, centro)
    bloque("B4:D4", meta.get("nombre_curso", ""), f_valor, izq)
    bloque("E4:F4", meta.get("fecha_txt", ""), f_valor, centro)
    bloque("G4:I4", "Misceláneo:  SI [ ]   NO [ ]     Origen:  Programado [ ]   "
                    "No Programado [ ]", f_nota, izq)
    bloque("J4:" + ult + "4", meta.get("region_txt", ""), f_valor, izq)

    etiqueta("A5:A5", "Tipo")
    bloque("B5:B5", "Curso [X]", f_nota, centro)
    bloque("C5:C5", "Seminario [ ]", f_nota, centro)
    bloque("D5:D5", "Charla [ ]", f_nota, centro)
    bloque("E5:F5", "Otro [ ]", f_nota, centro)
    etiqueta("G5:H5", "Comuna de ejecución")
    bloque("I5:" + ult + "5", meta.get("sede", ""), f_valor, izq)

    etiqueta("A6:A6", "Sede")
    bloque("B6:B6", "OA [ ]", f_nota, centro)
    bloque("C6:C6", "Empresa [ ]", f_nota, centro)
    bloque("D6:D6", "Otra [ ]", f_nota, centro)
    etiqueta("E6:F6", "Nombre completo relator")
    bloque("G6:" + ult + "6", "", f_valor, izq)
    ws.row_dimensions[7].height = 6

    fila_th = 8
    ws.row_dimensions[fila_th].height = 30
    for i, h in enumerate(_REG_ENCABEZADOS, start=1):
        c = ws.cell(row=fila_th, column=i, value=h)
        c.font, c.alignment, c.fill, c.border = f_th, centro, fill_lila, borde

    def _nom(f):
        return " ".join(x for x in (_limpiar(f.get("Nombres")),
                                    _limpiar(f.get("Apellido Paterno")),
                                    _limpiar(f.get("Apellido Materno"))) if x)

    # Orden alfabético por apellido: es el que permite pasar lista en sala.
    ordenadas = sorted(filas, key=lambda f: _sin_tilde(
        str(f.get("Apellido Paterno", "")) + " " + str(f.get("Nombres", ""))).upper())
    n = max(REGISTRO_FILAS_MINIMAS, len(ordenadas))
    fila_ini = fila_th + 1
    lugar = 3 if meta.get("virtual") else ""       # 3 = Virtual

    for i in range(n):
        r = fila_ini + i
        ws.row_dimensions[r].height = 16
        f = ordenadas[i] if i < len(ordenadas) else None
        if f is None:
            vals = [i + 1] + [""] * 12
        else:
            vals = [
                i + 1, _nom(f), _limpiar(f.get("Rut")), "",   # FIRMA: a mano
                _limpiar(f.get("Rut empresa (Sin puntos, con guión)")),
                _limpiar(f.get("Razón social")),
                "",                                  # Edad: no está en el origen
                _reg_sexo(f.get("Sexo")), _reg_nacionalidad(f.get("Nacionalidad")),
                "",                                  # Dependencia: se marca en sala
                _reg_rol(f.get("Rol Trabajador")), lugar, _limpiar(f.get("Nota")),
            ]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.font = f_td
            c.alignment = izq if j in (2, 6) else centro
            c.border = borde
    fila_fin = fila_ini + n - 1

    r = fila_fin + 1
    ws.row_dimensions[r].height = 26
    bloque("A" + str(r) + ":" + ult + str(r), _REG_LEYENDAS, f_nota, izq)

    r += 2
    bloque("A" + str(r) + ":" + ult + str(r), "ASPECTOS ADMINISTRATIVOS",
           Font(name="Calibri", bold=True, size=10, color=gris), centro, fill_lila)
    r += 1
    ws.row_dimensions[r].height = 24
    for col, txt in (("A", "Día"), ("B", "Fecha"), ("C", "Horario inicio"),
                     ("D", "Horario término"), ("E", "Hor. C")):
        etiqueta(col + str(r) + ":" + col + str(r), txt)
    etiqueta("F" + str(r) + ":H" + str(r), "Contenido")
    etiqueta("I" + str(r) + ":K" + str(r), "Nombre y firma del facilitador")
    etiqueta("L" + str(r) + ":" + ult + str(r), "R.U.T. del facilitador")
    for d in (1, 2, 3):
        r += 1
        ws.row_dimensions[r].height = 20
        bloque("A" + str(r) + ":A" + str(r), d, f_td, centro)
        bloque("B" + str(r) + ":B" + str(r),
               meta.get("fecha_txt", "") if d == 1 else "", f_td, centro)
        for col in ("C", "D", "E"):
            bloque(col + str(r) + ":" + col + str(r), "", f_td, centro)
        bloque("F" + str(r) + ":H" + str(r),
               meta.get("nombre_curso", "") if d == 1 else "", f_td, izq)
        bloque("I" + str(r) + ":K" + str(r), "", f_td, izq)
        bloque("L" + str(r) + ":" + ult + str(r), "", f_td, centro)

    r += 1
    ws.row_dimensions[r].height = 20
    etiqueta("A" + str(r) + ":A" + str(r), "Dirección")
    bloque("B" + str(r) + ":F" + str(r), "", f_td, izq)
    etiqueta("G" + str(r) + ":G" + str(r), "Comuna")
    bloque("H" + str(r) + ":J" + str(r), meta.get("sede", ""), f_td, izq)
    etiqueta("K" + str(r) + ":K" + str(r), "Ciudad")
    bloque("L" + str(r) + ":" + ult + str(r), "", f_td, izq)

    r += 1
    ws.cell(row=r, column=1, value="COD 9016/074").font = f_nota
    ws.merge_cells("A" + str(r) + ":C" + str(r))

    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_setup.fitToWidth = 1
    # Con más de 20 participantes ya no cabe en una carilla: se deja fluir a varias
    # páginas repitiendo el encabezado, en vez de encoger la letra hasta lo ilegible.
    ws.page_setup.fitToHeight = 1 if n <= REGISTRO_FILAS_MINIMAS else 0
    ws.print_title_rows = str(fila_th) + ":" + str(fila_th)
    ws.print_area = "A1:" + ult + str(r)
    ws.page_margins.left = ws.page_margins.right = 0.3
    ws.page_margins.top = ws.page_margins.bottom = 0.35
