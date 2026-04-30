import streamlit as st
import pandas as pd
import polars as pl
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from rut_chile import rut_chile
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Configuración básica
st.set_page_config(page_title="Inscripción de Participantes", layout="wide")

# Constantes
COMUNAS_REGIONES_PATH = "comunas-regiones.json"
MAESTRO_LOCAL_PATH = Path(__file__).parent / "maestro_adherentes.parquet"
SECRET_PASSWORD = st.secrets["SECRET_PASSWORD"]
API_URL = st.secrets["API_URL"]  # URL del Apps Script publicado como aplicación web
API_KEY = st.secrets["API_KEY"]  # Clave API configurada en el Apps Script
SMTP_USER = st.secrets.get("SMTP_USER", "")
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "")
MAESTRO_URL = st.secrets.get("MAESTRO_URL", None)

def _rut_valido(rut_str):
    try:
        return bool(rut_chile.is_valid_rut(str(rut_str).strip()))
    except Exception:
        return False

@st.cache_resource(show_spinner="Cargando maestro de adherentes…")
def load_maestro() -> pl.DataFrame:
    if MAESTRO_LOCAL_PATH.exists():
        df = pl.read_parquet(MAESTRO_LOCAL_PATH)
    elif MAESTRO_URL:
        try:
            sess = requests.Session()
            resp = sess.get(MAESTRO_URL, stream=True, timeout=30)
            if 'text/html' in resp.headers.get('Content-Type', ''):
                import re as _re
                m = _re.search(r'confirm=([0-9A-Za-z_-]+)', resp.text)
                if m:
                    resp = sess.get(f"{MAESTRO_URL}&confirm={m.group(1)}", stream=True, timeout=60)
            resp.raise_for_status()
            df = pl.read_parquet(io.BytesIO(resp.content))
        except Exception as e:
            st.error(f"Error al descargar maestro desde URL: {e}")
            return pl.DataFrame()
    else:
        return pl.DataFrame()
    cols = ['Rut Empresa', 'Razón Social', 'ID-CT', 'NUM SUC',
            'C.GLS_NOM_SUC', 'Dirección Suc', 'Comuna Sucursal',
            'Region Sucursal', 'Est Sucursal', 'Tipo suc']
    df = df.select([c for c in cols if c in df.columns])
    return df.filter(pl.col('Est Sucursal') == 'Si') if 'Est Sucursal' in df.columns else df

def _norm_rut(r: str) -> str:
    try: return rut_chile.format_rut_without_dots(str(r)).upper().strip()
    except Exception: return str(r).upper().strip()

def buscar_sucursales(rut_empresa: str = "", razon_social: str = "") -> pl.DataFrame:
    df = load_maestro()
    if df.is_empty(): return df
    if rut_empresa and _rut_valido(rut_empresa):
        rut_n = _norm_rut(rut_empresa)
        out = df.with_columns(pl.col('Rut Empresa').map_elements(_norm_rut, return_dtype=pl.Utf8).alias('_rut_n')) \
                .filter(pl.col('_rut_n') == rut_n).drop('_rut_n')
        if not out.is_empty(): return out
    if razon_social:
        return df.filter(pl.col('Razón Social') == razon_social)
    return pl.DataFrame()

@st.cache_data(show_spinner=False)
def listar_empresas() -> list[str]:
    df = load_maestro()
    if df.is_empty(): return []
    pdf = df.select(['Razón Social', 'Rut Empresa']).unique().to_pandas()
    pdf = pdf.dropna(subset=['Razón Social']).sort_values('Razón Social')
    return [f"{r['Razón Social']} — {r['Rut Empresa']}" for _, r in pdf.iterrows()]

# Listas para formulario
ROLES = ["TRABAJADOR", "PROFESIONAL SST", "MIEMBRO DE COMITÉ PARITARIO", 
         "MONITOR O DELEGADO", "DIRIGENTE SINDICAL", "EMPLEADOR", 
         "TRABAJADOR DEL OA", "OTROS"]
SEXO =['MUJER','HOMBRE']
NACIONALIDAD = ['CHILENO', 'EXTRANJERO']

# Cargar archivo JSON de comunas y regiones
with open(COMUNAS_REGIONES_PATH, "r", encoding='utf-8') as file:
    comunas_regiones = json.load(file)

# Obtener lista de regiones
regiones = [region["region"] for region in comunas_regiones["regiones"]]

def enviar_confirmacion(destinatario, nombres, apellido_paterno, rut, curso_id, region, fecha_inicio):
    """Envía correo de confirmación de inscripción al participante."""
    if not SMTP_USER or not SMTP_PASSWORD:
        return  # Sin credenciales configuradas, no enviar

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Confirmación de inscripción — {curso_id}"
        msg["From"] = SMTP_USER
        msg["To"] = destinatario

        html = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto">
          <div style="background:#1F4E79;padding:20px;text-align:center">
            <h2 style="color:white;margin:0">Inscripción Confirmada</h2>
            <p style="color:#cce4ff;margin:5px 0">Protocolo VOTME — IST</p>
          </div>
          <div style="padding:30px">
            <p>Estimado/a <strong>{nombres} {apellido_paterno}</strong>,</p>
            <p>Tu inscripción ha sido registrada exitosamente. A continuación los datos:</p>
            <table style="border-collapse:collapse;width:100%">
              <tr><td style="padding:8px;background:#f0f4f8;width:40%"><strong>RUT</strong></td>
                  <td style="padding:8px;background:#f0f4f8">{rut}</td></tr>
              <tr><td style="padding:8px"><strong>Curso</strong></td>
                  <td style="padding:8px">{curso_id}</td></tr>
              <tr><td style="padding:8px;background:#f0f4f8"><strong>Región</strong></td>
                  <td style="padding:8px;background:#f0f4f8">{region}</td></tr>
              <tr><td style="padding:8px"><strong>Fecha inicio</strong></td>
                  <td style="padding:8px">{fecha_inicio}</td></tr>
            </table>
            <p style="margin-top:20px">Si tienes dudas, responde este correo o contacta a tu ejecutivo IST.</p>
          </div>
          <div style="background:#f0f4f8;padding:15px;text-align:center;font-size:12px;color:#666">
            Instituto de Seguridad del Trabajo (IST)
          </div>
        </body></html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, destinatario, msg.as_string())

    except Exception:
        pass  # El correo es opcional — no interrumpe la inscripción


# Función para obtener datos de configuración desde la API
@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_config_data():
    try:
        response = requests.get(f"{API_URL}?action=getConfig&key={API_KEY}")
        data = response.json()
        
        if data['success']:
            df = pd.DataFrame(data['cursos'])
            if not df.empty:
                # Convertir columnas de fecha a datetime (probando múltiples formatos)
                date_cols = ['fecha_inicio', 'fecha_fin', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3', 'fecha_sesion_4']
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')

                if 'cupo_maximo' in df.columns:
                    df['cupo_maximo'] = pd.to_numeric(df['cupo_maximo'], errors='coerce')
                if 'num_sesiones' in df.columns:
                    df['num_sesiones'] = pd.to_numeric(df['num_sesiones'], errors='coerce').fillna(3).astype(int)
                else:
                    # Auto-detectar num_sesiones contando columnas fecha_sesion_N no nulas
                    def _count_sesiones(row):
                        count = 0
                        for i in range(1, 5):
                            col = f'fecha_sesion_{i}'
                            if col in row.index and pd.notna(row[col]) and row[col] != '':
                                count = i
                        return max(count, 3)
                    df['num_sesiones'] = df.apply(_count_sesiones, axis=1).astype(int)
            return df
        else:
            st.error(f"Error al obtener configuración: {data.get('error', 'Error desconocido')}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return pd.DataFrame()

# Función para obtener registros desde la API
@st.cache_data(ttl=180)  # Cache por 3 minutos (se actualiza más frecuentemente)
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

# Función para activar un curso
def activar_curso(curso_id):
    try:
        response = requests.post(
            API_URL,
            params={"action": "activarCurso", "key": API_KEY},
            json={"curso_id": curso_id}
        )
        data = response.json()
        
        if data['success']:
            return True
        else:
            st.error(f"Error al activar curso: {data.get('error', 'Error desconocido')}")
            return False
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return False

# Función para crear un nuevo curso
def crear_curso(curso_data):
    try:
        response = requests.post(
            API_URL,
            params={"action": "addCurso", "key": API_KEY},
            json=curso_data
        )
        data = response.json()
        
        if data['success']:
            return True
        else:
            st.error(f"Error al crear curso: {data.get('error', 'Error desconocido')}")
            return False
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return False

# Función para guardar un nuevo registro
def guardar_registro(registro, max_retries=3):
    """
    Guarda registro de participante con retry logic.

    Args:
        registro: Diccionario con datos del participante
        max_retries: Número máximo de reintentos (default: 3)

    Returns:
        True si se guardó exitosamente, False en caso contrario
    """
    import random

    for attempt in range(max_retries):
        try:
            # Agregar pequeño delay aleatorio en reintentos
            if attempt > 0:
                jitter = random.uniform(0.5, 2.0)
                time.sleep(jitter)
                st.info(f"🔄 Reintentando... (intento {attempt + 1}/{max_retries})")

            response = requests.post(
                API_URL,
                params={"action": "addRegistro", "key": API_KEY},
                json=registro,
                timeout=15  # Timeout de 15 segundos
            )
            data = response.json()

            if data['success']:
                return True
            else:
                error_msg = data.get('error', 'Error desconocido')

                # Si el error es "sistema ocupado", reintentar
                if 'ocupado' in error_msg.lower() or 'busy' in error_msg.lower():
                    if attempt < max_retries - 1:
                        continue  # Reintentar
                    else:
                        st.error(f"⚠️ Sistema sobrecargado. Por favor, intente nuevamente.")
                        return False

                # Otro tipo de error
                else:
                    st.error(f"Error al guardar registro: {error_msg}")
                    return False

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                st.warning(f"⏱️ Tiempo de espera agotado. Reintentando...")
                continue
            else:
                st.error(f"❌ Timeout después de {max_retries} intentos.")
                return False

        except Exception as e:
            if attempt < max_retries - 1:
                continue
            else:
                st.error(f"Error al conectar con la API: {str(e)}")
                return False

    return False

# Función auxiliar para formatear fechas
def formato_fecha_dd_mm_yyyy(fecha):
    """Convierte una fecha a formato dd-mm-yyyy para mostrar al usuario"""
    if pd.isna(fecha):
        return ""
    try:
        if isinstance(fecha, str):
            fecha = pd.to_datetime(fecha)
        return fecha.strftime('%d-%m-%Y')
    except:
        return str(fecha)

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

# Función para actualizar comunas basado en la región seleccionada
def update_comunas_state():
    # Reinicia la lista de comunas cada vez que se selecciona una región
    st.session_state.comunas = []
    # Si una región ha sido seleccionada
    if st.session_state.region:
        # Busca la región seleccionada y guarda las comunas en st.session_state
        for reg in comunas_regiones["regiones"]:
            if reg["region"] == st.session_state.region:
                st.session_state.comunas = reg["comunas"]
                break

try:
    # Panel de Administración
    st.sidebar.title("Panel de Control")
    password = st.sidebar.text_input("Contraseña", type="password")

    # Botón para limpiar cache (útil cuando hay actualizaciones)
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.sidebar.success("✅ Cache limpiado. Datos actualizados.")
        st.rerun()

    if password == SECRET_PASSWORD:
        st.sidebar.success("✅ Acceso concedido")

        # Obtener configuración de cursos
        df_cursos = get_config_data()

        # Filtro regional para admin
        st.sidebar.subheader("Filtrar por Región")
        opciones_region_admin = ["Todas las regiones"] + regiones
        region_admin = st.sidebar.selectbox(
            "Seleccione región para gestionar",
            opciones_region_admin,
            key="region_admin"
        )

        # Filtrar cursos según región seleccionada
        if not df_cursos.empty and region_admin != "Todas las regiones":
            if 'region' in df_cursos.columns:
                df_cursos_filtrados = df_cursos[df_cursos['region'] == region_admin]
            else:
                df_cursos_filtrados = df_cursos
        else:
            df_cursos_filtrados = df_cursos

        st.sidebar.divider()

        # Selector de curso para activar
        if not df_cursos_filtrados.empty:
            cursos_disponibles = df_cursos_filtrados['curso_id'].tolist()

            if cursos_disponibles:
                curso_seleccionado = st.sidebar.selectbox(
                    "Seleccionar Curso para Activar",
                    cursos_disponibles,
                    index=0
                )

                if st.sidebar.button("Activar Curso"):
                    if activar_curso(curso_seleccionado):
                        st.sidebar.success(f"✅ Curso {curso_seleccionado} activado")
                        time.sleep(1)
                        st.rerun()

        st.sidebar.divider()

        # Crear nuevo curso
        st.sidebar.subheader("Crear Nuevo Curso")

        # Selector de región para el nuevo curso
        region_curso = st.sidebar.selectbox(
            "Región del Curso (*)",
            regiones,
            key="region_nuevo_curso"
        )

        # Mapeo de regiones a códigos cortos
        region_codigo_map = {
            "Región de Arica y Parinacota": "ARI",
            "Región de Tarapacá": "TAR",
            "Región de Antofagasta": "ANT",
            "Región de Atacama": "ATA",
            "Región de Coquimbo": "COQ",
            "Región de Valparaíso": "VAL",
            "Región Metropolitana de Santiago": "RM",
            "Región del Libertador Gral. Bernardo O'Higgins": "OHI",
            "Región del Maule": "MAU",
            "Región de Ñuble": "ÑUB",
            "Región del Biobío": "BIO",
            "Región de la Araucanía": "ARA",
            "Región de Los Ríos": "RIO",
            "Región de Los Lagos": "LAG",
            "Región Aysén del Gral. Carlos Ibáñez del Campo": "AYS",
            "Región de Magallanes y de la Antártica Chilena": "MAG"
        }

        fecha_inicio = st.sidebar.date_input("Fecha de Inicio")
        fecha_fin = st.sidebar.date_input("Fecha de Término")

        # Número de sesiones y fechas
        num_sesiones = st.sidebar.selectbox("Número de Sesiones", [3, 4], index=0)
        st.sidebar.write("**Fechas de Sesiones:**")
        fechas_sesiones = []
        for i in range(1, num_sesiones + 1):
            fechas_sesiones.append(st.sidebar.date_input(f"Fecha Sesión {i}"))

        # Generar ID automáticamente en formato: CódigoRegión-MesAño
        meses_esp = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        mes_nombre = meses_esp[fecha_inicio.month]
        anio_corto = str(fecha_inicio.year)[2:]  # Últimos 2 dígitos del año
        codigo_region = region_codigo_map.get(region_curso, "OTR")

        curso_id_generado = f"{codigo_region}-{mes_nombre}{anio_corto}"

        # Mostrar ID generado (editable por si necesitan ajustarlo)
        curso_id = st.sidebar.text_input(
            "ID del Curso (Auto-generado)",
            value=curso_id_generado,
            help="Puede editar el ID si es necesario. Formato: CódigoRegión-MesAño"
        )

        cupo_maximo = st.sidebar.number_input("Cupo Máximo", min_value=1, value=50)

        if st.sidebar.button("Crear Curso"):
            # Validaciones
            if not curso_id:
                st.sidebar.error("⚠️ Debe ingresar un ID para el curso")
            elif fecha_fin <= fecha_inicio:
                st.sidebar.error("⚠️ La fecha de término debe ser posterior a la fecha de inicio")
            else:
                # Crear objeto de curso con región
                nuevo_curso = {
                    'curso_id': str(curso_id),
                    'region': region_curso,
                    'fecha_inicio': fecha_inicio.strftime('%d-%m-%Y'),
                    'fecha_fin': fecha_fin.strftime('%d-%m-%Y'),
                    'num_sesiones': num_sesiones,
                    'fecha_sesion_1': fechas_sesiones[0].strftime('%d-%m-%Y') if len(fechas_sesiones) > 0 else '',
                    'fecha_sesion_2': fechas_sesiones[1].strftime('%d-%m-%Y') if len(fechas_sesiones) > 1 else '',
                    'fecha_sesion_3': fechas_sesiones[2].strftime('%d-%m-%Y') if len(fechas_sesiones) > 2 else '',
                    'fecha_sesion_4': fechas_sesiones[3].strftime('%d-%m-%Y') if len(fechas_sesiones) > 3 else '',
                    'cupo_maximo': int(cupo_maximo),
                    'estado': 'ACTIVO'
                }

                if crear_curso(nuevo_curso):
                    st.sidebar.success("✅ Curso creado exitosamente")
                    time.sleep(1)
                    st.rerun()
        
        # Gestión de registros existentes
        st.sidebar.subheader("Gestión de Registros")
        
        # Obtener registros existentes
        df_registros = get_registros_data()
        
        # Selector de curso para descargar
        if not df_cursos.empty:
            cursos_disponibles = df_cursos['curso_id'].unique().tolist()
            curso_seleccionado_descarga = st.sidebar.selectbox(
                "Seleccionar Curso para Descargar",
                cursos_disponibles,
                index=None,
                placeholder="Seleccione un curso..."
            )
            
            if curso_seleccionado_descarga and st.sidebar.button("Descargar Registros"):
                # Filtrar registros del curso seleccionado
                if not df_registros.empty:
                    registros_curso = df_registros[df_registros['curso_id'] == curso_seleccionado_descarga]
                    
                    if not registros_curso.empty:
                        # Preparar Excel para descarga
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            registros_curso.to_excel(
                                writer,
                                sheet_name='Datos',
                                index=False,
                                float_format='%.2f'
                            )
                            
                            # Formato para el archivo Excel
                            workbook = writer.book
                            worksheet = writer.sheets['Datos']
                            header_format = workbook.add_format({
                                'bold': True,
                                'bg_color': '#D8E4BC',
                                'border': 1
                            })
                            
                            for col_num, value in enumerate(registros_curso.columns.values):
                                worksheet.write(0, col_num, value, header_format)
                                worksheet.set_column(col_num, col_num, len(str(value)) + 2)
                            
                            worksheet.freeze_panes(1, 0)
                        
                        buffer.seek(0)
                        st.sidebar.download_button(
                            label=f"📥 Descargar Registros ({len(registros_curso)} inscritos)",
                            data=buffer.getvalue(),
                            file_name=f"registros_curso_{curso_seleccionado_descarga}.xlsx",
                            mime="application/vnd.ms-excel"
                        )
                    else:
                        st.sidebar.warning("No hay registros para este curso")
                else:
                    st.sidebar.warning("No hay registros disponibles")

    # Mostrar formulario de inscripción
    try:
        st.title("Inscripción Curso de 20 horas Protocolo VOTME para Profesionales SST Implementadores - Empresas Adherentes de IST")

        # Obtener todos los cursos
        df_cursos = get_config_data()

        if df_cursos.empty:
            st.warning("No hay cursos disponibles. El administrador debe crear uno.")
            st.stop()

        # Filtrar cursos disponibles: fecha_fin >= hoy (cursos vigentes o futuros)
        hoy = pd.Timestamp.now().normalize()

        if 'fecha_fin' in df_cursos.columns:
            # Convertir ambas fechas a la misma zona horaria (sin timezone)
            df_cursos_copia = df_cursos.copy()
            df_cursos_copia['fecha_fin'] = pd.to_datetime(df_cursos_copia['fecha_fin']).dt.tz_localize(None)
            # Filtrar cursos donde la fecha_fin sea mayor o igual a hoy
            df_cursos_disponibles = df_cursos_copia[df_cursos_copia['fecha_fin'] >= hoy].copy()
        else:
            df_cursos_disponibles = df_cursos

        if df_cursos_disponibles.empty:
            st.warning("No hay cursos disponibles para inscripción. Todos los cursos han finalizado.")
            st.stop()

        # Paso 1: Seleccionar región del curso
        st.subheader("1. Seleccione la región del curso")

        # Obtener regiones con cursos disponibles
        if 'region' in df_cursos_disponibles.columns:
            regiones_con_cursos = df_cursos_disponibles['region'].unique().tolist()
            regiones_disponibles = [r for r in regiones if r in regiones_con_cursos]
        else:
            regiones_disponibles = regiones

        if not regiones_disponibles:
            st.warning("No hay cursos disponibles en ninguna región.")
            st.stop()

        region_curso_seleccionada = st.selectbox(
            "Región del curso (*)",
            regiones_disponibles,
            key='region_curso_inscripcion',
            placeholder="Seleccione una región..."
        )

        # Paso 2: Seleccionar curso de esa región
        if region_curso_seleccionada:
            if 'region' in df_cursos_disponibles.columns:
                cursos_region = df_cursos_disponibles[df_cursos_disponibles['region'] == region_curso_seleccionada]
            else:
                cursos_region = df_cursos_disponibles

            if cursos_region.empty:
                st.warning(f"No hay cursos disponibles en {region_curso_seleccionada}.")
                st.stop()

            st.subheader("2. Seleccione el curso")

            # Crear lista de cursos con información útil
            opciones_cursos = []
            for _, curso in cursos_region.iterrows():
                curso_info = f"{curso['curso_id']}"
                opciones_cursos.append(curso_info)

            curso_seleccionado_info = st.selectbox(
                "Curso (*)",
                opciones_cursos,
                key='curso_seleccionado_inscripcion'
            )

            # Obtener el curso seleccionado
            idx_curso = opciones_cursos.index(curso_seleccionado_info)
            curso_actual = cursos_region.iloc[idx_curso].to_dict()

            # Mostrar información del curso seleccionado
            st.info(f"**Curso seleccionado:** {curso_actual['curso_id']}")
            st.write(f"**Período:** {formato_fecha_dd_mm_yyyy(curso_actual['fecha_inicio'])} - {formato_fecha_dd_mm_yyyy(curso_actual['fecha_fin'])}")

            # Mostrar fechas de sesiones si están disponibles
            if 'fecha_sesion_1' in curso_actual:
                st.write("**Fechas de Sesiones:**")
                num_ses = int(curso_actual.get('num_sesiones', 3))
                cols = st.columns(min(num_ses, 3))
                for i in range(1, num_ses + 1):
                    col_idx = (i - 1) % 3
                    fecha_col = f'fecha_sesion_{i}'
                    if fecha_col in curso_actual and pd.notna(curso_actual[fecha_col]):
                        with cols[col_idx]:
                            st.write(f"📅 Sesión {i}: {formato_fecha_dd_mm_yyyy(curso_actual[fecha_col])}")

            # Verificar cupos disponibles
            df_registros = get_registros_data()
            if not df_registros.empty:
                inscritos_actuales = len(df_registros[df_registros['curso_id'] == curso_actual['curso_id']])
                cupos_disponibles = int(curso_actual['cupo_maximo']) - inscritos_actuales
            else:
                inscritos_actuales = 0
                cupos_disponibles = int(curso_actual['cupo_maximo'])

            # Mostrar información de cupos
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Cupo Máximo", curso_actual['cupo_maximo'])
            with col2:
                st.metric("Inscritos", inscritos_actuales)
            with col3:
                st.metric("Cupos Disponibles", cupos_disponibles)

            if cupos_disponibles <= 0:
                st.error("Lo sentimos, este curso ha alcanzado el límite máximo de inscripciones.")
                st.stop()

            st.divider()

            # Paso 3: Formulario de inscripción
            st.subheader("3. Complete sus datos")

            # Región y comuna de residencia del participante
            st.write("**Datos de ubicación del participante:**")

            if 'comunas' not in st.session_state or not st.session_state.comunas:
                for reg in comunas_regiones["regiones"]:
                    if reg["region"] == regiones[0]:
                        st.session_state.comunas = reg["comunas"]
                        break

            region = st.selectbox("Región del participante (*)", regiones, key='region', on_change=update_comunas_state)
            comuna = st.selectbox("Comuna de residencia (*)", st.session_state.get('comunas', []), key='comuna')

            # === Búsqueda de empresa (selectbox único) ===
            st.write("**Empresa y centro de trabajo:**")
            empresas_list = listar_empresas()
            empresa_seleccionada = st.selectbox(
                "Empresa (*)",
                options=empresas_list,
                index=None,
                placeholder="Escriba el nombre o el RUT de la empresa…",
                key='empresa_selectbox',
                help=f"{len(empresas_list):,} empresas disponibles."
            )
            razon_social_input = ""
            rut_empresa_input = ""
            if empresa_seleccionada:
                razon_social_input, rut_empresa_input = empresa_seleccionada.rsplit(" — ", 1)
                rut_empresa_input = rut_empresa_input.strip().upper()
                st.caption(f"RUT detectado: **{rut_empresa_input}**")

            _maestro_check = load_maestro()
            if _maestro_check.is_empty():
                st.error("❌ Maestro de adherentes no disponible. Configure `MAESTRO_URL` en los secrets.")

            sucursales_df = buscar_sucursales(rut_empresa_input, razon_social_input)
            sucursal_sel = None
            if not sucursales_df.is_empty():
                pdf = sucursales_df.to_pandas()
                pdf['_label'] = pdf.apply(
                    lambda r: f"[{r['ID-CT']}] {r['C.GLS_NOM_SUC']} — {r['Dirección Suc']} ({r['Comuna Sucursal']})",
                    axis=1
                )
                st.success(f"✅ {len(pdf)} centro(s) de trabajo encontrado(s)")
                opciones = ["— Seleccione un centro de trabajo —"] + pdf['_label'].tolist()
                seleccion = st.selectbox("Centro de trabajo (*)", opciones, key='sucursal_sel')
                if seleccion != opciones[0]:
                    sucursal_sel = pdf[pdf['_label'] == seleccion].iloc[0].to_dict()
                    with st.expander("Ver detalle del centro de trabajo"):
                        st.write(f"**ID-CT:** {sucursal_sel['ID-CT']}")
                        st.write(f"**NUM SUC:** {sucursal_sel['NUM SUC']}")
                        st.write(f"**Nombre Sucursal:** {sucursal_sel['C.GLS_NOM_SUC']}")
                        st.write(f"**Dirección:** {sucursal_sel['Dirección Suc']}")
                        st.write(f"**Comuna:** {sucursal_sel['Comuna Sucursal']}")
            elif rut_empresa_input or razon_social_input:
                st.warning("⚠️ No se encontraron centros de trabajo activos.")

            with st.form("registro_form"):
                col1, col2 = st.columns(2)

                with col1:
                    rut = st.text_input("RUT (*)", help="Formato: 12345678-9").upper()
                    nombres = st.text_input("Nombres (*)").upper()
                    apellido_paterno = st.text_input("Apellido Paterno (*)").upper()
                    email = st.text_input("Correo Electrónico (*)", help="ejemplo@dominio.com")
                    gmail = st.text_input("Correo Gmail (*)", help="ejemplo@gmail.com")

                with col2:
                    sexo = st.selectbox("Sexo (*)", SEXO).upper()
                    apellido_materno = st.text_input("Apellido Materno (*)").upper()
                    nacionalidad = st.selectbox("Nacionalidad (*)", NACIONALIDAD).upper()
                    rol = st.selectbox("Rol (*)", ROLES).upper()

                if sucursal_sel is not None:
                    rut_empresa = rut_empresa_input or _norm_rut(str(sucursal_sel.get('Rut Empresa', '')))
                    razon_social = str(sucursal_sel.get('Razón Social', '')).upper()
                    direccion = str(sucursal_sel['Dirección Suc']).upper()
                    st.info(f"Empresa: **{razon_social}** · CT: **{sucursal_sel['C.GLS_NOM_SUC']}** ({sucursal_sel['Comuna Sucursal']})")
                else:
                    st.warning("Sin centro de trabajo seleccionado — ingrese dirección manualmente:")
                    rut_empresa = rut_empresa_input
                    razon_social = razon_social_input
                    direccion = st.text_input("Dirección del centro de trabajo (*)").upper()

                if st.form_submit_button("Enviar"):
                    # Verificar nuevamente los cupos disponibles
                    df_registros = get_registros_data()
                    if not df_registros.empty:
                        inscritos_actuales = len(df_registros[df_registros['curso_id'] == curso_actual['curso_id']])
                        cupos_disponibles = int(curso_actual['cupo_maximo']) - inscritos_actuales
                    else:
                        cupos_disponibles = int(curso_actual['cupo_maximo'])

                    # Normalizar RUT para comparación (formato estándar: 12345678-5)
                    rut_normalizado = rut_chile.format_rut_without_dots(rut).upper()

                    # Verificar si el usuario ya está inscrito en este curso
                    if not df_registros.empty:
                        # Normalizar todos los RUTs en el dataframe para comparación
                        df_registros['rut_normalizado'] = df_registros['rut'].apply(lambda x: rut_chile.format_rut_without_dots(str(x)).upper() if x else '')

                        usuario_ya_inscrito = df_registros[
                            (df_registros['rut_normalizado'] == rut_normalizado) &
                            (df_registros['curso_id'] == curso_actual['curso_id'])
                        ]

                        if not usuario_ya_inscrito.empty:
                            st.error("⚠️ Ya estás inscrito en este curso")
                            st.info(f"📅 Inscripción registrada el: {usuario_ya_inscrito.iloc[0]['fecha_registro']}")
                            st.stop()  # Detener ejecución

                    if cupos_disponibles <= 0:
                        st.error("Lo sentimos, mientras se procesaba su solicitud se agotaron los cupos disponibles.")
                    elif not all([rut, nombres, apellido_paterno, nacionalidad, email, gmail,
                                 rut_empresa, razon_social, region, comuna, direccion]):
                        st.error("Complete todos los campos obligatorios")
                    elif not rut_chile.is_valid_rut(rut):
                        st.error("RUT personal inválido")
                    elif not rut_chile.is_valid_rut(rut_empresa):
                        st.error("RUT empresa inválido")
                    elif '@' not in email or '.' not in email:
                        st.error("Correo electrónico inválido")
                    #elif '@gmail.com' not in gmail.lower():
                    #    st.error("Debe ingresar un correo Gmail válido")
                    else:
                        # Normalizar RUTs al formato estándar: 12345678-5 (sin puntos, con guión)
                        rut_limpio = rut_chile.format_rut_without_dots(rut).upper()
                        rut_empresa_limpio = rut_chile.format_rut_without_dots(rut_empresa).upper()

                        # Preparar nuevo registro
                        nuevo_registro = {
                            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'curso_id': curso_actual['curso_id'],
                            'rut': rut_limpio,
                            'nombres': nombres,
                            'apellido_paterno': apellido_paterno,
                            'apellido_materno': apellido_materno,
                            'nacionalidad': nacionalidad,
                            'email': email,
                            'gmail': gmail,
                            'sexo': sexo,
                            'rol': rol,
                            'rut_empresa': rut_empresa_limpio,
                            'razon_social': razon_social,
                            'region': region,
                            'comuna': comuna,
                            'direccion': direccion,
                            'id_ct': str(sucursal_sel['ID-CT']) if sucursal_sel is not None else '',
                            'num_suc': str(sucursal_sel['NUM SUC']) if sucursal_sel is not None else '',
                            'nom_suc': str(sucursal_sel['C.GLS_NOM_SUC']) if sucursal_sel is not None else '',
                            'comuna_suc': str(sucursal_sel['Comuna Sucursal']) if sucursal_sel is not None else '',
                            'suc_resuelta': 'Si' if sucursal_sel is not None else 'No'
                        }
                        
                        # Guardar registro
                        if guardar_registro(nuevo_registro):
                            st.success("✅ Registro guardado exitosamente")
                            st.balloons()
                            # Enviar correo de confirmación (silencioso si falla)
                            enviar_confirmacion(
                                destinatario=email,
                                nombres=nombres,
                                apellido_paterno=apellido_paterno,
                                rut=rut_limpio,
                                curso_id=curso_actual['curso_id'],
                                region=region,
                                fecha_inicio=str(curso_actual.get('fecha_inicio', ''))
                            )
                            time.sleep(2)
                            st.rerun()

    except Exception as e:
        st.error(f"Error al cargar cursos: {str(e)}")

except Exception as e:
    st.error(f"Error en la aplicación: {str(e)}")