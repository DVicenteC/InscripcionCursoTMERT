"""
Sistema de Registro de Asistencia con Buffer de Alta Concurrencia
=================================================================

Esta versión usa DuckDB como buffer en memoria para manejar
alta concurrencia (1000+ usuarios simultáneos).

Características:
- Escrituras instantáneas (<100ms)
- Sincronización automática con Google Sheets cada 60 segundos
- Panel de monitoreo de sincronización
- Recuperación automática de errores

Para usar este archivo:
1. pip install duckdb
2. Renombrar AsistenciaCurso.py a AsistenciaCurso_OLD.py
3. Renombrar este archivo a AsistenciaCurso.py
"""

import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, date
from rut_chile import rut_chile
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Importar el sistema de buffer
from db_buffer import get_buffer

# Configuración básica
st.set_page_config(page_title="Registro de Asistencia", layout="wide", initial_sidebar_state="collapsed")

# Constantes
SECRET_PASSWORD = st.secrets["SECRET_PASSWORD"]
API_URL = st.secrets["API_URL"]
API_KEY = st.secrets["API_KEY"]

# ==================== FUNCIONES DE API ====================

# Función para obtener datos de configuración de cursos
@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_config_data():
    try:
        response = requests.get(f"{API_URL}?action=getConfig&key={API_KEY}")
        data = response.json()

        if data['success']:
            df = pd.DataFrame(data['cursos'])
            if not df.empty:
                # Convertir columnas de fecha a datetime (detectando formato automáticamente)
                date_cols = ['fecha_inicio', 'fecha_fin', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']
                for col in date_cols:
                    if col in df.columns:
                        # La API devuelve ISO con timezone (ej: 2026-03-04T03:00:00.000Z)
                        # Se convierte a UTC naive y se normaliza a medianoche para comparar solo la fecha
                        df[col] = (pd.to_datetime(df[col], utc=True, errors='coerce')
                                   .dt.tz_convert(None)
                                   .dt.normalize())

                df['cupo_maximo'] = pd.to_numeric(df['cupo_maximo'], errors='coerce')
            return df
        else:
            st.error(f"Error al obtener configuración: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para obtener asistencias directamente desde Google Sheets (para descargas)
@st.cache_data(ttl=60)
def get_asistencias_desde_sheets(curso_id=None, sesion=None):
    try:
        response = requests.get(f"{API_URL}?action=getAsistencias&key={API_KEY}", timeout=15)
        data = response.json()
        if data.get('success') and data.get('asistencias'):
            df = pd.DataFrame(data['asistencias'])
            if df.empty:
                return pd.DataFrame()
            if curso_id:
                df = df[df['curso_id'].astype(str) == str(curso_id)]
            if sesion is not None:
                df = df[df['sesion'].astype(str) == str(sesion)]
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# Función para obtener registros de inscripción
@st.cache_data(ttl=180)  # Cache por 3 minutos
def get_registros_data():
    try:
        response = requests.get(f"{API_URL}?action=getRegistros&key={API_KEY}")
        data = response.json()

        if data['success']:
            df = pd.DataFrame(data['registros'])
            # Si la API devolvió datos pero sin columnas esperadas, tratar como vacío
            if not df.empty and 'rut' not in df.columns:
                st.warning("⚠️ La API devolvió registros sin estructura esperada.")
                return pd.DataFrame()
            return df
        else:
            st.error(f"Error al obtener registros: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# ==================== FUNCIONES DE BUFFER ====================

def guardar_asistencia_buffer(curso_id, rut, sesion):
    """
    Guarda asistencia en el buffer local (instantáneo).

    Args:
        curso_id: ID del curso
        rut: RUT del participante
        sesion: Número de sesión

    Returns:
        dict: Resultado de la operación
    """
    buffer = get_buffer()

    # Verificar si ya existe
    if buffer.verificar_asistencia(curso_id, rut, sesion):
        return {
            'success': False,
            'message': 'Ya existe un registro de asistencia para este participante en esta sesión'
        }

    # Marcar asistencia en buffer (ultra rápido)
    resultado = buffer.marcar_asistencia(
        curso_id=curso_id,
        rut=rut,
        sesion=sesion,
        estado='presente',
        metodo='streamlit_buffer'
    )

    return resultado

def get_asistencias_from_buffer(curso_id=None, sesion=None):
    """
    Obtiene asistencias desde el buffer local (instantáneo).

    Args:
        curso_id: ID del curso (opcional)
        sesion: Número de sesión (opcional)

    Returns:
        pd.DataFrame: DataFrame con asistencias
    """
    buffer = get_buffer()

    if curso_id and sesion:
        return buffer.get_asistencias_curso(curso_id, sesion)
    elif curso_id:
        return buffer.get_asistencias_curso(curso_id)
    else:
        # Obtener todas las asistencias
        return buffer.conn.execute("SELECT * FROM asistencias_buffer").df()

# ==================== FUNCIONES AUXILIARES ====================

def get_cursos_con_sesion_hoy(df_cursos):
    """
    Filtra cursos que tienen sesión hoy y devuelve DataFrame con información adicional.

    Args:
        df_cursos: DataFrame con configuración de cursos

    Returns:
        pd.DataFrame: Cursos con sesión hoy incluyendo columna 'sesion_hoy'
    """
    if df_cursos.empty:
        return pd.DataFrame()

    hoy = pd.Timestamp.now().normalize()
    cursos_hoy = []

    for _, curso in df_cursos.iterrows():
        # Verificar cada sesión
        for sesion_num in [1, 2, 3]:
            fecha_col = f'fecha_sesion_{sesion_num}'
            if fecha_col in curso and pd.notna(curso[fecha_col]):
                fecha_sesion = pd.to_datetime(curso[fecha_col]).normalize()
                if fecha_sesion == hoy:
                    # Crear una copia del curso con info de la sesión
                    curso_dict = curso.to_dict()
                    curso_dict['sesion_hoy'] = sesion_num
                    curso_dict['fecha_sesion_hoy'] = curso[fecha_col]
                    cursos_hoy.append(curso_dict)
                    break  # Solo tomar la primera sesión del día

    if cursos_hoy:
        return pd.DataFrame(cursos_hoy)
    else:
        return pd.DataFrame()

def validar_participante_inscrito(rut, curso_id, df_registros):
    """
    Verifica si un participante está inscrito en un curso.

    Args:
        rut: RUT del participante
        curso_id: ID del curso
        df_registros: DataFrame con registros de inscripciones

    Returns:
        tuple: (bool, dict) - (está_inscrito, datos_participante)
    """
    if df_registros.empty:
        return False, None

    # Buscar participante — comparación case-insensitive (ej: 12345678-k == 12345678-K)
    rut_norm = str(rut).upper().strip()
    participante = df_registros[
        (df_registros['rut'].astype(str).str.upper().str.strip() == rut_norm) &
        (df_registros['curso_id'] == curso_id)
    ]

    if not participante.empty:
        return True, participante.iloc[0].to_dict()
    else:
        return False, None

# ==================== GENERACIÓN DE REPORTES EXCEL ====================

def _split_rut(rut_str):
    """Separa RUT en cuerpo y dígito verificador."""
    partes = str(rut_str).strip().upper().split('-')
    if len(partes) == 2:
        return partes[0].replace('.', ''), partes[1]
    return rut_str, ''

def _sexo_a_codigo(sexo):
    """Convierte HOMBRE/MUJER al código numérico MK."""
    return 1 if str(sexo).upper() == 'HOMBRE' else 2

def _nacionalidad_a_codigo(nac):
    """Convierte nacionalidad al código numérico MK."""
    return 1 if str(nac).upper() == 'CHILENO' else 2

_ROL_CODIGO_MK = {
    'PROFESIONAL SST': 1,
    'TRABAJADOR': 2,
    'MIEMBRO DE COMITÉ PARITARIO': 3,
    'MIEMBRO COMITE PARITARIO': 3,
    'MONITOR O DELEGADO': 4,
    'DIRIGENTE SINDICAL': 5,
}

def generar_excel_ist(df):
    """
    Genera Excel formato MASTER CARGAS EMPRESAS IST EDUCA.
    df debe tener columnas de inscripción (registros joined con asistencias).
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Campos inscripción ISTeduca"

    headers = [
        "RUT trabajador (Sin puntos ni dv)", "DV", "Nombres", "Apellidos (ambos)",
        "Email (individual)", "Género", "Rol trabajador", "Región", "Comuna",
        "Rut empresa (Sin puntos, con guión)", "Razón social"
    ]

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    thin = Side(style='thin', color="AAAAAA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = border
        ws.row_dimensions[1].height = 30

    widths = [22, 6, 25, 30, 30, 10, 25, 30, 25, 28, 35]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w

    data_font = Font(name="Arial", size=10)
    for row_idx, row in enumerate(df.itertuples(index=False), 2):
        rut_body, rut_dv = _split_rut(getattr(row, 'rut', ''))
        apellidos = f"{getattr(row, 'apellido_paterno', '')} {getattr(row, 'apellido_materno', '')}".strip()
        valores = [
            rut_body,
            rut_dv,
            getattr(row, 'nombres', ''),
            apellidos,
            getattr(row, 'email', ''),
            getattr(row, 'sexo', ''),
            getattr(row, 'rol', ''),
            getattr(row, 'region', ''),
            getattr(row, 'comuna', ''),
            getattr(row, 'rut_empresa', ''),
            getattr(row, 'razon_social', ''),
        ]
        for col, val in enumerate(valores, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = data_font
            cell.border = border

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def generar_excel_mk(df):
    """
    Genera Excel formato Plantilla Carga Trabajadores MK Capacitaciones.
    Incluye hoja Datos + hojas de referencia (MaeSexo, MaeNacionalidad, MaeRolTrabajador).
    """
    wb = Workbook()

    # Hoja Datos
    ws = wb.active
    ws.title = "Datos"

    headers = ["Rut", "Nombres", "Apellido Paterno", "Apellido Materno",
               "Sexo", "Nacionalidad", "Rol Trabajador", "Otro Rol"]

    header_fill = PatternFill("solid", fgColor="2E75B6")
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    thin = Side(style='thin', color="AAAAAA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    widths = [18, 25, 25, 25, 8, 14, 16, 25]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = w

    data_font = Font(name="Arial", size=10)
    for row_idx, row in enumerate(df.itertuples(index=False), 2):
        rol_str = str(getattr(row, 'rol', '')).upper()
        otro_rol = rol_str if rol_str not in _ROL_CODIGO_MK else ''
        valores = [
            getattr(row, 'rut', ''),
            getattr(row, 'nombres', ''),
            getattr(row, 'apellido_paterno', ''),
            getattr(row, 'apellido_materno', ''),
            str(getattr(row, 'sexo', '')).capitalize(),
            str(getattr(row, 'nacionalidad', '')).capitalize(),
            rol_str.capitalize(),
            otro_rol,
        ]
        for col, val in enumerate(valores, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = data_font
            cell.border = border

    # Hoja Parametros
    wp = wb.create_sheet("Parametros")
    for r in [("Descripcion", "Valor"), ("Largo máximo Rut", 15),
              ("Largo máximo nombres", 50), ("Largo máximo apellido paterno", 50),
              ("Largo máximo apellido materno", 50)]:
        wp.append(r)

    # Hoja MaeSexo
    ws2 = wb.create_sheet("MaeSexo")
    for r in [("Codigo", "Valor"), (1, "Hombre"), (2, "Mujer")]:
        ws2.append(r)

    # Hoja MaeNacionalidad
    wn = wb.create_sheet("MaeNacionalidad")
    for r in [("Codigo", "Valor"), (1, "Chileno"), (2, "Extranjero")]:
        wn.append(r)

    # Hoja MaeRolTrabajador
    wr = wb.create_sheet("MaeRolTrabajador")
    for r in [("Codigo", "Valor"), (1, "Profesional SST"), (2, "Trabajador"),
              (3, "Miembro Comité Paritario"), (4, "Monitor o Delegado"), (5, "Dirigente Sindical")]:
        wr.append(r)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ==================== INTERFAZ PRINCIPAL ====================

def main():
    st.title("📋 Sistema de Registro de Asistencia")

    # Obtener instancia del buffer
    buffer = get_buffer()

    # ==================== SIDEBAR CON PANEL ADMIN ====================

    st.sidebar.title("🔐 Panel de Control")

    # Panel administrativo - primero la contraseña
    password = st.sidebar.text_input("Contraseña Admin", type="password")
    admin_mode = password == SECRET_PASSWORD

    if admin_mode:
        st.sidebar.success("✅ Acceso administrativo concedido")

        # Recargar asistencias desde Sheets al iniciar sesión admin (solo una vez por sesión)
        if not st.session_state.get("admin_hydrated"):
            with st.spinner("🔄 Cargando asistencias desde Google Sheets..."):
                n = buffer.force_hydrate()
            st.session_state["admin_hydrated"] = True
            st.sidebar.info(f"✅ {n} asistencias cargadas desde Sheets")

        # Mostrar estadísticas del buffer
        st.sidebar.subheader("📊 Estado del Buffer")
        stats = buffer.get_estadisticas()

        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.sidebar.metric("Total", stats['total'])
            st.sidebar.metric("Sincronizadas", stats['sincronizadas'])
        with col2:
            st.sidebar.metric("Pendientes", stats['pendientes'])
            st.sidebar.metric("Fallidas", stats['fallidas'])

        # Botón para forzar sincronización
        if st.sidebar.button("🔄 Sincronizar Ahora"):
            with st.spinner("Sincronizando con Google Sheets..."):
                resultado = buffer.sincronizar(batch_size=100)

            st.sidebar.success(f"✅ Sincronizados: {resultado['sincronizados']}")
            if resultado['fallidos'] > 0:
                st.sidebar.warning(f"⚠️ Fallidos: {resultado['fallidos']}")

        # Botón para limpiar todos los sincronizados (incluye los de hoy)
        if st.sidebar.button("🗑️ Limpiar Sincronizados"):
            eliminados = buffer.limpiar_sincronizados(dias=0)
            st.sidebar.success(f"✅ Eliminados: {eliminados} registros")

        # Botón para borrar TODO el buffer y re-hidratar desde Sheets
        if st.sidebar.button("🚨 Borrar Todo el Buffer", type="primary"):
            buffer.conn.execute("DELETE FROM asistencias_buffer")
            buffer.hydrate_from_sheets()  # Recargar lo que ya está en Sheets
            st.sidebar.success("✅ Buffer vaciado y recargado desde Sheets")
            st.rerun()

        st.sidebar.divider()

    # ==================== MODO PARTICIPANTE (SIN PASSWORD) ====================

    if not admin_mode:
        st.info("👤 **Modo Participante:** Marca tu asistencia ingresando tu RUT")

        # Obtener cursos con sesión hoy
        df_cursos = get_config_data()
        df_cursos_hoy = get_cursos_con_sesion_hoy(df_cursos)

        if df_cursos_hoy.empty:
            st.warning("⚠️ No hay cursos con sesión programada para hoy.")
            st.stop()

        # Mostrar cursos disponibles
        st.subheader("📅 Cursos con Sesión Hoy")

        @st.fragment
        def formulario_asistencia(curso_id, sesion_hoy, region, fecha_str):
            with st.expander(f"📚 {curso_id} - Sesión {sesion_hoy}", expanded=True):
                st.write(f"**Región:** {region}")
                st.write(f"**Fecha:** {fecha_str}")
                st.write(f"**Sesión:** {sesion_hoy} de 3")

                with st.form(key=f"form_{curso_id}_{sesion_hoy}", clear_on_submit=True):
                    rut_input = st.text_input(
                        "Ingresa tu RUT (sin puntos, con guión)",
                        placeholder="12345678-9"
                    )
                    submit = st.form_submit_button("✅ Marcar Asistencia")

                    if submit and rut_input:
                        rut_input = rut_input.strip().upper()
                        if not rut_chile.is_valid_rut(rut_input):
                            st.error("❌ RUT inválido. Verifica el formato.")
                        else:
                            df_registros = get_registros_data()
                            esta_inscrito, datos = validar_participante_inscrito(
                                rut_input, curso_id, df_registros
                            )
                            if not esta_inscrito:
                                st.error("❌ No estás inscrito en este curso. Contacta al administrador.")
                            else:
                                resultado = guardar_asistencia_buffer(
                                    curso_id=curso_id,
                                    rut=rut_input,
                                    sesion=sesion_hoy
                                )
                                if resultado['success']:
                                    nombre_completo = f"{datos.get('nombres', '')} {datos.get('apellido_paterno', '')}".strip() or rut_input
                                    st.success(f"✅ ¡Asistencia registrada para {nombre_completo}!")
                                    st.info("🎉 Ya puedes cerrar esta pestaña.")
                                    st.balloons()
                                else:
                                    st.warning(f"ℹ️ {resultado['message']}")

        for _, curso in df_cursos_hoy.iterrows():
            formulario_asistencia(
                curso_id=curso['curso_id'],
                sesion_hoy=curso['sesion_hoy'],
                region=curso.get('region', 'N/A'),
                fecha_str=curso['fecha_sesion_hoy'].strftime('%d-%m-%Y')
            )

        st.stop()

    # ==================== MODO ADMIN ====================

    if admin_mode:
        # Tabs para diferentes funciones
        tab1, tab2 = st.tabs(["📝 Gestionar Asistencia", "🔧 Mantenimiento"])

        # TAB 1: Gestionar Asistencia Manual
        with tab1:
            st.subheader("📝 Registro Manual de Asistencia")

            df_cursos = get_config_data()

            if df_cursos.empty:
                st.warning("⚠️ No hay cursos disponibles")
            else:
                # Seleccionar curso
                curso_ids = df_cursos['curso_id'].tolist()
                curso_seleccionado = st.selectbox("Selecciona un curso", curso_ids)

                # Obtener info del curso
                curso = df_cursos[df_cursos['curso_id'] == curso_seleccionado].iloc[0]

                # Mostrar sesiones disponibles
                sesiones = []
                for i in [1, 2, 3]:
                    if f'fecha_sesion_{i}' in curso and pd.notna(curso[f'fecha_sesion_{i}']):
                        sesiones.append(i)

                if not sesiones:
                    st.warning("⚠️ Este curso no tiene sesiones configuradas")
                else:
                    sesion_seleccionada = st.selectbox("Selecciona sesión", sesiones)

                    # Asistentes actuales con nombre + RUT
                    df_asist_actual = get_asistencias_from_buffer(curso_seleccionado, sesion_seleccionada if sesiones else 1)
                    if not df_asist_actual.empty:
                        df_reg_all = get_registros_data()
                        if not df_reg_all.empty and 'curso_id' in df_reg_all.columns:
                            df_reg_c = df_reg_all[df_reg_all['curso_id'] == curso_seleccionado].copy()
                            df_reg_c['rut_norm'] = df_reg_c['rut'].astype(str).str.upper().str.strip()
                            ruts_asist = df_asist_actual['rut'].str.upper().str.strip()
                            df_reg_c['asistió'] = df_reg_c['rut_norm'].isin(ruts_asist)
                            df_mostrar = df_reg_c[df_reg_c['asistió']][['rut', 'nombres', 'apellido_paterno']].copy()
                            df_mostrar.columns = ['RUT', 'Nombres', 'Apellido Paterno']
                            st.write(f"**Asistentes registrados: {len(df_mostrar)}**")
                            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
                        else:
                            st.write(f"**Asistentes: {len(df_asist_actual)}**")
                            st.dataframe(df_asist_actual[['rut', 'estado']], use_container_width=True, hide_index=True)

                    # ---- Descargar Reportes ----
                    st.divider()
                     # Formulario de registro
                    with st.form("form_admin"):
                        col1, col2 = st.columns(2)

                        with col1:
                            rut = st.text_input("RUT", placeholder="12345678-9")

                        with col2:
                            estado = st.selectbox("Estado", ["presente", "ausente", "justificado"])

                        submit = st.form_submit_button("💾 Registrar")

                        if submit and rut:
                            if not rut_chile.is_valid_rut(rut):
                                st.error("❌ RUT inválido")
                            else:
                                df_registros = get_registros_data()
                                esta_inscrito, datos = validar_participante_inscrito(
                                    rut, curso_seleccionado, df_registros
                                )

                                if not esta_inscrito:
                                    st.error("❌ Participante no inscrito en este curso")
                                else:
                                    resultado = buffer.marcar_asistencia(
                                        curso_id=curso_seleccionado,
                                        rut=rut,
                                        sesion=sesion_seleccionada,
                                        estado=estado,
                                        metodo='admin_manual'
                                    )

                                    if resultado['success']:
                                        nombre_completo = f"{datos.get('nombres', '')} {datos.get('apellido_paterno', '')}".strip() or datos.get('nombre', rut)
                                        st.success(f"✅ Asistencia registrada — {nombre_completo} ({rut})")
                                    else:
                                        st.error(f"❌ {resultado['message']}")
                    st.divider()
                    st.subheader("📥 Descargar Reportes")
                    df_registros_rep = get_registros_data()
                    if not df_registros_rep.empty and 'curso_id' in df_registros_rep.columns:
                        df_asist_rep = get_asistencias_desde_sheets(curso_seleccionado, sesion_seleccionada)
                        ruts_rep = df_asist_rep['rut'].astype(str).str.upper().str.strip().unique() if not df_asist_rep.empty else []
                        df_reg_rep = df_registros_rep[df_registros_rep['curso_id'] == curso_seleccionado].copy()
                        df_reg_rep['rut_norm'] = df_reg_rep['rut'].astype(str).str.upper().str.strip()
                        df_asistentes_rep = df_reg_rep[df_reg_rep['rut_norm'].isin(ruts_rep)].copy()

                        if df_asistentes_rep.empty:
                            st.info("ℹ️ No hay asistentes registrados para generar reportes.")
                        else:
                            col_r1, col_r2 = st.columns(2)
                            with col_r1:
                                st.markdown("**Formato IST Educa**")
                                st.download_button(
                                    label="📥 Descargar IST Educa (.xlsx)",
                                    data=generar_excel_ist(df_asistentes_rep),
                                    file_name=f"IST_{curso_seleccionado}_s{sesion_seleccionada}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            with col_r2:
                                st.markdown("**Formato MK Capacitaciones**")
                                st.download_button(
                                    label="📥 Descargar MK Capacitaciones (.xlsx)",
                                    data=generar_excel_mk(df_asistentes_rep),
                                    file_name=f"MK_{curso_seleccionado}_s{sesion_seleccionada}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )              

        # TAB 2: Mantenimiento
        with tab2:
            st.subheader("🔧 Mantenimiento del Sistema")

            st.write("### Sincronización Manual")
            batch_size = st.number_input("Tamaño del lote", min_value=10, max_value=200, value=50)

            if st.button("🚀 Sincronizar Lote Completo"):
                with st.spinner("Sincronizando..."):
                    resultado = buffer.sincronizar(batch_size=batch_size)

                st.write("**Resultado:**")
                st.json(resultado)

            st.divider()

            st.write("### Limpieza de Registros")
            dias = st.number_input("Mantener últimos N días", min_value=1, max_value=30, value=7)

            if st.button("🗑️ Limpiar Registros Antiguos"):
                eliminados = buffer.limpiar_sincronizados(dias=dias)
                st.success(f"✅ Eliminados {eliminados} registros antiguos")


if __name__ == "__main__":
    main()
