import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, date
from rut_chile import rut_chile
import io

# Configuración básica
st.set_page_config(page_title="Registro de Asistencia", layout="wide")

# Constantes
SECRET_PASSWORD = st.secrets["SECRET_PASSWORD"]
API_URL = st.secrets["API_URL"]
API_KEY = st.secrets["API_KEY"]

# ==================== FUNCIONES DE API ====================

# Función para obtener datos de configuración de cursos
def get_config_data():
    try:
        response = requests.get(f"{API_URL}?action=getConfig&key={API_KEY}")
        data = response.json()

        if data['success']:
            df = pd.DataFrame(data['cursos'])
            if not df.empty:
                df['cupo_maximo'] = pd.to_numeric(df['cupo_maximo'])
            return df
        else:
            st.error(f"Error al obtener configuración: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para obtener registros de inscripción
def get_registros_data():
    try:
        response = requests.get(f"{API_URL}?action=getRegistros&key={API_KEY}")
        data = response.json()

        if data['success']:
            return pd.DataFrame(data['registros'])
        else:
            st.error(f"Error al obtener registros: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para obtener el curso activo
def get_curso_activo():
    try:
        response = requests.get(f"{API_URL}?action=getCursoActivo&key={API_KEY}")
        data = response.json()

        if data['success']:
            return data['curso']
        else:
            return None
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return None

# Función para obtener registros de asistencia
def get_asistencias_data():
    try:
        response = requests.get(f"{API_URL}?action=getAsistencias&key={API_KEY}")
        data = response.json()

        if data['success']:
            return pd.DataFrame(data['asistencias'])
        else:
            st.error(f"Error al obtener asistencias: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para guardar un nuevo registro de asistencia
def guardar_asistencia(asistencia):
    try:
        response = requests.post(
            API_URL,
            params={"action": "addAsistencia", "key": API_KEY},
            json=asistencia
        )
        data = response.json()

        if data['success']:
            return True
        else:
            st.error(f"Error al guardar asistencia: {data.get('error', 'Error desconocido')}")
            return False
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return False

# Función para eliminar un registro de asistencia
def eliminar_asistencia(asistencia_id):
    try:
        response = requests.post(
            API_URL,
            params={"action": "deleteAsistencia", "key": API_KEY},
            json={"asistencia_id": asistencia_id}
        )
        data = response.json()

        if data['success']:
            return True
        else:
            st.error(f"Error al eliminar asistencia: {data.get('error', 'Error desconocido')}")
            return False
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return False

# ==================== FUNCIONES AUXILIARES ====================

def normalizar_fecha(fecha_valor):
    """
    Normaliza una fecha a formato yyyy-mm-dd para comparación.
    Maneja múltiples formatos de entrada.
    """
    if pd.isna(fecha_valor) or fecha_valor == '':
        return None

    fecha_str = str(fecha_valor)

    # Si está en formato ISO con T (ej: 2026-01-29T03:00:00.000Z)
    if 'T' in fecha_str:
        return fecha_str.split('T')[0]

    # Si ya está en formato yyyy-mm-dd
    if len(fecha_str) == 10 and fecha_str[4] == '-':
        return fecha_str

    # Si está en formato d/m/yyyy o dd/mm/yyyy
    if '/' in fecha_str:
        partes = fecha_str.split('/')
        if len(partes) == 3:
            dia = partes[0].zfill(2)
            mes = partes[1].zfill(2)
            anio = partes[2]
            return f"{anio}-{mes}-{dia}"

    # Intentar parsear como datetime
    try:
        if hasattr(fecha_valor, 'strftime'):
            return fecha_valor.strftime('%Y-%m-%d')
    except:
        pass

    return fecha_str


def get_cursos_con_sesion_hoy(df_cursos):
    """
    Filtra los cursos que tienen alguna sesión programada para HOY.
    Retorna un DataFrame con los cursos y la sesión correspondiente.
    Si un curso tiene múltiples sesiones hoy, se agrega una entrada por cada sesión.
    """
    if df_cursos.empty:
        return pd.DataFrame()

    hoy = date.today().strftime('%Y-%m-%d')
    cursos_hoy = []

    for _, curso in df_cursos.iterrows():
        # Verificar cada sesión (sin break, para capturar múltiples sesiones el mismo día)
        for sesion_num in [1, 2, 3]:
            fecha_col = f'fecha_sesion_{sesion_num}'
            if fecha_col in curso:
                fecha_sesion = normalizar_fecha(curso[fecha_col])
                if fecha_sesion == hoy:
                    curso_dict = curso.to_dict()
                    curso_dict['sesion_hoy'] = sesion_num
                    cursos_hoy.append(curso_dict)
                    # NO hacer break - permite múltiples sesiones el mismo día

    return pd.DataFrame(cursos_hoy)


def calcular_porcentaje_asistencia(rut, curso_id, df_asistencias):
    """Calcula el porcentaje de asistencia de un participante en un curso"""
    if df_asistencias.empty:
        return 0

    asistencias_participante = df_asistencias[
        (df_asistencias['rut'] == rut) &
        (df_asistencias['curso_id'] == curso_id)
    ]

    # Contar sesiones únicas a las que asistió
    sesiones_asistidas = asistencias_participante['sesion'].nunique()

    # Total de sesiones es 3
    porcentaje = (sesiones_asistidas / 3) * 100

    return round(porcentaje, 1)

def get_estado_aprobacion(porcentaje):
    """Determina el estado de aprobación basado en el porcentaje de asistencia"""
    if porcentaje >= 75:
        return "APROBADO"
    else:
        return "REPROBADO"

def crear_reporte_detallado(curso_id, df_registros, df_asistencias):
    """Crea un DataFrame con el detalle de asistencia por sesión"""
    if df_registros.empty:
        return pd.DataFrame()

    # Filtrar registros del curso
    participantes = df_registros[df_registros['curso_id'] == curso_id].copy()

    if participantes.empty:
        return pd.DataFrame()

    # Crear columnas para cada sesión
    participantes['Sesion_1'] = 'AUSENTE'
    participantes['Sesion_2'] = 'AUSENTE'
    participantes['Sesion_3'] = 'AUSENTE'

    # Marcar asistencias
    if not df_asistencias.empty:
        for idx, row in participantes.iterrows():
            rut = row['rut']

            # Verificar asistencia a cada sesión
            for sesion in [1, 2, 3]:
                asistio = not df_asistencias[
                    (df_asistencias['rut'] == rut) &
                    (df_asistencias['curso_id'] == curso_id) &
                    (df_asistencias['sesion'] == sesion)
                ].empty

                if asistio:
                    participantes.at[idx, f'Sesion_{sesion}'] = 'PRESENTE'

    # Calcular porcentaje y estado
    participantes['Porcentaje_Asistencia'] = participantes['rut'].apply(
        lambda rut: calcular_porcentaje_asistencia(rut, curso_id, df_asistencias)
    )

    participantes['Estado'] = participantes['Porcentaje_Asistencia'].apply(get_estado_aprobacion)

    # Seleccionar columnas relevantes para el reporte
    columnas_reporte = ['rut', 'nombres', 'apellido_paterno', 'apellido_materno',
                       'Sesion_1', 'Sesion_2', 'Sesion_3',
                       'Porcentaje_Asistencia', 'Estado']

    return participantes[columnas_reporte]

# ==================== INTERFAZ PRINCIPAL ====================

try:
    # Título principal
    st.title("📋 Sistema de Registro de Asistencia")

    # ==================== PANEL ADMINISTRATIVO ====================

    st.sidebar.title("🔐 Panel Administrativo")
    password = st.sidebar.text_input("Contraseña", type="password")

    admin_mode = password == SECRET_PASSWORD

    if admin_mode:
        st.sidebar.success("✅ Acceso administrativo concedido")

        # En modo admin, necesitamos un curso activo para gestionar
        curso_actual = get_curso_activo()

        if not curso_actual:
            st.warning("⚠️ No hay ningún curso activo. Seleccione uno desde el panel de Inscripción.")
            st.stop()

        # Mostrar información del curso activo (solo para admin)
        st.info(f"**Curso Activo (Admin):** {curso_actual['curso_id']}")

        # Verificar si el curso tiene fechas de sesiones
        if 'fecha_sesion_1' not in curso_actual:
            st.error("❌ Este curso no tiene fechas de sesiones configuradas.")
            st.stop()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"📅 **Sesión 1:** {curso_actual['fecha_sesion_1']}")
        with col2:
            st.write(f"📅 **Sesión 2:** {curso_actual['fecha_sesion_2']}")
        with col3:
            st.write(f"📅 **Sesión 3:** {curso_actual['fecha_sesion_3']}")

        st.divider()

        st.sidebar.divider()
        st.sidebar.subheader("Opciones de Administrador")

        opcion_admin = st.sidebar.radio(
            "Seleccione una opción:",
            ["📝 Marcar Asistencia Manual",
             "📊 Ver Reportes y Estadísticas",
             "📥 Descargar Reporte Excel",
             "✏️ Editar/Corregir Asistencias"]
        )

        st.sidebar.divider()

        # ==================== MARCAR ASISTENCIA MANUAL ====================

        if opcion_admin == "📝 Marcar Asistencia Manual":
            st.header("📝 Marcar Asistencia Manual")

            # Obtener participantes inscritos
            df_registros = get_registros_data()

            if df_registros.empty:
                st.warning("No hay participantes inscritos en este curso.")
            else:
                participantes_curso = df_registros[df_registros['curso_id'] == curso_actual['curso_id']]

                if participantes_curso.empty:
                    st.warning("No hay participantes inscritos en este curso.")
                else:
                    # Selector de sesión
                    sesion = st.selectbox(
                        "Seleccione la sesión:",
                        [1, 2, 3],
                        format_func=lambda x: f"Sesión {x} - {curso_actual[f'fecha_sesion_{x}']}"
                    )

                    # Crear lista de participantes para selección
                    participantes_lista = participantes_curso.apply(
                        lambda row: f"{row['rut']} - {row['nombres']} {row['apellido_paterno']} {row['apellido_materno']}",
                        axis=1
                    ).tolist()

                    participante_seleccionado = st.selectbox(
                        "Seleccione el participante:",
                        participantes_lista
                    )

                    if st.button("✅ Marcar como PRESENTE", type="primary"):
                        # Extraer RUT del participante seleccionado
                        rut_participante = participante_seleccionado.split(" - ")[0]

                        # Verificar si ya existe registro de asistencia
                        df_asistencias = get_asistencias_data()

                        ya_registrado = False
                        if not df_asistencias.empty:
                            ya_registrado = not df_asistencias[
                                (df_asistencias['rut'] == rut_participante) &
                                (df_asistencias['curso_id'] == curso_actual['curso_id']) &
                                (df_asistencias['sesion'] == sesion)
                            ].empty

                        if ya_registrado:
                            st.warning("⚠️ Este participante ya tiene registrada su asistencia para esta sesión.")
                        else:
                            # Crear registro de asistencia
                            nueva_asistencia = {
                                'curso_id': curso_actual['curso_id'],
                                'rut': rut_participante,
                                'sesion': sesion,
                                'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'estado': 'PRESENTE',
                                'metodo': 'MANUAL'
                            }

                            if guardar_asistencia(nueva_asistencia):
                                st.success(f"✅ Asistencia registrada exitosamente para {participante_seleccionado}")
                                time.sleep(1)
                                st.rerun()

        # ==================== VER REPORTES Y ESTADÍSTICAS ====================

        elif opcion_admin == "📊 Ver Reportes y Estadísticas":
            st.header("📊 Reportes y Estadísticas de Asistencia")

            # Obtener datos
            df_registros = get_registros_data()
            df_asistencias = get_asistencias_data()

            if df_registros.empty:
                st.warning("No hay participantes inscritos.")
            else:
                participantes_curso = df_registros[df_registros['curso_id'] == curso_actual['curso_id']]

                if participantes_curso.empty:
                    st.warning("No hay participantes inscritos en este curso.")
                else:
                    total_inscritos = len(participantes_curso)

                    # Estadísticas por sesión
                    st.subheader("📈 Estadísticas por Sesión")

                    col1, col2, col3 = st.columns(3)

                    for i, col in enumerate([col1, col2, col3], start=1):
                        with col:
                            if df_asistencias.empty:
                                presentes = 0
                            else:
                                presentes = len(df_asistencias[
                                    (df_asistencias['curso_id'] == curso_actual['curso_id']) &
                                    (df_asistencias['sesion'] == i)
                                ])

                            porcentaje = (presentes / total_inscritos * 100) if total_inscritos > 0 else 0

                            st.metric(
                                f"Sesión {i}",
                                f"{presentes}/{total_inscritos}",
                                f"{porcentaje:.1f}%"
                            )

                    st.divider()

                    # Reporte detallado
                    st.subheader("📋 Detalle de Asistencia por Participante")

                    reporte = crear_reporte_detallado(curso_actual['curso_id'], df_registros, df_asistencias)

                    if not reporte.empty:
                        # Aplicar formato condicional
                        def highlight_estado(row):
                            if row['Estado'] == 'APROBADO':
                                return ['background-color: #d4edda'] * len(row)
                            else:
                                return ['background-color: #f8d7da'] * len(row)

                        st.dataframe(
                            reporte.style.apply(highlight_estado, axis=1),
                            use_container_width=True,
                            hide_index=True
                        )

                        # Resumen de aprobación
                        st.divider()
                        st.subheader("🎓 Resumen de Aprobación")

                        aprobados = len(reporte[reporte['Estado'] == 'APROBADO'])
                        reprobados = len(reporte[reporte['Estado'] == 'REPROBADO'])

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Inscritos", total_inscritos)
                        with col2:
                            st.metric("Aprobados", aprobados, f"{(aprobados/total_inscritos*100):.1f}%")
                        with col3:
                            st.metric("Reprobados", reprobados, f"{(reprobados/total_inscritos*100):.1f}%")

        # ==================== DESCARGAR REPORTE EXCEL ====================

        elif opcion_admin == "📥 Descargar Reporte Excel":
            st.header("📥 Descargar Reporte de Asistencia")

            df_registros = get_registros_data()
            df_asistencias = get_asistencias_data()

            if df_registros.empty:
                st.warning("No hay participantes inscritos.")
            else:
                participantes_curso = df_registros[df_registros['curso_id'] == curso_actual['curso_id']]

                if participantes_curso.empty:
                    st.warning("No hay participantes inscritos en este curso.")
                else:
                    reporte = crear_reporte_detallado(curso_actual['curso_id'], df_registros, df_asistencias)

                    if not reporte.empty:
                        # Preparar Excel para descarga
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            reporte.to_excel(
                                writer,
                                sheet_name='Asistencia',
                                index=False
                            )

                            # Formato para el archivo Excel
                            workbook = writer.book
                            worksheet = writer.sheets['Asistencia']

                            # Formato de encabezado
                            header_format = workbook.add_format({
                                'bold': True,
                                'bg_color': '#4472C4',
                                'font_color': 'white',
                                'border': 1
                            })

                            # Formato para aprobados
                            aprobado_format = workbook.add_format({
                                'bg_color': '#C6EFCE',
                                'border': 1
                            })

                            # Formato para reprobados
                            reprobado_format = workbook.add_format({
                                'bg_color': '#FFC7CE',
                                'border': 1
                            })

                            # Aplicar formato de encabezado
                            for col_num, value in enumerate(reporte.columns.values):
                                worksheet.write(0, col_num, value, header_format)
                                worksheet.set_column(col_num, col_num, len(str(value)) + 2)

                            worksheet.freeze_panes(1, 0)

                        buffer.seek(0)

                        st.download_button(
                            label=f"📥 Descargar Reporte de Asistencia ({len(reporte)} participantes)",
                            data=buffer.getvalue(),
                            file_name=f"asistencia_{curso_actual['curso_id']}.xlsx",
                            mime="application/vnd.ms-excel",
                            type="primary"
                        )

                        st.success("✅ Reporte generado correctamente. Haga clic en el botón para descargar.")

        # ==================== EDITAR/CORREGIR ASISTENCIAS ====================

        elif opcion_admin == "✏️ Editar/Corregir Asistencias":
            st.header("✏️ Editar/Corregir Asistencias")

            df_asistencias = get_asistencias_data()

            if df_asistencias.empty:
                st.info("No hay registros de asistencia para este curso.")
            else:
                asistencias_curso = df_asistencias[df_asistencias['curso_id'] == curso_actual['curso_id']]

                if asistencias_curso.empty:
                    st.info("No hay registros de asistencia para este curso.")
                else:
                    st.write("**Registros de asistencia existentes:**")
                    st.dataframe(asistencias_curso, use_container_width=True, hide_index=True)

                    st.divider()

                    st.subheader("🗑️ Eliminar Registro de Asistencia")
                    st.warning("⚠️ Esta acción eliminará permanentemente el registro de asistencia seleccionado.")

                    # Crear lista de registros para eliminar
                    registros_lista = asistencias_curso.apply(
                        lambda row: f"ID: {row.get('id', 'N/A')} | {row['rut']} | Sesión {row['sesion']} | {row['fecha_registro']}",
                        axis=1
                    ).tolist()

                    if registros_lista:
                        registro_seleccionado = st.selectbox(
                            "Seleccione el registro a eliminar:",
                            registros_lista
                        )

                        if st.button("🗑️ Eliminar Registro", type="secondary"):
                            # Extraer ID del registro (si existe)
                            if 'id' in asistencias_curso.columns:
                                idx = registros_lista.index(registro_seleccionado)
                                asistencia_id = asistencias_curso.iloc[idx]['id']

                                if eliminar_asistencia(asistencia_id):
                                    st.success("✅ Registro eliminado exitosamente")
                                    time.sleep(1)
                                    st.rerun()
                            else:
                                st.error("No se puede eliminar: el registro no tiene ID")

    # ==================== MODO PÚBLICO - AUTOREGISTRO ====================

    else:
        st.header("✅ Registro de Asistencia")
        st.write("Ingrese su RUT para verificar su inscripción y registrar asistencia")

        # Paso 1: Ingresar RUT
        rut_participante = st.text_input("RUT (*)", help="Formato: 12345678-9", key="rut_autoregistro").upper()

        if rut_participante:
            # Validar formato de RUT
            if not rut_chile.is_valid_rut(rut_participante):
                st.error("❌ RUT inválido. Verifique el formato (ej: 12345678-9)")
            else:
                # Verificar si está inscrito en ALGÚN curso
                df_registros = get_registros_data()

                if df_registros.empty:
                    st.error("❌ No hay participantes inscritos en ningún curso")
                else:
                    # Buscar si el RUT está inscrito en algún curso
                    inscripciones_participante = df_registros[df_registros['rut'] == rut_participante]

                    if inscripciones_participante.empty:
                        st.error("❌ No está inscrito en ningún curso. Debe inscribirse primero.")
                    else:
                        # Obtener datos del participante
                        datos_participante = inscripciones_participante.iloc[0]
                        nombre_completo = f"{datos_participante['nombres']} {datos_participante['apellido_paterno']}"

                        st.success(f"✅ Bienvenido/a, **{nombre_completo}**")

                        # Obtener todos los cursos
                        df_cursos = get_config_data()

                        if df_cursos.empty:
                            st.warning("⚠️ No hay cursos configurados en el sistema")
                        else:
                            # Filtrar cursos con sesión HOY
                            df_cursos_hoy = get_cursos_con_sesion_hoy(df_cursos)

                            if df_cursos_hoy.empty:
                                st.info("📅 No hay sesiones programadas para hoy. Vuelva el día de su sesión.")
                            else:
                                st.divider()
                                st.subheader("📅 Cursos con sesión hoy")

                                # Mostrar cursos disponibles
                                opciones_cursos = []
                                for _, curso in df_cursos_hoy.iterrows():
                                    region_curso = curso.get('region', 'Sin región')
                                    sesion_num = curso['sesion_hoy']
                                    curso_info = f"{curso['curso_id']} - {region_curso} (Sesión {sesion_num})"
                                    opciones_cursos.append(curso_info)

                                curso_seleccionado_info = st.selectbox(
                                    "Seleccione el curso donde desea registrar asistencia (*)",
                                    opciones_cursos,
                                    key="curso_asistencia"
                                )

                                # Obtener el curso y sesión seleccionados
                                idx_curso = opciones_cursos.index(curso_seleccionado_info)
                                curso_seleccionado = df_cursos_hoy.iloc[idx_curso]
                                sesion_seleccionada = int(curso_seleccionado['sesion_hoy'])

                                # Mostrar información del curso
                                st.info(f"**Curso:** {curso_seleccionado['curso_id']}")
                                st.write(f"**Sesión {sesion_seleccionada}:** {curso_seleccionado[f'fecha_sesion_{sesion_seleccionada}']}")

                                # Botón para registrar asistencia
                                if st.button("✅ Registrar mi Asistencia", type="primary"):
                                    # Verificar si ya registró asistencia para esta sesión en este curso
                                    df_asistencias = get_asistencias_data()

                                    ya_registrado = False
                                    if not df_asistencias.empty:
                                        ya_registrado = not df_asistencias[
                                            (df_asistencias['rut'] == rut_participante) &
                                            (df_asistencias['curso_id'] == curso_seleccionado['curso_id']) &
                                            (df_asistencias['sesion'] == sesion_seleccionada)
                                        ].empty

                                    if ya_registrado:
                                        st.warning("⚠️ Ya tiene registrada su asistencia para esta sesión en este curso")
                                    else:
                                        # Registrar asistencia
                                        nueva_asistencia = {
                                            'curso_id': curso_seleccionado['curso_id'],
                                            'rut': rut_participante,
                                            'sesion': sesion_seleccionada,
                                            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'estado': 'PRESENTE',
                                            'metodo': 'AUTOREGISTRO'
                                        }

                                        if guardar_asistencia(nueva_asistencia):
                                            st.success(f"✅ Asistencia registrada exitosamente para {nombre_completo}")
                                            st.balloons()
                                            time.sleep(2)
                                            st.rerun()

except Exception as e:
    st.error(f"❌ Error en la aplicación: {str(e)}")
