// ============================================
// CÓDIGO PARA ACTUALIZAR EN GOOGLE APPS SCRIPT
// ============================================
// Este código debe agregarse a tu Apps Script existente

// Nombre de la hoja de asistencias
const SHEET_NAME_ASISTENCIAS = 'Asistencias';

// ============================================
// FUNCIÓN PRINCIPAL - ACTUALIZAR doGet()
// ============================================
// Agregar estos casos al switch de la función doGet() existente:

/*
function doGet(e) {
  const action = e.parameter.action;
  const key = e.parameter.key;

  // Verificar API key
  if (key !== API_KEY) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: 'API key inválida'
    })).setMimeType(ContentService.MimeType.JSON);
  }

  switch(action) {
    // ... casos existentes ...

    // NUEVOS CASOS PARA ASISTENCIAS:
    case 'getAsistencias':
      return getAsistencias();
    case 'getCursoActivo':
      return getCursoActivo();
    default:
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Acción no válida'
      })).setMimeType(ContentService.MimeType.JSON);
  }
}
*/

// ============================================
// FUNCIÓN PRINCIPAL - ACTUALIZAR doPost()
// ============================================
// Agregar estos casos al switch de la función doPost() existente:

/*
function doPost(e) {
  const action = e.parameter.action;
  const key = e.parameter.key;

  // Verificar API key
  if (key !== API_KEY) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: 'API key inválida'
    })).setMimeType(ContentService.MimeType.JSON);
  }

  const data = JSON.parse(e.postData.contents);

  switch(action) {
    // ... casos existentes ...

    // NUEVOS CASOS PARA ASISTENCIAS:
    case 'addAsistencia':
      return addAsistencia(data);
    case 'deleteAsistencia':
      return deleteAsistencia(data);
    case 'addCurso':
      return addCurso(data);
    default:
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Acción no válida'
      })).setMimeType(ContentService.MimeType.JSON);
  }
}
*/

// ============================================
// FUNCIONES PARA ASISTENCIAS
// ============================================

// Función para obtener todas las asistencias
function getAsistencias() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME_ASISTENCIAS);

    // Si la hoja no existe, crearla
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME_ASISTENCIAS);
      // Crear encabezados
      sheet.getRange('A1:G1').setValues([[
        'id', 'curso_id', 'rut', 'sesion', 'fecha_registro', 'estado', 'metodo'
      ]]);
      sheet.getRange('A1:G1').setFontWeight('bold');
      sheet.getRange('A1:G1').setBackground('#4472C4');
      sheet.getRange('A1:G1').setFontColor('white');

      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        asistencias: []
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const data = sheet.getDataRange().getValues();

    // Si solo hay encabezados
    if (data.length <= 1) {
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        asistencias: []
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const headers = data[0];
    const asistencias = [];

    for (let i = 1; i < data.length; i++) {
      const row = {};
      for (let j = 0; j < headers.length; j++) {
        row[headers[j]] = data[i][j];
      }
      asistencias.push(row);
    }

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      asistencias: asistencias
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Función para agregar una nueva asistencia
function addAsistencia(data) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME_ASISTENCIAS);

    // Si la hoja no existe, crearla
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME_ASISTENCIAS);
      sheet.getRange('A1:G1').setValues([[
        'id', 'curso_id', 'rut', 'sesion', 'fecha_registro', 'estado', 'metodo'
      ]]);
      sheet.getRange('A1:G1').setFontWeight('bold');
      sheet.getRange('A1:G1').setBackground('#4472C4');
      sheet.getRange('A1:G1').setFontColor('white');
    }

    // Verificar si ya existe un registro para este RUT, curso y sesión
    const existingData = sheet.getDataRange().getValues();
    for (let i = 1; i < existingData.length; i++) {
      if (existingData[i][1] === data.curso_id &&
          existingData[i][2] === data.rut &&
          existingData[i][3] === data.sesion) {
        return ContentService.createTextOutput(JSON.stringify({
          success: false,
          error: 'Ya existe un registro de asistencia para este participante en esta sesión'
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    // Generar ID único
    const lastRow = sheet.getLastRow();
    const newId = lastRow; // Simple incremental ID

    // Agregar nueva fila
    sheet.appendRow([
      newId,
      data.curso_id,
      data.rut,
      data.sesion,
      data.fecha_registro,
      data.estado,
      data.metodo
    ]);

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      message: 'Asistencia registrada correctamente'
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Función para eliminar una asistencia
function deleteAsistencia(data) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME_ASISTENCIAS);

    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Hoja de asistencias no encontrada'
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const values = sheet.getDataRange().getValues();

    // Buscar y eliminar la fila con el ID correspondiente
    for (let i = 1; i < values.length; i++) {
      if (values[i][0] == data.asistencia_id) {
        sheet.deleteRow(i + 1);

        return ContentService.createTextOutput(JSON.stringify({
          success: true,
          message: 'Asistencia eliminada correctamente'
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: 'Registro no encontrado'
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// ============================================
// ACTUALIZAR FUNCIÓN addCurso EXISTENTE
// ============================================
// Modificar tu función addCurso para incluir las fechas de sesiones:

/*
function addCurso(data) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME_CONFIG);

    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Hoja de configuración no encontrada'
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // Verificar si el curso ya existe
    const existingData = sheet.getDataRange().getValues();
    for (let i = 1; i < existingData.length; i++) {
      if (existingData[i][0] === data.curso_id) {
        return ContentService.createTextOutput(JSON.stringify({
          success: false,
          error: 'Ya existe un curso con este ID'
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    // Agregar nueva fila con las fechas de sesiones
    sheet.appendRow([
      data.curso_id,
      data.fecha_inicio,
      data.fecha_fin,
      data.estado || 'ACTIVO',
      data.cupo_maximo,
      data.fecha_sesion_1 || '',
      data.fecha_sesion_2 || '',
      data.fecha_sesion_3 || ''
    ]);

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      message: 'Curso creado correctamente'
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
*/

// ============================================
// FUNCIÓN getCursoActivo
// ============================================
// Esta función puede que ya la tengas, si no, agrégala:

/*
function getCursoActivo() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME_CONFIG);

    if (!sheet) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Hoja de configuración no encontrada'
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const data = sheet.getDataRange().getValues();
    const headers = data[0];

    // Buscar el curso con estado ACTIVO
    for (let i = 1; i < data.length; i++) {
      const estado = data[i][3]; // Asumiendo que 'estado' está en columna D (índice 3)

      if (estado === 'ACTIVO') {
        const curso = {};
        for (let j = 0; j < headers.length; j++) {
          curso[headers[j]] = data[i][j];
        }

        return ContentService.createTextOutput(JSON.stringify({
          success: true,
          curso: curso
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      curso: null
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
*/

// ============================================
// ACTUALIZAR ESTRUCTURA DE HOJA "Config"
// ============================================
/*
IMPORTANTE: Agregar estas columnas a la hoja "Config" en Google Sheets:

Estructura actual (probablemente):
A: curso_id
B: fecha_inicio
C: fecha_fin
D: estado
E: cupo_maximo

Estructura nueva (agregar):
F: fecha_sesion_1
G: fecha_sesion_2
H: fecha_sesion_3

Puedes agregar estas columnas manualmente o crear un script de migración.
*/

// ============================================
// NOTAS IMPORTANTES
// ============================================
/*
1. Asegúrate de que la hoja "Config" tenga las nuevas columnas antes de crear cursos
2. La hoja "Asistencias" se creará automáticamente al primer registro
3. Los IDs de asistencias son auto-incrementales
4. No olvides actualizar tu API_KEY en el script
5. Después de actualizar el código, debes publicar nuevamente como aplicación web
6. Asegúrate de que el acceso sea "Cualquiera" para que funcione desde Streamlit
*/
