import requests
import streamlit as st

# Usar los mismos secrets que tienes configurados
API_URL = st.secrets["API_URL"]
API_KEY = st.secrets["API_KEY"]

print("=" * 50)
print("PRUEBA DE CONEXIÓN A LA API")
print("=" * 50)

# Prueba 1: Test básico
print("\n1. Probando endpoint de test...")
try:
    response = requests.get(f"{API_URL}?action=test&key={API_KEY}")
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'No especificado')}")
    print(f"Respuesta Raw (primeros 500 chars):")
    print(response.text[:500])
    print("\nRespuesta JSON:")
    print(response.json())
except Exception as e:
    print(f"❌ Error: {e}")

# Prueba 2: getAsistencias
print("\n" + "=" * 50)
print("2. Probando getAsistencias...")
try:
    response = requests.get(f"{API_URL}?action=getAsistencias&key={API_KEY}")
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'No especificado')}")
    print(f"Respuesta Raw (primeros 500 chars):")
    print(response.text[:500])
    print("\nRespuesta JSON:")
    print(response.json())
except Exception as e:
    print(f"❌ Error: {e}")

# Prueba 3: getCursoActivo
print("\n" + "=" * 50)
print("3. Probando getCursoActivo...")
try:
    response = requests.get(f"{API_URL}?action=getCursoActivo&key={API_KEY}")
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'No especificado')}")
    print(f"Respuesta Raw (primeros 500 chars):")
    print(response.text[:500])
    print("\nRespuesta JSON:")
    print(response.json())
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 50)
print("FIN DE PRUEBAS")
print("=" * 50)
