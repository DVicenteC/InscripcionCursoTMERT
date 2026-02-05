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

# Importar el sistema de buffer
from db_buffer import get_buffer

# Configuración básica
st.set_page_config(page_title="Registro de Asistencia", layout="wide")

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
                        df[col] = pd.to_datetime(df[col], errors='coerce')

                df['cupo_maximo'] = pd.to_numeric(df['cupo_maximo'], errors='coerce')
            return df
        else:
            st.error(f"Error al obtener configuración: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para obtener registros de inscripción
@st.cache_data(ttl=180)  # Cache por 3 minutos
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

    # Buscar participante en el curso
    participante = df_registros[
        (df_registros['rut'] == rut) &
        (df_registros['curso_id'] == curso_id)
    ]

    if not participante.empty:
        return True, participante.iloc[0].to_dict()
    else:
        return False, None

# ==================== INTERFAZ PRINCIPAL ====================

def main():
    st.title("📋 Sistema de Registro de Asistencia (Con Buffer)")

    # Obtener instancia del buffer
    buffer = get_buffer()

    # ==================== SIDEBAR CON ESTADÍSTICAS ====================

    st.sidebar.title("🔐 Panel de Control")

    # Mostrar estadísticas del buffer
    st.sidebar.subheader("📊 Estado del Buffer")
    stats = buffer.get_estadisticas()

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Total", stats['total'])
        st.metric("Sincronizadas", stats['sincronizadas'])
    with col2:
        st.metric("Pendientes", stats['pendientes'])
        st.metric("Fallidas", stats['fallidas'])

    # Botón para forzar sincronización
    if st.sidebar.button("🔄 Sincronizar Ahora"):
        with st.spinner("Sincronizando con Google Sheets..."):
            resultado = buffer.sincronizar(batch_size=100)

        st.sidebar.success(f"✅ Sincronizados: {resultado['sincronizados']}")
        if resultado['fallidos'] > 0:
            st.sidebar.warning(f"⚠️ Fallidos: {resultado['fallidos']}")

    # Botón para limpiar cache
    if st.sidebar.button("🗑️ Limpiar Sincronizados"):
        eliminados = buffer.limpiar_sincronizados(dias=1)
        st.sidebar.success(f"✅ Eliminados: {eliminados} registros")

    st.sidebar.divider()

    # Panel administrativo
    password = st.sidebar.text_input("Contraseña Admin", type="password")
    admin_mode = password == SECRET_PASSWORD

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

        for _, curso in df_cursos_hoy.iterrows():
            with st.expander(f"📚 {curso['curso_id']} - Sesión {curso['sesion_hoy']}"):
                st.write(f"**Región:** {curso.get('region', 'N/A')}")
                st.write(f"**Fecha:** {curso['fecha_sesion_hoy'].strftime('%d-%m-%Y')}")
                st.write(f"**Sesión:** {curso['sesion_hoy']} de 3")

                # Formulario para marcar asistencia
                with st.form(key=f"form_{curso['curso_id']}_{curso['sesion_hoy']}"):
                    rut_input = st.text_input(
                        "Ingresa tu RUT (sin puntos, con guión)",
                        placeholder="12345678-9"
                    )

                    submit = st.form_submit_button("✅ Marcar Asistencia")

                    if submit and rut_input:
                        # Validar RUT
                        if not rut_chile.is_valid_rut(rut_input):
                            st.error("❌ RUT inválido. Verifica el formato.")
                        else:
                            # Verificar inscripción
                            df_registros = get_registros_data()
                            esta_inscrito, datos = validar_participante_inscrito(
                                rut_input,
                                curso['curso_id'],
                                df_registros
                            )

                            if not esta_inscrito:
                                st.error("❌ No estás inscrito en este curso. Contacta al administrador.")
                            else:
                                # Marcar asistencia en BUFFER (instantáneo)
                                resultado = guardar_asistencia_buffer(
                                    curso_id=curso['curso_id'],
                                    rut=rut_input,
                                    sesion=curso['sesion_hoy']
                                )

                                if resultado['success']:
                                    st.success(f"✅ ¡Asistencia registrada para {datos['nombre']}!")
                                    st.info("📤 Tu asistencia se sincronizará automáticamente con Google Sheets en los próximos 60 segundos.")
                                else:
                                    st.warning(f"ℹ️ {resultado['message']}")

        st.stop()

    # ==================== MODO ADMIN ====================

    if admin_mode:
        st.sidebar.success("✅ Acceso administrativo concedido")

        # Tabs para diferentes funciones
        tab1, tab2, tab3 = st.tabs(["📝 Gestionar Asistencia", "📊 Ver Asistencias", "🔧 Mantenimiento"])

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
                                # Verificar inscripción
                                df_registros = get_registros_data()
                                esta_inscrito, datos = validar_participante_inscrito(
                                    rut, curso_seleccionado, df_registros
                                )

                                if not esta_inscrito:
                                    st.error("❌ Participante no inscrito en este curso")
                                else:
                                    # Marcar en buffer
                                    resultado = buffer.marcar_asistencia(
                                        curso_id=curso_seleccionado,
                                        rut=rut,
                                        sesion=sesion_seleccionada,
                                        estado=estado,
                                        metodo='admin_manual'
                                    )

                                    if resultado['success']:
                                        st.success(f"✅ Asistencia registrada para {datos['nombre']}")
                                    else:
                                        st.error(f"❌ {resultado['message']}")

        # TAB 2: Ver Asistencias
        with tab2:
            st.subheader("📊 Visualizar Asistencias")

            df_cursos = get_config_data()

            if not df_cursos.empty:
                curso_ids = df_cursos['curso_id'].tolist()
                curso_ver = st.selectbox("Curso", curso_ids, key="ver_curso")

                sesion_ver = st.selectbox("Sesión", [1, 2, 3], key="ver_sesion")

                # Obtener asistencias desde el buffer
                df_asist = get_asistencias_from_buffer(curso_ver, sesion_ver)

                if not df_asist.empty:
                    st.write(f"**Total registros:** {len(df_asist)}")

                    # Mostrar estado de sincronización
                    sincronizadas = df_asist['sincronizado'].sum()
                    pendientes = len(df_asist) - sincronizadas

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("✅ Sincronizadas", sincronizadas)
                    with col2:
                        st.metric("⏳ Pendientes", pendientes)

                    # Mostrar tabla
                    st.dataframe(
                        df_asist[['rut', 'estado', 'fecha_registro', 'sincronizado', 'intentos_sync']],
                        use_container_width=True
                    )

                    # Botón para exportar
                    csv = df_asist.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Descargar CSV",
                        csv,
                        f"asistencias_{curso_ver}_sesion_{sesion_ver}.csv",
                        "text/csv"
                    )
                else:
                    st.info("ℹ️ No hay asistencias registradas para este curso y sesión")

        # TAB 3: Mantenimiento
        with tab3:
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
