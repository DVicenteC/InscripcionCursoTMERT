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