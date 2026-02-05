/**
 * Script de Google Apps Script para gestionar inscripciones a cursos TMERT
 * Y REGISTRO DE ASISTENCIAS
 * Este script se debe copiar en el Editor de secuencias de comandos
 * de tu hoja de cálculo de Google Sheets
 */

// ID de la hoja de cálculo (no necesitas modificarlo si ejecutas el script desde la hoja)
const SPREADSHEET_ID = '1U64j95_UPpKH1gZvjB11YhFypcpKJQX8P320KhIK6js';

// Nombres de las hojas
const REGISTROS_SHEET_NAME = 'Hoja 1';
const CONFIG_SHEET_NAME = 'Config';
const SHEET_NAME_ASISTENCIAS = 'Asistencias';
const API_KEY = 'tu_clave_secretaISTColon3066'; // Cámbiala por una clave segura

// Función para configurar el servicio web
// Función para recibir solicitudes GET
function doGet(e) {
  try {
    // Registrar información de depuración
    console.log("doGet llamado con parámetros: " + JSON.stringify(e.parameter));

    const action = e.parameter.action;
    const key = e.parameter.key;

    // Prueba simple para verificar que el Apps Script funciona
    if (action === "test") {
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        message: "Conexión exitosa",
        timestamp: new Date().toString()
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // Verificar clave API
    if (key !== API_KEY) {
      console.log("Clave API inválida: " + key);
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Clave API inválida'
      })).setMimeType(ContentService.MimeType.JSON);
    }

    let result;

    switch (action) {
      case 'getConfig':
        console.log("Ejecutando getConfigData()");
        result = getConfigData();
        break;
      case 'getRegistros':
        console.log("Ejecutando getRegistrosData()");
        result = getRegistrosData();
        break;
      case 'getCursoActivo':
        console.log("Ejecutando getCursoActivo()");
        result = getCursoActivo();
        break;
      case 'getAsistencias':
        console.log("Ejecutando getAsistencias()");
        result = getAsistencias();
        break;
      default:
        console.log("Acción no reconocida: " + action);
        result = { success: false, error: 'Acción no válida: ' + action };
    }

    console.log("Resultado: " + JSON.stringify(result));
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    console.error("Error en doGet: " + error.toString());
    console.error("Stack: " + error.stack);
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString(),
      stack: error.stack
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Función para recibir datos (POST)
function doPost(e) {
  try {
    console.log("doPost llamado con parámetros: " + JSON.stringify(e.parameter));
    console.log("Tipo de e: " + typeof e);
    console.log("Propiedades de e: " + Object.keys(e).join(", "));
    console.log("postData existe: " + (e.postData ? "Sí" : "No"));

    const action = e.parameter.action;
    const key = e.parameter.key;

    // Verificar clave API
    if (key !== API_KEY) {
      console.log("Clave API inválida: " + key);
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: 'Clave API inválida'
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // Prueba simple para verificar que el Apps Script funciona
    if (action === "test") {
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        message: "Conexión POST exitosa",
        timestamp: new Date().toString(),
        hasPostData: e.postData ? true : false
      })).setMimeType(ContentService.MimeType.JSON);
    }

    let result;
    let data = {};

    // Comprobar si hay datos POST y procesarlos con seguridad
    if (e.postData && e.postData.contents) {
      console.log("Contenido de postData: " + e.postData.contents);
      try {
        data = JSON.parse(e.postData.contents);
        console.log("Datos parseados: " + JSON.stringify(data));
      } catch (parseError) {
        console.error("Error al parsear JSON: " + parseError.toString());
        return ContentService.createTextOutput(JSON.stringify({
          success: false,
          error: 'Error al parsear JSON: ' + parseError.toString(),
          rawContent: e.postData.contents
        })).setMimeType(ContentService.MimeType.JSON);
      }
    } else {
      console.log("No hay datos POST o contenido");
      // Si no hay datos POST, pero se necesitan para la operación, devolver error
      if (action === "addRegistro" || action === "addCurso" || action === "updateConfig" || action === "addAsistencia") {
        return ContentService.createTextOutput(JSON.stringify({
          success: false,
          error: 'No se recibieron datos POST'
        })).setMimeType(ContentService.MimeType.JSON);
      }
    }

    switch (action) {
      case 'addRegistro':
        console.log("Ejecutando addRegistro con datos: " + JSON.stringify(data));
        result = addRegistro(data);
        break;
      case 'updateConfig':
        console.log("Ejecutando updateConfig con datos: " + JSON.stringify(data));
        result = updateConfig(data);
        break;
      case 'addCurso':
        console.log("Ejecutando addCurso con datos: " + JSON.stringify(data));
        result = addCurso(data);
        break;
      case 'activarCurso':
        console.log("Ejecutando activarCurso con curso_id: " + (data.curso_id || "undefined"));
        result = activarCurso(data.curso_id);
        break;
      case 'addAsistencia':
        console.log("Ejecutando addAsistencia con datos: " + JSON.stringify(data));
        result = addAsistencia(data);
        break;
      case 'deleteAsistencia':
        console.log("Ejecutando deleteAsistencia con datos: " + JSON.stringify(data));
        result = deleteAsistencia(data);
        break;
      default:
        console.log("Acción POST no reconocida: " + action);
        result = { success: false, error: 'Acción POST no válida: ' + action };
    }

    console.log("Resultado: " + JSON.stringify(result));
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    console.error("Error en doPost: " + error.toString());
    console.error("Stack: " + error.stack);
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: error.toString(),
      stack: error.stack
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Obtener datos de configuración
function getConfigData() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    // Verificar si existe la hoja de configuración, si no, crearla
    let configSheet;
    try {
      configSheet = ss.getSheetByName(CONFIG_SHEET_NAME);
      if (!configSheet) {
        configSheet = ss.insertSheet(CONFIG_SHEET_NAME);
        configSheet.appendRow(['curso_id', 'fecha_inicio', 'fecha_fin', 'estado', 'cupo_maximo', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']);
      }
    } catch (error) {
      configSheet = ss.insertSheet(CONFIG_SHEET_NAME);
      configSheet.appendRow(['curso_id', 'fecha_inicio', 'fecha_fin', 'estado', 'cupo_maximo', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']);
    }

    const data = configSheet.getDataRange().getValues();
    const headers = data[0];

    // Convertir datos a JSON
    const cursos = [];
    for (let i = 1; i < data.length; i++) {
      const curso = {};
      for (let j = 0; j < headers.length; j++) {
        curso[headers[j]] = data[i][j];
      }
      cursos.push(curso);
    }

    return {
      success: true,
      cursos: cursos
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Obtener datos de registros
function getRegistrosData() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = ss.getSheetByName(REGISTROS_SHEET_NAME);

    // Verificar si la hoja tiene encabezados, si no, agregarlos
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    if (headers.length === 0 || headers[0] === '') {
      sheet.appendRow([
        'fecha_registro', 'curso_id', 'rut', 'nombres', 'apellido_paterno',
        'apellido_materno', 'nacionalidad', 'email', 'gmail', 'sexo', 'rol', 'rut_empresa',
        'razon_social', 'region', 'comuna', 'direccion'
      ]);
    }

    const data = sheet.getDataRange().getValues();
    const registrosHeaders = data[0];

    // Convertir datos a JSON
    const registros = [];
    for (let i = 1; i < data.length; i++) {
      const registro = {};
      for (let j = 0; j < registrosHeaders.length; j++) {
        registro[registrosHeaders[j]] = data[i][j];
      }
      registros.push(registro);
    }

    return {
      success: true,
      registros: registros
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Agregar un nuevo registro
function addRegistro(data) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = ss.getSheetByName(REGISTROS_SHEET_NAME);

    // Verificar si la hoja tiene encabezados, si no, agregarlos
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        'fecha_registro', 'curso_id', 'rut', 'nombres', 'apellido_paterno',
        'apellido_materno', 'nacionalidad', 'email', 'gmail', 'sexo', 'rol', 'rut_empresa',
        'razon_social', 'region', 'comuna', 'direccion'
      ]);
    }

    // Obtener todos los datos y encabezados
    const allData = sheet.getDataRange().getValues();
    const headers = allData[0];

    // Crear mapeo de nombres de columna a índices
    const colIndices = {};
    headers.forEach((header, index) => {
      colIndices[header] = index;
    });

    // Verificar si el registro ya existe (por RUT y curso_id)
    for (let i = 1; i < allData.length; i++) {
      if (allData[i][colIndices['rut']] === data.rut &&
          allData[i][colIndices['curso_id']] === data.curso_id &&
          allData[i][colIndices['rut_empresa']] === data.rut_empresa) {
        return {
          success: false,
          error: 'Ya existe un registro con este RUT para este curso'
        };
      }
    }

    // Agregar el nuevo registro
    sheet.appendRow([
      data.fecha_registro,
      data.curso_id,
      data.rut,
      data.nombres,
      data.apellido_paterno,
      data.apellido_materno,
      data.nacionalidad,
      data.email,
      data.gmail,
      data.sexo,
      data.rol,
      data.rut_empresa,
      data.razon_social,
      data.region,
      data.comuna,
      data.direccion
    ]);

    return {
      success: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Agregar un nuevo curso (ACTUALIZADO CON REGIÓN Y FECHAS DE SESIONES)
function addCurso(data) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    // Verificar si existe la hoja de configuración, si no, crearla
    let configSheet;
    try {
      configSheet = ss.getSheetByName(CONFIG_SHEET_NAME);
      if (!configSheet) {
        configSheet = ss.insertSheet(CONFIG_SHEET_NAME);
        // IMPORTANTE: Estructura con región y columnas de sesiones
        configSheet.appendRow(['curso_id', 'region', 'fecha_inicio', 'fecha_fin', 'estado', 'cupo_maximo', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']);
      }
    } catch (error) {
      configSheet = ss.insertSheet(CONFIG_SHEET_NAME);
      configSheet.appendRow(['curso_id', 'region', 'fecha_inicio', 'fecha_fin', 'estado', 'cupo_maximo', 'fecha_sesion_1', 'fecha_sesion_2', 'fecha_sesion_3']);
    }

    // Establecer todos los cursos como inactivos
    const lastRow = configSheet.getLastRow();
    if (lastRow > 1) {
      const range = configSheet.getRange(2, 5, lastRow - 1, 1); // Columna 5 es 'estado' (ahora que region está en col 2)
      range.setValue('INACTIVO');
    }

    // Agregar el nuevo curso con región y fechas de sesiones
    configSheet.appendRow([
      data.curso_id,
      data.region || '',
      data.fecha_inicio,
      data.fecha_fin,
      'ACTIVO',
      data.cupo_maximo,
      data.fecha_sesion_1 || '',
      data.fecha_sesion_2 || '',
      data.fecha_sesion_3 || ''
    ]);

    return {
      success: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Activar un curso específico
function activarCurso(curso_id) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const configSheet = ss.getSheetByName(CONFIG_SHEET_NAME);

    if (!configSheet) {
      return {
        success: false,
        error: 'No existe la hoja de configuración'
      };
    }

    const data = configSheet.getDataRange().getValues();
    const headers = data[0];

    // Encontrar el índice de la columna 'estado' dinámicamente
    const estadoColIndex = headers.indexOf('estado');
    if (estadoColIndex === -1) {
      return {
        success: false,
        error: 'Columna estado no encontrada'
      };
    }

    // Marcar todos como inactivos primero
    for (let i = 1; i < data.length; i++) {
      configSheet.getRange(i + 1, estadoColIndex + 1).setValue('INACTIVO');
    }

    // Buscar y activar el curso seleccionado
    let cursoEncontrado = false;
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === curso_id) {
        configSheet.getRange(i + 1, estadoColIndex + 1).setValue('ACTIVO');
        cursoEncontrado = true;
        break;
      }
    }

    if (!cursoEncontrado) {
      return {
        success: false,
        error: 'Curso no encontrado'
      };
    }

    return {
      success: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Obtener el curso activo
function getCursoActivo() {
  try {
    const configData = getConfigData();

    if (!configData.success) {
      return configData;
    }

    const cursoActivo = configData.cursos.find(curso => curso.estado === 'ACTIVO');

    if (!cursoActivo) {
      return {
        success: false,
        error: 'No hay curso activo'
      };
    }

    return {
      success: true,
      curso: cursoActivo
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Actualizar la configuración
function updateConfig(data) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const configSheet = ss.getSheetByName(CONFIG_SHEET_NAME);

    if (!configSheet) {
      return {
        success: false,
        error: 'No existe la hoja de configuración'
      };
    }

    // Limpiar la hoja
    const lastRow = configSheet.getLastRow();
    if (lastRow > 1) {
      configSheet.deleteRows(2, lastRow - 1);
    }

    // Agregar los datos actualizados (con región)
    for (const curso of data) {
      configSheet.appendRow([
        curso.curso_id,
        curso.region || '',
        curso.fecha_inicio,
        curso.fecha_fin,
        curso.estado,
        curso.cupo_maximo,
        curso.fecha_sesion_1 || '',
        curso.fecha_sesion_2 || '',
        curso.fecha_sesion_3 || ''
      ]);
    }

    return {
      success: true
    };
  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// ============================================
// FUNCIONES PARA ASISTENCIAS (NUEVAS)
// ============================================

// Función para obtener todas las asistencias
function getAsistencias() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
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

      return {
        success: true,
        asistencias: []
      };
    }

    const data = sheet.getDataRange().getValues();

    // Si solo hay encabezados
    if (data.length <= 1) {
      return {
        success: true,
        asistencias: []
      };
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

    return {
      success: true,
      asistencias: asistencias
    };

  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Función para agregar una nueva asistencia
function addAsistencia(data) {
  // OPTIMIZACIÓN: Usar LockService para evitar race conditions con 50 usuarios simultáneos
  const lock = LockService.getScriptLock();

  try {
    // Intentar obtener el lock, esperar hasta 10 segundos
    lock.waitLock(10000);
  } catch (e) {
    return {
      success: false,
      error: 'Sistema ocupado procesando otras solicitudes. Por favor, intente nuevamente en unos segundos.'
    };
  }

  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
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

    // OPTIMIZACIÓN: Solo leer columnas necesarias (B, C, D) en lugar de toda la hoja
    const lastRow = sheet.getLastRow();

    if (lastRow > 1) {
      // Leer solo las columnas curso_id (B), rut (C), sesion (D)
      const searchRange = sheet.getRange(2, 2, lastRow - 1, 3);
      const existingData = searchRange.getValues();

      // OPTIMIZACIÓN: Usar find() más eficiente que loop manual
      const duplicate = existingData.find(row =>
        row[0] === data.curso_id &&
        row[1] === data.rut &&
        row[2] === data.sesion
      );

      if (duplicate) {
        return {
          success: false,
          error: 'Ya existe un registro de asistencia para este participante en esta sesión'
        };
      }
    }

    // Generar ID único con timestamp para mayor unicidad
    const timestamp = new Date().getTime();
    const newId = `ASIST-${timestamp}-${lastRow}`;

    // Agregar nueva fila con fecha actual si no se proporcionó
    const fechaRegistro = data.fecha_registro || new Date().toISOString();

    sheet.appendRow([
      newId,
      data.curso_id,
      data.rut,
      data.sesion,
      fechaRegistro,
      data.estado || 'presente',
      data.metodo || 'manual'
    ]);

    return {
      success: true,
      message: 'Asistencia registrada correctamente',
      id: newId
    };

  } catch (error) {
    console.error('Error en addAsistencia:', error);
    return {
      success: false,
      error: error.toString()
    };
  } finally {
    // CRÍTICO: Siempre liberar el lock, incluso si hay error
    lock.releaseLock();
  }
}

// Función para eliminar una asistencia
function deleteAsistencia(data) {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = ss.getSheetByName(SHEET_NAME_ASISTENCIAS);

    if (!sheet) {
      return {
        success: false,
        error: 'Hoja de asistencias no encontrada'
      };
    }

    const values = sheet.getDataRange().getValues();

    // Buscar y eliminar la fila con el ID correspondiente
    for (let i = 1; i < values.length; i++) {
      if (values[i][0] == data.asistencia_id) {
        sheet.deleteRow(i + 1);

        return {
          success: true,
          message: 'Asistencia eliminada correctamente'
        };
      }
    }

    return {
      success: false,
      error: 'Registro no encontrado'
    };

  } catch (error) {
    return {
      success: false,
      error: error.toString()
    };
  }
}

// Función de prueba (mantener al final)
function testAddRegistro() {
  // Simular datos de registro completos
  const testData = {
    fecha_registro: new Date().toISOString(),
    curso_id: "TEST-CURSO",
    rut: "TEST-RUT",
    nombres: "NOMBRE TEST",
    apellido_paterno: "APELLIDO TEST",
    apellido_materno: "MATERNO TEST",
    nacionalidad: "TEST",
    email: "test@example.com",
    gmail: "test@gmail.com",
    sexo: "Hombre",
    rol: "TEST",
    rut_empresa: "TEST-EMPRESA",
    razon_social: "TEST SA",
    region: "TEST REGION",
    comuna: "TEST COMUNA",
    direccion: "TEST DIRECCION"
  };

  // Ejecutar la función addRegistro con los datos de prueba
  const result = addRegistro(testData);
  console.log("Resultado de prueba: " + JSON.stringify(result));
  return result;
}
