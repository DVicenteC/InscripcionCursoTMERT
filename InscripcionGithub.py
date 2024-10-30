import streamlit as st
from github import Github
import base64
from datetime import datetime, timedelta
import pandas as pd
import io

# Configuración
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"] 
REPO_NAME = "DVicenteC/InscripcionCursoTMERT"
DATA_PATH = "data/registros.parquet"
CURSO_CONFIG_PATH = "data/config.json"

class GitHubStorage:
    def __init__(self):
        self.g = Github(GITHUB_TOKEN)
        self.repo = self.g.get_repo(REPO_NAME)
        
    def read_data(self):
        try:
            # Leer archivo de registros
            content = self.repo.get_contents(DATA_PATH)
            data = base64.b64decode(content.content)
            return pd.read_parquet(io.BytesIO(data))
        except:
            return pd.DataFrame()
    
    def save_data(self, df):
        buffer = io.BytesIO()
        df.to_parquet(buffer)
        content = base64.b64encode(buffer.getvalue()).decode()
        
        try:
            # Intentar actualizar archivo existente
            file = self.repo.get_contents(DATA_PATH)
            self.repo.update_file(
                DATA_PATH,
                f"Actualización de registros {datetime.now()}",
                content,
                file.sha
            )
        except:
            # Crear nuevo archivo si no existe
            self.repo.create_file(
                DATA_PATH,
                f"Creación inicial de registros {datetime.now()}",
                content
            )
    
    def read_config(self):
        try:
            content = self.repo.get_contents(CURSO_CONFIG_PATH)
            return pd.read_json(base64.b64decode(content.content))
        except:
            # Configuración por defecto
            return pd.DataFrame([{
                'curso_id': datetime.now().strftime("%Y%m%d"),
                'fecha_inicio': datetime.now().date(),
                'fecha_fin': (datetime.now() + timedelta(days=30)).date(),
                'estado': 'ACTIVO'
            }])
            
    def save_config(self, config_df):
        content = config_df.to_json()
        try:
            file = self.repo.get_contents(CURSO_CONFIG_PATH)
            self.repo.update_file(
                CURSO_CONFIG_PATH,
                f"Actualización de configuración {datetime.now()}",
                content,
                file.sha
            )
        except:
            self.repo.create_file(
                CURSO_CONFIG_PATH,
                f"Creación inicial de configuración {datetime.now()}",
                content
            )

# Modificar las funciones existentes para usar GitHubStorage
def init_database():
    storage = GitHubStorage()
    config = storage.read_config()
    
    # Verificar si el curso está en período válido
    curso_actual = config[config['estado'] == 'ACTIVO'].iloc[0]
    fecha_actual = datetime.now().date()
    
    if fecha_actual > curso_actual['fecha_fin']:
        st.error("El período de inscripción ha finalizado")
        st.stop()
    
    return storage, curso_actual

def save_registro(storage, data_dict):
    try:
        df = storage.read_data()
        df = pd.concat([df, pd.DataFrame([data_dict])], ignore_index=True)
        storage.save_data(df)
        return True
    except Exception as e:
        st.error(f"Error al guardar registro: {str(e)}")
        return False
    
# Después de las funciones existentes

# Configuración de la página
st.set_page_config(page_title="Registro de Participantes", layout="wide")

# Listas de opciones
ROLES = [
    "TRABAJADOR",
    "PROFESIONAL SST",
    "MIEMBRO DE COMITÉ PARITARIO",
    "MONITOR O DELEGADO",
    "DIRIGENTE SINDICAL",
    "EMPLEADOR",
    "TRABAJADOR DEL OA",
    "OTROS"
]

REGIONES = [
    "Región de Arica y Parinacota",
    "Región de Tarapacá",
    # ... (resto de las regiones)
]

try:
    # Inicializar almacenamiento y obtener configuración
    storage, curso_actual = init_database()
    
    # Mostrar información del curso
    st.title("Formulario de Inscripción a Curso")
    st.write(f"Curso ID: {curso_actual['curso_id']}")
    st.write(f"Período de inscripción: {curso_actual['fecha_inicio']} - {curso_actual['fecha_fin']}")
    
    # Crear formulario
    with st.form("registro_form"):
        # Datos personales
        st.subheader("Datos Personales")
        col1, col2 = st.columns(2)
        
        with col1:
            rut = st.text_input("RUT (*)", help="Formato: 12345678-9")
            nombres = st.text_input("Nombres (*)")
            apellido_paterno = st.text_input("Apellido Paterno (*)")
            
        with col2:
            apellido_materno = st.text_input("Apellido Materno")
            nacionalidad = st.text_input("Nacionalidad (*)")
            rol = st.selectbox("Rol (*)", ROLES)
        
        # Datos de empresa
        st.subheader("Datos de la Empresa")
        col3, col4 = st.columns(2)
        
        with col3:
            rut_empresa = st.text_input("RUT Empresa (*)")
            razon_social = st.text_input("Razón Social (*)")
            region = st.selectbox("Región (*)", REGIONES)
            
        with col4:
            comuna = st.text_input("Comuna (*)")
            direccion = st.text_input("Dirección (*)")
        
        submitted = st.form_submit_button("Enviar")
        
        if submitted:
            # Validar datos
            if not all([rut, nombres, apellido_paterno, nacionalidad, 
                       rut_empresa, razon_social, region, comuna, direccion]):
                st.error("Por favor complete todos los campos obligatorios")
            else:
                # Crear registro
                new_data = {
                    'fecha_registro': datetime.now(),
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
                
                if save_registro(storage, new_data):
                    st.success("Registro guardado exitosamente")
                    st.balloons()
                
except Exception as e:
    st.error(f"Error: {str(e)}")