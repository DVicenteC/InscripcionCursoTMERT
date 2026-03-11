"""
Test exhaustivo local del sistema de asistencia.
Simula todos los flujos críticos sin tocar Google Sheets.
"""

import sys
import os
import pandas as pd
from datetime import datetime, date
import duckdb
import traceback

# ─────────────────────────────────────────────
PASS = "✅ PASS"
FAIL = "❌ FAIL"
resultados = []

def check(nombre, condicion, detalle=""):
    estado = PASS if condicion else FAIL
    resultados.append((estado, nombre, detalle))
    print(f"  {estado}  {nombre}" + (f" → {detalle}" if detalle else ""))

def seccion(titulo):
    print(f"\n{'═'*60}")
    print(f"  {titulo}")
    print(f"{'═'*60}")

# ─────────────────────────────────────────────
seccion("1. PARSEO DE FECHAS (ISO timezone desde Apps Script)")

casos_fecha = [
    ("2026-03-04T03:00:00.000Z", "Formato Apps Script con Z"),
    ("2026-03-04T00:00:00.000Z", "Medianoche UTC"),
    ("2026-03-04",               "Solo fecha ISO"),
    ("4/3/2026",                 "Formato chileno DD/MM/YYYY"),
    ("3/4/2026",                 "Formato US MM/DD/YYYY"),
    ("Wed Mar 04 2026 00:00:00 GMT-0300", "Date.toString() Apps Script"),
]

HOY = pd.Timestamp.now().normalize()
print(f"  Hoy (local): {HOY.date()}")

for valor, descripcion in casos_fecha:
    try:
        parsed = (pd.to_datetime(valor, utc=True, errors='coerce')
                  .tz_convert(None)
                  .normalize())
        es_hoy = (parsed == HOY)
        check(descripcion, not pd.isna(parsed), f"→ {parsed.date() if not pd.isna(parsed) else 'NaT'} {'(HOY ✓)' if es_hoy else ''}")
    except Exception as e:
        check(descripcion, False, str(e))

# ─────────────────────────────────────────────
seccion("2. LÓGICA get_cursos_con_sesion_hoy")

def get_cursos_con_sesion_hoy(df_cursos):
    if df_cursos.empty:
        return pd.DataFrame()
    hoy = pd.Timestamp.now().normalize()
    cursos_hoy = []
    for _, curso in df_cursos.iterrows():
        for sesion_num in [1, 2, 3]:
            fecha_col = f'fecha_sesion_{sesion_num}'
            if fecha_col in curso and pd.notna(curso[fecha_col]):
                fecha_sesion = pd.to_datetime(curso[fecha_col]).normalize()
                if fecha_sesion == hoy:
                    curso_dict = curso.to_dict()
                    curso_dict['sesion_hoy'] = sesion_num
                    curso_dict['fecha_sesion_hoy'] = curso[fecha_col]
                    cursos_hoy.append(curso_dict)
                    break
    return pd.DataFrame(cursos_hoy) if cursos_hoy else pd.DataFrame()

# Simular respuesta de API con fecha de HOY en formato Apps Script
hoy_iso = datetime.utcnow().strftime("%Y-%m-%dT03:00:00.000Z")
manana_iso = datetime.utcnow().strftime("%Y-%m-%dT03:00:00.000Z")  # simplificado

df_test = pd.DataFrame([{
    'curso_id': 'mar26-RM',
    'region': 'Región Metropolitana de Santiago',
    'fecha_inicio': hoy_iso,
    'fecha_fin': hoy_iso,
    'estado': 'ACTIVO',
    'cupo_maximo': 100,
    'fecha_sesion_1': hoy_iso,
    'fecha_sesion_2': '2026-03-10T03:00:00.000Z',
    'fecha_sesion_3': '2026-03-12T03:00:00.000Z',
}])

# Aplicar el mismo parseo que get_config_data
date_cols = ['fecha_inicio', 'fecha_fin', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']
for col in date_cols:
    df_test[col] = (pd.to_datetime(df_test[col], utc=True, errors='coerce')
                    .dt.tz_convert(None)
                    .dt.normalize())

df_hoy = get_cursos_con_sesion_hoy(df_test)
check("Curso mar26-RM aparece hoy", not df_hoy.empty)
check("Sesión detectada es la 1", not df_hoy.empty and df_hoy.iloc[0]['sesion_hoy'] == 1)

# Curso sin sesión hoy
df_sin_hoy = pd.DataFrame([{
    'curso_id': 'otro-curso',
    'fecha_sesion_1': '2026-04-01T03:00:00.000Z',
    'fecha_sesion_2': '2026-04-08T03:00:00.000Z',
    'fecha_sesion_3': '2026-04-15T03:00:00.000Z',
}])
for col in ['fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']:
    df_sin_hoy[col] = (pd.to_datetime(df_sin_hoy[col], utc=True, errors='coerce')
                       .dt.tz_convert(None).dt.normalize())
df_sin = get_cursos_con_sesion_hoy(df_sin_hoy)
check("Curso sin sesión hoy no aparece", df_sin.empty)

# ─────────────────────────────────────────────
seccion("3. BUFFER DUCKDB — Inicialización y operaciones")

TEST_DB = "test_buffer_prueba.duckdb"
try:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    conn = duckdb.connect(TEST_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asistencias_buffer (
            id VARCHAR PRIMARY KEY,
            curso_id VARCHAR NOT NULL,
            rut VARCHAR NOT NULL,
            sesion INTEGER NOT NULL,
            fecha_registro TIMESTAMP NOT NULL,
            estado VARCHAR DEFAULT 'presente',
            metodo VARCHAR DEFAULT 'streamlit',
            sincronizado BOOLEAN DEFAULT false,
            intentos_sync INTEGER DEFAULT 0,
            ultimo_error VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(curso_id, rut, sesion)
        )
    """)
    check("Tabla creada correctamente", True)

    # Insertar registro
    conn.execute("""
        INSERT INTO asistencias_buffer
        (id, curso_id, rut, sesion, fecha_registro, estado, metodo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ["ASIST-1", "mar26-RM", "18340815-1", 1, datetime.now(), "presente", "streamlit_buffer"])
    check("Inserción de asistencia", True)

    # Verificar duplicado (UNIQUE constraint)
    try:
        conn.execute("""
            INSERT INTO asistencias_buffer
            (id, curso_id, rut, sesion, fecha_registro, estado, metodo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (curso_id, rut, sesion) DO UPDATE
            SET estado = EXCLUDED.estado
        """, ["ASIST-2", "mar26-RM", "18340815-1", 1, datetime.now(), "presente", "test"])
        check("ON CONFLICT DO UPDATE no lanza error", True)
    except Exception as e:
        check("ON CONFLICT manejo", False, str(e))

    # verificar_asistencia
    result = conn.execute("""
        SELECT COUNT(*) FROM asistencias_buffer
        WHERE curso_id = ? AND rut = ? AND sesion = ?
    """, ["mar26-RM", "18340815-1", 1]).fetchone()
    check("verificar_asistencia detecta existente", result[0] > 0)

    result2 = conn.execute("""
        SELECT COUNT(*) FROM asistencias_buffer
        WHERE curso_id = ? AND rut = ? AND sesion = ?
    """, ["mar26-RM", "99999999-9", 1]).fetchone()
    check("verificar_asistencia detecta no existente", result2[0] == 0)

    # Insertar segundo participante
    conn.execute("""
        INSERT INTO asistencias_buffer
        (id, curso_id, rut, sesion, fecha_registro, estado, metodo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ["ASIST-3", "mar26-RM", "12345678-9", 1, datetime.now(), "presente", "streamlit_buffer"])

    total = conn.execute("SELECT COUNT(*) FROM asistencias_buffer").fetchone()[0]
    check("Dos participantes en buffer", total == 2)

    # Estadísticas
    pendientes = conn.execute("SELECT COUNT(*) FROM asistencias_buffer WHERE sincronizado = false AND intentos_sync < 5").fetchone()[0]
    check(f"Pendientes de sync: {pendientes}", pendientes == 2)

    # Marcar uno como sincronizado
    conn.execute("UPDATE asistencias_buffer SET sincronizado = true WHERE rut = '18340815-1'")
    sincronizadas = conn.execute("SELECT COUNT(*) FROM asistencias_buffer WHERE sincronizado = true").fetchone()[0]
    check("Marcar como sincronizado", sincronizadas == 1)

    conn.close()
    check("Conexión cerrada sin errores", True)

except Exception as e:
    check("Buffer DuckDB general", False, traceback.format_exc())

# ─────────────────────────────────────────────
seccion("4. LIMPIAR SINCRONIZADOS — Sintaxis DuckDB")

try:
    conn = duckdb.connect(TEST_DB)

    # Test limpiar con dias=0 usando pre-count
    count = conn.execute("SELECT COUNT(*) FROM asistencias_buffer WHERE sincronizado = true").fetchone()[0]
    conn.execute("DELETE FROM asistencias_buffer WHERE sincronizado = true")
    check("limpiar_sincronizados(dias=0) — sintaxis OK", True)
    check(f"pre-count devuelve número real ({count})", isinstance(count, int) and count >= 0)

    # Test limpiar con dias > 0
    result2 = conn.execute("""
        DELETE FROM asistencias_buffer
        WHERE sincronizado = true
          AND created_at < CAST(CURRENT_TIMESTAMP AS TIMESTAMP) - (? * INTERVAL '1 day')
    """, [7])
    check("limpiar_sincronizados(dias=7) — sintaxis OK", True)

    conn.close()
except Exception as e:
    check("limpiar_sincronizados sintaxis", False, str(e))

# ─────────────────────────────────────────────
seccion("5. HIDRATACIÓN — Simulación de respuesta Apps Script")

datos_sheets_mock = [
    {"id": 1, "curso_id": "mar26-RM", "rut": "18340815-1", "sesion": 1.0,
     "fecha_registro": "2026-03-04T12:00:00.000Z", "estado": "presente", "metodo": "streamlit_buffer"},
    {"id": 2, "curso_id": "mar26-RM", "rut": "12345678-9", "sesion": 1.0,
     "fecha_registro": "2026-03-04T12:05:00.000Z", "estado": "presente", "metodo": "streamlit_buffer"},
    {"id": 3, "curso_id": "mar26-RM", "rut": "11111111-1", "sesion": 1.0,
     "fecha_registro": "fecha_invalida",  # caso borde
     "estado": "presente", "metodo": "streamlit_buffer"},
]

try:
    conn = duckdb.connect(TEST_DB)
    # Limpiar para el test
    conn.execute("DELETE FROM asistencias_buffer")

    cargados = 0
    for asist in datos_sheets_mock:
        try:
            asist_id = f"SHEETS-{asist.get('curso_id','')}-{asist.get('rut','')}-{asist.get('sesion','')}"

            # Parseo robusto de fecha
            try:
                fecha_pd = pd.to_datetime(str(asist['fecha_registro']), utc=True, errors='coerce')
                fecha = fecha_pd.to_pydatetime().replace(tzinfo=None) if pd.notna(fecha_pd) else datetime.now()
            except Exception:
                fecha = datetime.now()

            conn.execute("""
                INSERT INTO asistencias_buffer
                (id, curso_id, rut, sesion, fecha_registro, estado, metodo, sincronizado)
                VALUES (?, ?, ?, ?, ?, ?, ?, true)
                ON CONFLICT (curso_id, rut, sesion) DO NOTHING
            """, [
                asist_id,
                str(asist.get('curso_id', '')),
                str(asist.get('rut', '')),
                int(asist.get('sesion', 0)),   # float 1.0 → int 1
                fecha,
                str(asist.get('estado', 'presente')),
                'sheets_hydration'
            ])
            cargados += 1
        except Exception as e:
            print(f"    ⚠️  Error en fila {asist.get('rut')}: {e}")
            continue

    check("Hidratación carga 3 registros (incluyendo fecha inválida)", cargados == 3)

    total = conn.execute("SELECT COUNT(*) FROM asistencias_buffer").fetchone()[0]
    check("3 registros en buffer post-hidratación", total == 3)

    # Verificar que sesion float (1.0) se guardó como int 1
    sesion_val = conn.execute("SELECT sesion FROM asistencias_buffer WHERE rut = '18340815-1'").fetchone()
    check("sesion guardada como int (1.0 → 1)", sesion_val and sesion_val[0] == 1)

    # Simular ON CONFLICT DO NOTHING (no duplica)
    conn.execute("""
        INSERT INTO asistencias_buffer
        (id, curso_id, rut, sesion, fecha_registro, estado, metodo, sincronizado)
        VALUES (?, ?, ?, ?, ?, ?, ?, true)
        ON CONFLICT (curso_id, rut, sesion) DO NOTHING
    """, ["SHEETS-mar26-RM-18340815-1-1.0", "mar26-RM", "18340815-1", 1,
          datetime.now(), "presente", "sheets_hydration"])
    total2 = conn.execute("SELECT COUNT(*) FROM asistencias_buffer").fetchone()[0]
    check("ON CONFLICT DO NOTHING — no crea duplicados", total2 == 3)

    conn.close()
except Exception as e:
    check("Hidratación general", False, traceback.format_exc())

# ─────────────────────────────────────────────
seccion("6. VALIDACIÓN DE NOMBRE — Campos de registros")

registros_mock = [
    {"rut": "18340815-1", "curso_id": "mar26-RM", "nombres": "JUAN CARLOS", "apellido_paterno": "PÉREZ"},
    {"rut": "12345678-9", "curso_id": "mar26-RM", "nombres": "MARÍA", "apellido_paterno": "SOTO"},
    {"rut": "11111111-1", "curso_id": "mar26-RM"},  # sin nombre (caso borde)
]

for reg in registros_mock:
    datos = reg
    rut_input = reg["rut"]
    nombre_completo = f"{datos.get('nombres', '')} {datos.get('apellido_paterno', '')}".strip() or rut_input
    check(f"Nombre para {rut_input}", bool(nombre_completo), f"→ '{nombre_completo}'")

# ─────────────────────────────────────────────
seccion("7. NORMALIZACIÓN RUT — k minúscula vs K mayúscula")

casos_rut = [
    ("18340815-k", "18340815-K", True,  "k minúscula → encuentra K mayúscula"),
    ("18340815-K", "18340815-K", True,  "K mayúscula → encuentra K mayúscula"),
    ("18340815-k", "18340815-k", True,  "k minúscula → encuentra k minúscula"),
    (" 12345678-9 ", "12345678-9", True, "Espacios extra → normaliza y encuentra"),
    ("99999999-9", "12345678-9", False, "RUT diferente → no encuentra"),
]

for rut_ingresado, rut_guardado, deberia_encontrar, descripcion in casos_rut:
    rut_norm = str(rut_ingresado).strip().upper()
    rut_stored_norm = str(rut_guardado).upper().strip()
    resultado = (rut_norm == rut_stored_norm)
    check(descripcion, resultado == deberia_encontrar,
          f"'{rut_ingresado}'.upper().strip()='{rut_norm}' vs '{rut_guardado}'")

seccion("8. VALIDACIÓN PARTICIPANTE INSCRITO")

df_registros = pd.DataFrame(registros_mock)

def validar_participante_inscrito(rut, curso_id, df_registros):
    """Versión que replica el fix de case-insensitive."""
    if df_registros.empty:
        return False, None
    rut_norm = str(rut).upper().strip()
    participante = df_registros[
        (df_registros['rut'].astype(str).str.upper().str.strip() == rut_norm) &
        (df_registros['curso_id'] == curso_id)
    ]
    if not participante.empty:
        return True, participante.iloc[0].to_dict()
    return False, None

ok, datos = validar_participante_inscrito("18340815-1", "mar26-RM", df_registros)
check("Participante inscrito encontrado", ok)
check("Datos contienen nombres", datos and 'nombres' in datos)

ok2, _ = validar_participante_inscrito("99999999-9", "mar26-RM", df_registros)
check("Participante NO inscrito retorna False", not ok2)

ok3, _ = validar_participante_inscrito("18340815-1", "otro-curso", df_registros)
check("Participante en otro curso retorna False", not ok3)

# ─────────────────────────────────────────────
seccion("9. FLUJO COMPLETO — Registro de asistencia end-to-end")

try:
    conn = duckdb.connect(TEST_DB)

    def verificar(curso_id, rut, sesion):
        r = conn.execute("SELECT COUNT(*) FROM asistencias_buffer WHERE curso_id=? AND rut=? AND sesion=?",
                         [curso_id, rut, sesion]).fetchone()
        return r[0] > 0

    def marcar(curso_id, rut, sesion):
        if verificar(curso_id, rut, sesion):
            return {'success': False, 'message': 'Ya existe un registro de asistencia para este participante en esta sesión'}
        import time
        asist_id = f"ASIST-{curso_id}-{rut}-{sesion}-{int(time.time()*1000)}"
        conn.execute("""
            INSERT INTO asistencias_buffer
            (id, curso_id, rut, sesion, fecha_registro, estado, metodo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (curso_id, rut, sesion) DO UPDATE
            SET fecha_registro = EXCLUDED.fecha_registro
        """, [asist_id, curso_id, rut, sesion, datetime.now(), "presente", "streamlit_buffer"])
        return {'success': True, 'message': 'Asistencia registrada en buffer local'}

    # Limpiar buffer para este test
    conn.execute("DELETE FROM asistencias_buffer")

    # Primer registro — debe funcionar
    r1 = marcar("mar26-RM", "18340815-1", 1)
    check("Primer registro exitoso", r1['success'])

    # Segundo intento del mismo participante — debe rechazar
    r2 = marcar("mar26-RM", "18340815-1", 1)
    check("Duplicado rechazado correctamente", not r2['success'])
    check("Mensaje de duplicado correcto", "Ya existe" in r2['message'])

    # Otro participante misma sesión — debe funcionar
    r3 = marcar("mar26-RM", "12345678-9", 1)
    check("Otro participante registrado OK", r3['success'])

    # Mismo participante otra sesión — debe funcionar
    r4 = marcar("mar26-RM", "18340815-1", 2)
    check("Mismo participante sesión 2 registrado OK", r4['success'])

    total = conn.execute("SELECT COUNT(*) FROM asistencias_buffer").fetchone()[0]
    check(f"Total registros en buffer = 3", total == 3)

    conn.close()
except Exception as e:
    check("Flujo end-to-end", False, traceback.format_exc())

# ─────────────────────────────────────────────
# Limpieza
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
if os.path.exists(TEST_DB + ".wal"):
    os.remove(TEST_DB + ".wal")

# ─────────────────────────────────────────────
seccion("RESUMEN FINAL")

total_tests = len(resultados)
pasados = sum(1 for r in resultados if r[0] == PASS)
fallados = total_tests - pasados

print(f"\n  Total: {total_tests} | {PASS}: {pasados} | {FAIL}: {fallados}\n")

if fallados > 0:
    print("  Tests fallidos:")
    for estado, nombre, detalle in resultados:
        if estado == FAIL:
            print(f"    ❌ {nombre}: {detalle}")

sys.exit(0 if fallados == 0 else 1)
