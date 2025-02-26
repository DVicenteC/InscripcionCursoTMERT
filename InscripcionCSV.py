import streamlit as st
from github import Github
import base64
from datetime import datetime
import pandas as pd
import io
from rut_chile import rut_chile
import json
import time
from cryptography.fernet import Fernet

import streamlit as st
from github import Github
import base64
from datetime import datetime
import pandas as pd
import io
from rut_chile import rut_chile
import json
import time
from cryptography.fernet import Fernet

# Clase para manejar la anonimización
class DataAnonymizer:
    def __init__(self):
        self.key = st.secrets["ENCRYPTION_KEY"].encode()
        self.cipher_suite = Fernet(self.key)
        
    def encrypt_value(self, value):
        """Encripta un valor individual"""
        if pd.isna(value):
            return value
        return self.cipher_suite.encrypt(str(value).encode()).decode()
    
    def decrypt_value(self, value):
        """Desencripta un valor individual"""
        if pd.isna(value):
            return value
        return self.cipher_suite.decrypt(str(value).encode()).decode()

    def anonymize_data(self, data):
        """Encripta campos sensibles del DataFrame"""
        if isinstance(data, dict):
            data = pd.DataFrame([data])
            
        # Campos a anonimizar
        sensitive_fields = ['rut', 'nombres', 'apellido_paterno', 'apellido_materno', 
                          'rut_empresa', 'razon_social']
        
        df_anon = data.copy()
        
        for field in sensitive_fields:
            if field in df_anon.columns:
                df_anon[field] = df_anon[field].apply(self.encrypt_value)
                
        return df_anon
    
    def deanonymize_data(self, data):
        """Desencripta campos sensibles del DataFrame"""
        if data.empty:
            return data
            
        df_deanon = data.copy()
        
        sensitive_fields = ['rut', 'nombres', 'apellido_paterno', 'apellido_materno', 
                          'rut_empresa', 'razon_social']
        
        for field in sensitive_fields:
            if field in df_deanon.columns:
                df_deanon[field] = df_deanon[field].apply(self.decrypt_value)
                
        return df_deanon

# Funciones para manejar archivos parquet en GitHub
def save_to_parquet(df, repo, path):
    """Guarda DataFrame en formato parquet en GitHub"""
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer)
    parquet_content = base64.b64encode(parquet_buffer.getvalue()).decode()
    
    try:
        file = repo.get_contents(path)
        repo.update_file(
            path,
            f"Actualización registros {datetime.now()}",
            parquet_content,
            file.sha
        )
    except:
        repo.create_file(
            path,
            f"Creación registros {datetime.now()}",
            parquet_content
        )

def load_from_parquet(repo, path):
    """Carga DataFrame desde archivo parquet en GitHub"""
    try:
        file = repo.get_contents(path)
        parquet_content = base64.b64decode(file.content)
        return pd.read_parquet(io.BytesIO(parquet_content))
    except:
        return pd.DataFrame()

# Inicializar el anonymizer como variable global
anonymizer = DataAnonymizer()
# Configuración básica
st.set_page_config(page_title="Registro de Participantes", layout="wide")

# Constantes
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = "DVicenteC/InscripcionCursoTMERT"
DATA_PATH = "data/registros.parquet"
CURSO_CONFIG_PATH = "data/config.json"
COMUNAS_REGIONES_PATH = "comunas-regiones.json"
SECRET_PASSWORD = st.secrets["SECRET_PASSWORD"]

# Cargar archivo JSON de comunas y regiones
with open(COMUNAS_REGIONES_PATH, "r", encoding='utf-8') as file:
    comunas_regiones = json.load(file)

# Obtener lista de regiones
regiones = [region["region"] for region in comunas_regiones["regiones"]]

# Listas para formulario
ROLES = ["TRABAJADOR", "PROFESIONAL SST", "MIEMBRO DE COMITÉ PARITARIO", 
         "MONITOR O DELEGADO", "DIRIGENTE SINDICAL", "EMPLEADOR", 
         "TRABAJADOR DEL OA", "OTROS"]

try:
    # Inicializar GitHub
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    # Panel de Administración
    # Panel de Administración
    st.sidebar.title("Panel de Control")
    password = st.sidebar.text_input("Contraseña", type="password")

    if password == SECRET_PASSWORD:
        st.sidebar.success("✅ Acceso concedido")
        
        # Leer configuración de cursos
        config_file = repo.get_contents(CURSO_CONFIG_PATH)
        config_data = json.loads(base64.b64decode(config_file.content))
        df_cursos = pd.DataFrame(config_data)
        df_cursos['cupo_maximo'] = pd.to_numeric(df_cursos['cupo_maximo'])
        
        # Selector de curso para activar
        cursos_disponibles = df_cursos['curso_id'].tolist()
        curso_seleccionado = st.sidebar.selectbox(
            "Seleccionar Curso para Activar",
            cursos_disponibles,
            index=0
        )
        
        if st.sidebar.button("Activar Curso"):
            # Marcar el curso seleccionado como activo y los demás como inactivos
            df_cursos['estado'] = df_cursos['curso_id'].apply(lambda x: 'ACTIVO' if x == curso_seleccionado else 'INACTIVO')
            
            # Guardar configuración actualizada en GitHub
            config_json = df_cursos.to_json(orient='records')
            file = repo.get_contents(CURSO_CONFIG_PATH)
            repo.update_file(
                CURSO_CONFIG_PATH,
                f"Activación de curso {curso_seleccionado}",
                config_json,
                file.sha
            )
            
            st.sidebar.success(f"✅ Curso {curso_seleccionado} activado")
        
        # Crear nuevo curso
        st.sidebar.subheader("Crear Nuevo Curso")
        curso_id = st.sidebar.text_input("ID del Curso")
        fecha_inicio = st.sidebar.date_input("Fecha de Inicio")
        fecha_fin = st.sidebar.date_input("Fecha de Término")
        curso_id = curso_id + "-" + fecha_inicio.strftime("%Y%m%d") + "-" + fecha_fin.strftime("%Y%m%d")
        
        cupo_maximo = st.sidebar.number_input("Cupo Máximo", min_value=1, value=50) 
        if st.sidebar.button("Crear Curso"):
            if curso_id and fecha_fin > fecha_inicio:
                try:
                    # Leer configuración existente
                    try:
                        file = repo.get_contents(CURSO_CONFIG_PATH)
                        config_existente = json.loads(base64.b64decode(file.content))
                        df_config = pd.DataFrame(config_existente)
                    except:
                        df_config = pd.DataFrame()

                    # Agregar nuevo curso
                    nuevo_curso = pd.DataFrame([{
                        'curso_id': str(curso_id),
                        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'),
                        'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),
                        'cupo_maximo': int(cupo_maximo),  # Agregamos el cupo máximo
                        'estado': 'ACTIVO'
                    }])

                    # Combinar configuración
                    df_config = pd.concat([df_config, nuevo_curso], ignore_index=True)

                    # Guardar configuración
                    config_json = df_config.to_json(orient='records')
                    try:
                        file = repo.get_contents(CURSO_CONFIG_PATH)
                        repo.update_file(
                            CURSO_CONFIG_PATH,
                            f"Actualización curso {datetime.now()}",
                            config_json,
                            file.sha
                        )
                    except:
                        repo.create_file(
                            CURSO_CONFIG_PATH,
                            f"Creación curso {datetime.now()}",
                            config_json
                        )
                    st.sidebar.success("✅ Curso creado exitosamente")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error al crear curso: {str(e)}")

        # Gestión de registros existentes
        st.sidebar.subheader("Gestión de Registros")
        
        try:
            # Leer configuración de cursos
            config_file = repo.get_contents(CURSO_CONFIG_PATH)
            config_data = json.loads(base64.b64decode(config_file.content))
            df_config = pd.DataFrame(config_data)
            
            # Leer registros existentes
            try:
                registros_file = repo.get_contents(DATA_PATH)
                df_registros = pd.read_csv(io.StringIO(base64.b64decode(registros_file.content).decode()))
            except:
                df_registros = pd.DataFrame()
            
            # Selector de curso para descargar
            cursos_disponibles = df_config['curso_id'].unique().tolist()
            curso_seleccionado = st.sidebar.selectbox(
                "Seleccionar Curso para Descargar",
                cursos_disponibles,
                index=None,
                placeholder="Seleccione un curso..."
            )
            
            if curso_seleccionado and st.sidebar.button("Descargar Registros"):
                try:
                    # Cargar datos desde parquet
                    df_registros = load_from_parquet(repo, DATA_PATH)
                    
                    # Desencriptar datos para la descarga
                    df_registros_desc = anonymizer.deanonymize_data(df_registros)
                    
                    # Filtrar registros del curso seleccionado
                    registros_curso = df_registros_desc[df_registros_desc['curso_id'] == curso_seleccionado]
                    
                    if not registros_curso.empty:
                        # Preparar Excel para descarga
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            registros_curso.to_excel(
                                writer,
                                sheet_name='Datos',
                                index=False,
                                float_format='%.2f',
                                columns=[
                                    'fecha_registro', 'curso_id', 'rut', 'nombres',
                                    'apellido_paterno', 'apellido_materno', 'nacionalidad',
                                    'rol', 'rut_empresa', 'razon_social', 'region',
                                    'comuna', 'direccion'
                                ]
                            )
                            
                            # Formato para el archivo Excel
                            workbook = writer.book
                            worksheet = writer.sheets['Datos']
                            header_format = workbook.add_format({
                                'bold': True,
                                'bg_color': '#D8E4BC',
                                'border': 1
                            })
                            
                            # Aplicar formato a las columnas
                            for col_num, value in enumerate(registros_curso.columns.values):
                                worksheet.write(0, col_num, value, header_format)
                                worksheet.set_column(col_num, col_num, len(str(value)) + 2)
                            
                            worksheet.freeze_panes(1, 0)
                        
                        buffer.seek(0)
                        st.sidebar.download_button(
                            label=f"📥 Descargar Registros ({len(registros_curso)} inscritos)",
                            data=buffer.getvalue(),
                            file_name=f"registros_curso_{curso_seleccionado}.xlsx",
                            mime="application/vnd.ms-excel"
                        )
                    else:
                        st.sidebar.warning("No hay registros para este curso")
                        
                except Exception as e:
                    st.sidebar.error(f"Error al preparar la descarga: {str(e)}")
            
            # Reinicio de base de datos (no funcionó)
                        
        except Exception as e:
            st.sidebar.error(f"Error al cargar datos: {str(e)}")

    # Verificar curso activo y mostrar formulario
    
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
        config_file = repo.get_contents(CURSO_CONFIG_PATH)
        config_data = json.loads(base64.b64decode(config_file.content))

        # Agregar estas líneas de depuración
        #st.write("Config data:", config_data)

        df_cursos = pd.DataFrame(config_data)

        # Si no existe la columna cupo_maximo, agregarla con valor por defecto
        if 'cupo_maximo' not in df_cursos.columns:
            df_cursos['cupo_maximo'] = 50  # valor por defecto

            # Actualizar el archivo config.json con la nueva columna
            config_json = df_cursos.to_json(orient='records')
            repo.update_file(
                CURSO_CONFIG_PATH,
                "Agregando columna cupo_maximo",
                config_json,
                config_file.sha
            )

        df_cursos['cupo_maximo'] = pd.to_numeric(df_cursos['cupo_maximo'])

        # Buscar curso activo
        curso_activo = df_cursos[df_cursos['estado'] == 'ACTIVO']
        
        if not curso_activo.empty:
            curso_actual = curso_activo.iloc[0]
            
            st.title("Inscripción Curso de 40 horas Protocolo TMERT para Implementadores - Empresas Adherentes de IST")
            st.write(f"Curso: {curso_actual['curso_id']}")
            st.write(f"Período: {curso_actual['fecha_inicio']} - {curso_actual['fecha_fin']}")
            
            # Agregar esto:
            try:
                registros_file = repo.get_contents(DATA_PATH)
                df_registros = pd.read_csv(io.StringIO(base64.b64decode(registros_file.content).decode()))
                inscritos_actuales = len(df_registros[df_registros['curso_id'] == curso_actual['curso_id']])
                cupos_disponibles = curso_actual['cupo_maximo'] - inscritos_actuales

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
            except:
                # Si no hay archivo de registros, inicializar contadores
                inscritos_actuales = 0
                cupos_disponibles = curso_actual['cupo_maximo']
            
            
            
            # [Aquí va el resto del código del formulario, que se mantiene igual]
            region = st.selectbox("Región (*)", regiones, key='region', on_change=update_comunas_state)
            
            comuna = st.selectbox("Comuna (*)", st.session_state.get('comunas', []), key='comuna')

            with st.form("registro_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    rut = st.text_input("RUT (*)", help="Formato: 12345678-9").upper()
                    nombres = st.text_input("Nombres (*)").upper()
                    apellido_paterno = st.text_input("Apellido Paterno (*)").upper()
                    
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
                    # Seleccionar región y comuna fuera de un formulario
                    
                if st.form_submit_button("Enviar"):
                    try:
                        # Cargar registros existentes (si hay)
                        df_registros = load_from_parquet(repo, DATA_PATH)
                        
                        # Crear el nuevo registro primero
                        nuevo_registro = {
                            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'curso_id': curso_actual['curso_id'],
                            'rut': rut,
                            'nombres': nombres,
                            'apellido_paterno': apellido_paterno,
                            'apellido_materno': apellido_materno,
                            'nacionalidad': nacionalidad,
                            'rol': rol,
                            'rut_empresa': rut_empresa,
                            'razon_social': razon_social,
                            'region': region,
                            'comuna': comuna,
                            'direccion': direccion
                        }

                        # Validaciones básicas
                        if not all([rut, nombres, apellido_paterno, nacionalidad, 
                                    rut_empresa, razon_social, region, comuna, direccion]):
                            st.error("Complete todos los campos obligatorios")
                            st.stop()
                        
                        if not rut_chile.is_valid_rut(rut):
                            st.error("RUT personal inválido")
                            st.stop()
                            
                        if not rut_chile.is_valid_rut(rut_empresa):
                            st.error("RUT empresa inválido")
                            st.stop()

                        # Verificar cupos solo si hay registros existentes
                        if not df_registros.empty:
                            df_registros_desc = anonymizer.deanonymize_data(df_registros)
                            inscritos_actuales = len(df_registros_desc[df_registros_desc['curso_id'] == curso_actual['curso_id']])
                            cupos_disponibles = curso_actual['cupo_maximo'] - inscritos_actuales

                            if cupos_disponibles <= 0:
                                st.error("Lo sentimos, mientras se procesaba su solicitud se agotaron los cupos disponibles.")
                                st.stop()

                            # Verificar duplicados solo si hay registros existentes
                            registro_a_validar = f"{rut}|{rut_empresa}"
                            df_curso_actual = df_registros_desc[df_registros_desc['curso_id'] == curso_actual['curso_id']]
                            
                            if not df_curso_actual.empty:
                                df_curso_actual["ID_registro"] = (
                                    df_curso_actual["rut"].astype(str) + "|" +
                                    df_curso_actual["rut_empresa"].astype(str)
                                )
                                
                                if registro_a_validar in df_curso_actual["ID_registro"].values:
                                    st.warning(f"Este registro ya existe para el curso {curso_actual['curso_id']}")
                                    st.stop()

                        # Anonimizar el nuevo registro
                        df_nuevo = anonymizer.anonymize_data(nuevo_registro)
                        
                        # Combinar con registros existentes o crear nuevo DataFrame
                        if df_registros.empty:
                            df_actualizado = df_nuevo
                        else:
                            df_actualizado = pd.concat([df_registros, df_nuevo], ignore_index=True)
                        
                        # Guardar en formato parquet
                        save_to_parquet(df_actualizado, repo, DATA_PATH)
                        
                        st.success("✅ Registro guardado exitosamente")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error al guardar registro: {str(e)}")
                        # Para debugging
                        st.write("Detalles del error:", e)
                            
            if st.button("Ver inscritos"):
                try:
                    # Cargar datos desde parquet
                    df_registros = load_from_parquet(repo, DATA_PATH)
                    
                    # Desencriptar datos para mostrarlos
                    df_registros_desc = anonymizer.deanonymize_data(df_registros)
                    
                    # Filtrar por curso actual
                    registros_curso = df_registros_desc[df_registros_desc['curso_id'] == curso_actual['curso_id']]

                    if not registros_curso.empty:
                        # Mostrar métricas de cupos en la parte superior
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Cupo Máximo", curso_actual['cupo_maximo'])
                        with col2:
                            st.metric("Inscritos", len(registros_curso))
                        with col3:
                            st.metric("Cupos Disponibles", curso_actual['cupo_maximo'] - len(registros_curso))

                        # Mostrar la tabla de inscritos
                        st.write("### Lista de Inscritos")
                        st.write(registros_curso)
                    else:
                        st.info("Aún no hay inscritos en este curso")
                except Exception as e:
                    st.error(f"Error al cargar registros: {str(e)}")
            
        else:
            st.warning("No hay ningún curso activo. El administrador debe crear uno.")
    except Exception as e:
        st.error(f"Error al verificar curso activo: {str(e)}")

except Exception as e:
    st.error(f"Error en la aplicación: {str(e)}")
