# Sistema de Inscripción y Registro de Asistencia

Este proyecto contiene dos aplicaciones Streamlit independientes para la gestión completa de cursos:

## 📋 Aplicaciones

### 1. InscripcionCSV.py - Sistema de Inscripción
Permite la inscripción de participantes a cursos con gestión de cupos y sesiones.

**Características:**
- Creación de cursos con ID, fechas y cupos máximos
- Configuración de 3 fechas de sesiones por curso
- Formulario de inscripción con validación de RUT
- Panel administrativo para:
  - Crear y activar cursos
  - Visualizar inscritos
  - Descargar listados en Excel

**Datos requeridos por participante:**
- RUT, nombres, apellidos
- Sexo, nacionalidad
- Email y Gmail
- Rol en la empresa
- Datos de la empresa (RUT, razón social, dirección)
- Región y comuna

### 2. AsistenciaCurso.py - Sistema de Registro de Asistencia
Permite el registro de asistencia por sesión y genera reportes de aprobación.

**Características:**

#### Modo Público (Sin contraseña):
- **Autoregistro de asistencia:** Los participantes ingresan su RUT para marcar asistencia
- Selección de sesión (1, 2 o 3)
- Validación automática contra lista de inscritos
- Prevención de registro duplicado por sesión

#### Modo Administrador (Con contraseña):

##### 📝 Marcar Asistencia Manual
- Selección de participante desde lista de inscritos
- Selección de sesión
- Registro manual de asistencia
- Prevención de duplicados

##### 📊 Ver Reportes y Estadísticas
- Estadísticas por sesión (presentes/total, porcentaje)
- Tabla detallada con asistencia por participante
- Columnas: Sesión 1, Sesión 2, Sesión 3, Porcentaje, Estado
- Código de colores: verde para aprobados, rojo para reprobados
- Resumen de aprobación (total, aprobados, reprobados)

##### 📥 Descargar Reporte Excel
- Exportación de reporte completo en formato Excel
- Formato profesional con encabezados y estilos
- Incluye todas las sesiones y estado final

##### ✏️ Editar/Corregir Asistencias
- Visualización de todos los registros de asistencia
- Eliminación de registros erróneos
- Información detallada de cada registro

## 📊 Estructura de Datos

### Cursos (Config)
```json
{
  "curso_id": "PVOTME-5-20250303-20250314",
  "fecha_inicio": "2025-03-03",
  "fecha_fin": "2025-03-14",
  "fecha_sesion_1": "2025-03-03",
  "fecha_sesion_2": "2025-03-05",
  "fecha_sesion_3": "2025-03-07",
  "cupo_maximo": 100,
  "estado": "ACTIVO"
}
```

### Inscripciones (Registros)
```json
{
  "fecha_registro": "2025-01-20 10:30:00",
  "curso_id": "PVOTME-5-20250303-20250314",
  "rut": "12345678-9",
  "nombres": "JUAN",
  "apellido_paterno": "PEREZ",
  "apellido_materno": "GONZALEZ",
  "nacionalidad": "CHILENA",
  "email": "juan@empresa.cl",
  "gmail": "juan@gmail.com",
  "sexo": "HOMBRE",
  "rol": "TRABAJADOR",
  "rut_empresa": "76543210-K",
  "razon_social": "EMPRESA EJEMPLO S.A.",
  "region": "Región Metropolitana",
  "comuna": "Santiago",
  "direccion": "Av. Principal 123"
}
```

### Asistencias
```json
{
  "curso_id": "PVOTME-5-20250303-20250314",
  "rut": "12345678-9",
  "sesion": 1,
  "fecha_registro": "2025-03-03 09:15:00",
  "estado": "PRESENTE",
  "metodo": "AUTOREGISTRO"
}
```

## 🎓 Criterios de Aprobación

- **Total de sesiones:** 3 sesiones por curso
- **Porcentaje mínimo:** 75% de asistencia (al menos 2.25 sesiones)
- **Estado APROBADO:** Asistencia >= 75%
- **Estado REPROBADO:** Asistencia < 75%

Ejemplos:
- 3/3 sesiones = 100% = APROBADO ✅
- 2/3 sesiones = 66.7% = REPROBADO ❌
- 3/3 sesiones = 100% = APROBADO ✅

## 🔧 Configuración del Backend (Google Apps Script)

Para que el sistema de asistencia funcione, debes actualizar tu Apps Script con las siguientes funciones:

### Nuevas acciones requeridas:

1. **getAsistencias** - Obtener todos los registros de asistencia
2. **addAsistencia** - Agregar nuevo registro de asistencia
3. **deleteAsistencia** - Eliminar registro de asistencia

### Estructura de la hoja "Asistencias" en Google Sheets:

| curso_id | rut | sesion | fecha_registro | estado | metodo | id |
|----------|-----|--------|----------------|--------|--------|-----|
| PVOTME-5-... | 12345678-9 | 1 | 2025-03-03 09:15:00 | PRESENTE | AUTOREGISTRO | 1 |

### Actualización de la hoja "Config":

Agregar las columnas:
- fecha_sesion_1
- fecha_sesion_2
- fecha_sesion_3

## 📦 Instalación y Uso

### Requisitos
```bash
pip install -r requirements.txt
```

### Ejecutar Inscripción
```bash
streamlit run InscripcionCSV.py
```

### Ejecutar Asistencia
```bash
streamlit run AsistenciaCurso.py
```

### Configuración (.streamlit/secrets.toml)
```toml
SECRET_PASSWORD = "tu_contraseña_aqui"
API_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"
API_KEY = "tu_api_key_aqui"
```

## 🚀 Despliegue en Streamlit Cloud

### Para InscripcionCSV.py:
1. Crear nueva app en Streamlit Cloud
2. Conectar repositorio GitHub
3. Main file path: `InscripcionCSV.py`
4. Configurar secrets en Settings

### Para AsistenciaCurso.py:
1. Crear nueva app en Streamlit Cloud
2. Conectar el MISMO repositorio GitHub
3. Main file path: `AsistenciaCurso.py`
4. Configurar los MISMOS secrets en Settings

## 📝 Flujo de Trabajo Recomendado

1. **Crear curso** (InscripcionCSV.py - Admin)
   - Ingresar ID, fechas de inicio/fin
   - Configurar las 3 fechas de sesiones
   - Establecer cupo máximo
   - Activar curso

2. **Inscripciones** (InscripcionCSV.py - Público)
   - Participantes llenan formulario
   - Sistema valida cupos disponibles
   - Se registra inscripción

3. **Registro de asistencia** (AsistenciaCurso.py)
   - Día de la sesión: participantes marcan asistencia con su RUT
   - Alternativa: instructor marca asistencia manualmente

4. **Reportes** (AsistenciaCurso.py - Admin)
   - Ver estadísticas en tiempo real
   - Descargar reportes Excel
   - Verificar estado de aprobación

## 🔒 Seguridad

- Validación de RUT usando librería rut-chile
- Validación de cupos disponibles
- Prevención de registros duplicados
- Panel administrativo protegido con contraseña
- Validación de inscripción antes de registrar asistencia

## 📊 Reportes Generados

### Reporte de Inscripciones (Excel)
- Datos completos de todos los inscritos
- Filtrable por curso

### Reporte de Asistencia (Excel)
- RUT, Nombre completo
- Estado por sesión (PRESENTE/AUSENTE)
- Porcentaje de asistencia
- Estado final (APROBADO/REPROBADO)
- Formato con colores para fácil lectura

## 🛠️ Mantenimiento

### Editar asistencias
- Usar panel administrativo > Editar/Corregir Asistencias
- Seleccionar registro a eliminar
- Confirmar eliminación

### Corrección de errores
- Si un participante marcó la sesión incorrecta: eliminar registro y volver a marcar
- Si falta asistencia: usar marcar asistencia manual

## ⚠️ Consideraciones Importantes

1. **Fechas de sesiones:** Deben configurarse al crear el curso
2. **Cursos activos:** Solo puede haber un curso activo a la vez
3. **Aprobación:** Se calcula automáticamente basado en asistencia
4. **Respaldos:** Recomendado descargar reportes periódicamente
5. **Google Sheets:** Mantener estructura de columnas intacta

## 📞 Soporte

Para problemas o preguntas sobre el sistema, contactar al administrador.
