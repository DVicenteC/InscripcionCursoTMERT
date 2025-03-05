import streamlit as st
import pandas as pd
import json
import time
import requests
from datetime import datetime
from rut_chile import rut_chile
import io

# Configuración básica
st.set_page_config(page_title="Registro de Participantes", layout="wide")

# Constantes
COMUNAS_REGIONES_PATH = "comunas-regiones.json"
SECRET_PASSWORD = st.secrets["SECRET_PASSWORD"]
API_URL = st.secrets["API_URL"]  # URL del Apps Script publicado como aplicación web
API_KEY = st.secrets["API_KEY"]  # Clave API configurada en el Apps Script

# Listas para formulario
ROLES = ["TRABAJADOR", "PROFESIONAL SST", "MIEMBRO DE COMITÉ PARITARIO", 
         "MONITOR O DELEGADO", "DIRIGENTE SINDICAL", "EMPLEADOR", 
         "TRABAJADOR DEL OA", "OTROS"]

# Cargar archivo JSON de comunas y regiones
with open(COMUNAS_REGIONES_PATH, "r", encoding='utf-8') as file:
    comunas_regiones = json.load(file)

# Obtener lista de regiones
regiones = [region["region"] for region in comunas_regiones["regiones"]]

# Función para obtener datos de configuración desde la API
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

# Función para obtener registros desde la API
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
def guardar_registro(registro):
    try:
        response = requests.post(
            API_URL,
            params={"action": "addRegistro", "key": API_KEY},
            json=registro
        )
        data = response.json()
        
        if data['success']:
            return True
        else:
            st.error(f"Error al guardar registro: {data.get('error', 'Error desconocido')}")
            return False
    except Exception as e:
        st.error(f"Error al conectar con la API: {str(e)}")
        return False

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

    if password == SECRET_PASSWORD:
        st.sidebar.success("✅ Acceso concedido")
        
        # Obtener configuración de cursos
        df_cursos = get_config_data()
        
        # Selector de curso para activar
        if not df_cursos.empty:
            cursos_disponibles = df_cursos['curso_id'].tolist()
            
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
        
        # Crear nuevo curso
        st.sidebar.subheader("Crear Nuevo Curso")
        curso_id = st.sidebar.text_input("ID del Curso")
        fecha_inicio = st.sidebar.date_input("Fecha de Inicio")
        fecha_fin = st.sidebar.date_input("Fecha de Término")
        
        if curso_id:
            curso_id = curso_id + "-" + fecha_inicio.strftime("%Y%m%d") + "-" + fecha_fin.strftime("%Y%m%d")
        
        cupo_maximo = st.sidebar.number_input("Cupo Máximo", min_value=1, value=50) 
        
        if st.sidebar.button("Crear Curso"):
            if curso_id and fecha_fin > fecha_inicio:
                # Crear objeto de curso
                nuevo_curso = {
                    'curso_id': str(curso_id),
                    'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
                    'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
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

    # Verificar curso activo y mostrar formulario
    try:
        # Obtener curso activo
        curso_actual = get_curso_activo()
        
        if curso_actual:
            st.title("Inscripción Curso de 40 horas Protocolo TMERT para Implementadores - Empresas Adherentes de IST")
            st.write(f"Curso: {curso_actual['curso_id']}")
            st.write(f"Período: {curso_actual['fecha_inicio']} - {curso_actual['fecha_fin']}")
            
            # Verificar cupos disponibles
            df_registros = get_registros_data()
            if not df_registros.empty:
                inscritos_actuales = len(df_registros[df_registros['curso_id'] == curso_actual['curso_id']])
                cupos_disponibles = curso_actual['cupo_maximo'] - inscritos_actuales
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
            
            # Formulario de inscripción
            region = st.selectbox("Región (*)", regiones, key='region', on_change=update_comunas_state)
            comuna = st.selectbox("Comuna (*)", st.session_state.get('comunas', []), key='comuna')

            with st.form("registro_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    rut = st.text_input("RUT (*)", help="Formato: 12345678-9").upper()
                    nombres = st.text_input("Nombres (*)").upper()
                    apellido_paterno = st.text_input("Apellido Paterno (*)").upper()
                    email = st.text_input("Correo Electrónico (*)", help="ejemplo@dominio.com")
                    gmail = st.text_input("Correo Gmail (*)", help="ejemplo@gmail.com")
                    
                with col2:
                    apellido_materno = st.text_input("Apellido Materno (*)").upper()
                    nacionalidad = st.text_input("Nacionalidad (*)").upper()
                    rol = st.selectbox("Rol (*)", ROLES).upper()
                
                col3, col4 = st.columns(2)
                
                with col3:
                    rut_empresa = st.text_input("RUT Empresa (*)").upper()
                    razon_social = st.text_input("Razón Social (*)").upper()
        
                with col4:
                    direccion = st.text_input("Dirección (*)").upper()
                
                if st.form_submit_button("Enviar"):
                    # Verificar nuevamente los cupos disponibles
                    df_registros = get_registros_data()
                    if not df_registros.empty:
                        inscritos_actuales = len(df_registros[df_registros['curso_id'] == curso_actual['curso_id']])
                        cupos_disponibles = int(curso_actual['cupo_maximo']) - inscritos_actuales
                    else:
                        cupos_disponibles = int(curso_actual['cupo_maximo'])

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
                    elif '@gmail.com' not in gmail.lower():
                        st.error("Debe ingresar un correo Gmail válido")
                    else:    
                        # Preparar nuevo registro
                        nuevo_registro = {
                            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'curso_id': curso_actual['curso_id'],
                            'rut': rut,
                            'nombres': nombres,
                            'apellido_paterno': apellido_paterno,
                            'apellido_materno': apellido_materno,
                            'nacionalidad': nacionalidad,
                            'email': email,
                            'gmail': gmail,
                            'rol': rol,
                            'rut_empresa': rut_empresa,
                            'razon_social': razon_social,
                            'region': region,
                            'comuna': comuna,
                            'direccion': direccion
                        }
                        
                        # Guardar registro
                        if guardar_registro(nuevo_registro):
                            st.success("✅ Registro guardado exitosamente")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
            
            # Botón para ver inscritos
            if st.button("Ver inscritos"):
                df_registros = get_registros_data()
                if not df_registros.empty:
                    registros_curso = df_registros[df_registros['curso_id'] == curso_actual['curso_id']]

                    if not registros_curso.empty:
                        # Mostrar métricas de cupos en la parte superior
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Cupo Máximo", curso_actual['cupo_maximo'])
                        with col2:
                            st.metric("Inscritos", len(registros_curso))
                        with col3:
                            st.metric("Cupos Disponibles", int(curso_actual['cupo_maximo']) - len(registros_curso))

                        # Mostrar la tabla de inscritos
                        st.write("### Lista de Inscritos")
                        st.write(registros_curso)
                    else:
                        st.info("Aún no hay inscritos en este curso")
                else:
                    st.info("Aún no hay inscritos en este curso")
        else:
            st.warning("No hay ningún curso activo. El administrador debe crear uno.")
    except Exception as e:
        st.error(f"Error al verificar curso activo: {str(e)}")

except Exception as e:
    st.error(f"Error en la aplicación: {str(e)}")