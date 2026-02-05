# 📚 Sistema de Inscripción y Asistencia a Cursos

Sistema completo para gestionar inscripciones y registro de asistencia a cursos, optimizado para alta concurrencia.

## 🚀 Inicio Rápido

### **Instalación**

```bash
# Clonar repositorio
git clone [tu-repo]
cd InscripcionCursoTMERT

# Instalar dependencias
pip install -r requirements.txt

# Instalar DuckDB (para sistema de asistencia)
pip install duckdb

# Configurar secrets
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
# Editar secrets.toml con tus credenciales
```

### **Ejecutar**

```bash
# Sistema de Inscripción
streamlit run InscripcionCSV.py

# Sistema de Asistencia
streamlit run AsistenciaCurso.py
```

---

## 📦 Archivos Principales

### **Aplicaciones**

- `InscripcionCSV.py` - Sistema de inscripción de participantes (con cache)
- `AsistenciaCurso.py` - Sistema de registro de asistencia (SIN buffer - versión simple)
- `AsistenciaCurso_ConBuffer.py` - Sistema de asistencia (CON buffer - alta concurrencia)
- `db_buffer.py` - Motor del buffer con DuckDB

### **Backend**

- `Codigo_ACTUALIZADO.gs` - Google Apps Script (backend en Google Sheets)
- `comunas-regiones.json` - Datos de comunas y regiones de Chile

### **Configuración**

- `.streamlit/secrets.toml` - Credenciales y configuración (no subir a Git)
- `requirements.txt` - Dependencias Python

---

## 📖 Documentación

**Lee PRIMERO:**
- **`IMPLEMENTACION_FINAL.md`** ← Guía completa de implementación paso a paso

**Referencia:**
- `BUFFER_GUIDE.md` - Guía del sistema de buffer para alta concurrencia
- `RESULTADOS_PRUEBAS.md` - Resultados de pruebas de rendimiento
- `OPTIMIZACIONES.md` - Optimizaciones implementadas

**Técnico:**
- `BATCH_VS_INDIVIDUAL.md` - Comparación de métodos de sincronización
- `COMPARACION_SOLUCIONES.md` - Análisis de alternativas

---

## 🎯 Sistemas

### **1. Sistema de Inscripción**

**Características:**
- ✅ Registro de participantes con validación de RUT
- ✅ Gestión de cursos multi-región
- ✅ Cache de Streamlit (5 minutos)
- ✅ Retry logic automático
- ✅ 3 sesiones por curso

**Tecnología:**
- Streamlit + Google Sheets
- Cache en memoria
- Apps Script como API

**Capacidad:**
- 20-30 inscripciones sin problemas
- Latencia: 800-1200ms (primera carga), <50ms (cache)

---

### **2. Sistema de Asistencia**

**Versión Simple (Actual):**
- Registro directo a Google Sheets
- Cache de datos
- Adecuado para <30 usuarios simultáneos

**Versión con Buffer (Alta Concurrencia):**
- Buffer local con DuckDB
- Escrituras instantáneas (<100ms)
- Sincronización automática cada 60s
- Dashboard de monitoreo
- Capacidad: 1000+ usuarios simultáneos

**Cuándo usar Buffer:**
- ✅ >50 usuarios marcando asistencia simultáneamente
- ✅ Necesitas respuesta instantánea
- ✅ Evitar timeouts y race conditions

**Cómo activar Buffer:**
```bash
# Instalar DuckDB
pip install duckdb

# Activar versión con buffer
mv AsistenciaCurso.py AsistenciaCurso_SinBuffer.py
mv AsistenciaCurso_ConBuffer.py AsistenciaCurso.py

# Ejecutar
streamlit run AsistenciaCurso.py
```

---

## 🔧 Configuración

### **Google Apps Script**

1. Abrir Google Sheets
2. Extensiones → Apps Script
3. Copiar contenido de `Codigo_ACTUALIZADO.gs`
4. Guardar y Deploy como Web App
5. Copiar URL del deployment
6. Actualizar `.streamlit/secrets.toml`

### **Secrets (`.streamlit/secrets.toml`)**

```toml
SECRET_PASSWORD = "tu_password_admin"
API_URL = "https://script.google.com/macros/s/TU_ID/exec"
API_KEY = "tu_clave_api_segura"
```

---

## 📊 Estructura de Google Sheets

### **Hoja "Config" (Cursos)**

```
curso_id | region | fecha_inicio | fecha_fin | estado | cupo_maximo | fecha_sesion_1 | fecha_sesion_2 | fecha_sesion_3
---------|--------|--------------|-----------|--------|-------------|----------------|----------------|---------------
RM-Mar26 | RM     | 04-03-2026   | 13-03-2026| activo | 50          | 04-03-2026     | 06-03-2026     | 13-03-2026
```

### **Hoja "Hoja 1" (Inscripciones)**

```
curso_id | rut         | nombre        | email           | telefono    | region | comuna | rol        | sexo
---------|-------------|---------------|-----------------|-------------|--------|--------|------------|------
RM-Mar26 | 12345678-9  | Juan Pérez    | juan@email.com  | 912345678   | RM     | ...    | TRABAJADOR | HOMBRE
```

### **Hoja "Asistencias"**

```
id              | curso_id | rut        | sesion | fecha_registro      | estado   | metodo
----------------|----------|------------|--------|---------------------|----------|--------
ASIST-123-456   | RM-Mar26 | 12345678-9 | 1      | 2026-03-04 09:00:00 | presente | streamlit
```

---

## 🎯 Uso

### **Modo Administrador**

**Inscripciones:**
1. Abrir `InscripcionCSV.py`
2. Ingresar contraseña en sidebar
3. Crear curso o inscribir participantes
4. Botón "Actualizar Datos" para refrescar cache

**Asistencias:**
1. Abrir `AsistenciaCurso.py`
2. Ingresar contraseña en sidebar
3. Gestionar asistencias manualmente
4. Ver estadísticas y exportar datos

### **Modo Participante**

**Marcar Asistencia:**
1. Abrir `AsistenciaCurso.py` (sin contraseña)
2. Seleccionar curso con sesión hoy
3. Ingresar RUT
4. Confirmar asistencia
5. Recibir confirmación instantánea

---

## 📈 Rendimiento

### **Sistema de Inscripción (Con Cache)**

- Primera carga: 800-1200ms
- Cache hit: <50ms
- Tasa de cache hit: ~70-80%

### **Sistema de Asistencia (Con Buffer)**

- Escritura: <100ms
- Sincronización: 50 registros en ~2.5s
- Capacidad: 1000+ usuarios simultáneos
- Auto-sync: cada 60 segundos

---

## 🔍 Monitoreo

### **Dashboard de Asistencias (Con Buffer)**

En sidebar aparece:
```
📊 Estado del Buffer
Total: 150
Sincronizadas: 145
Pendientes: 5
Fallidas: 0

[🔄 Sincronizar Ahora]
[🗑️ Limpiar Sincronizados]
```

**Indicadores de salud:**
- ✅ Pendientes < 50
- ✅ Fallidos = 0
- ⚠️ Si Pendientes > 100 → Click "Sincronizar Ahora"

---

## 🛠️ Mantenimiento

### **Limpiar Cache**

```bash
# Desde la app: Click "Actualizar Datos"
# O manualmente:
streamlit cache clear
```

### **Limpiar Buffer**

```bash
# Desde la app: Tab Mantenimiento → Limpiar Registros
# O manualmente:
rm asistencias_buffer.duckdb
```

---

## 📞 Soporte

**Problemas comunes:**
- Ver `IMPLEMENTACION_FINAL.md` sección Troubleshooting
- Revisar logs de Apps Script en Google
- Verificar conectividad con Google Sheets

---

## 📝 Licencia

[Tu licencia aquí]

---

## 🚀 Próximos Pasos

1. Leer `IMPLEMENTACION_FINAL.md`
2. Actualizar Apps Script en Google Sheets
3. Configurar `.streamlit/secrets.toml`
4. Probar localmente
5. Implementar en producción
6. Monitorear y ajustar

---

**Versión:** 1.0
**Última actualización:** Febrero 2026
