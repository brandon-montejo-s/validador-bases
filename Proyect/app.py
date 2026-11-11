import os
import json
import io
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Validador de Archivos de Motores",
    page_icon="🔍",
    layout="wide"
)

# Cargar la configuración leyendo el JSON desde la misma carpeta
@st.cache_data(ttl=60)
def cargar_configuracion():
    ruta_base = os.path.dirname(__file__)
    ruta_json = os.path.join(ruta_base, "motores_config.json")
    with open(ruta_json, "r", encoding="utf-8") as f:
        return json.load(f)

# Función para convertir DataFrame a Excel descargable
def df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# Función para cargar CSV o Excel de forma segura
def cargar_archivo(uploaded_file):
    nombre = uploaded_file.name
    try:
        if nombre.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin-1')
        elif nombre.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file)
        else:
            return None
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return None

# Cargar configuración de motores
try:
    config_motores = cargar_configuracion()
except Exception as e:
    st.error(f"Error crítico al cargar 'motores_config.json': {e}")
    st.stop()

# --- BARRA LATERAL (SIDEBAR): VISUALIZADOR DE CONFIGURACIÓN JSON ---
st.sidebar.title("⚙️ Administración")
st.sidebar.markdown("Consulta las reglas activas de los motores cargados en la plataforma.")

# Expander para ver el JSON en la Sidebar
with st.sidebar.expander("📄 Ver Configuración JSON Completa"):
    st.json(config_motores)

# Interfaz Principal
st.title("🔍 Validador y Limpiador de Archivos por Motor")
st.markdown("Selecciona el motor correspondiente, sube tu archivo y aplica las herramientas de limpieza automática.")

# Lista desplegable de motores
opciones_motores = [f"{m['motor']} ({m['formato_importacion']})" for m in config_motores]
seleccion = st.selectbox("Selecciona el Motor / Formato:", opciones_motores)

# Datos del motor seleccionado
indice_seleccionado = opciones_motores.index(seleccion)
motor_actual = config_motores[indice_seleccionado]

# Resumen en Sidebar del motor activo
st.sidebar.markdown("---")
st.sidebar.subheader(f"📌 Motor Activo: {motor_actual['motor']}")
st.sidebar.markdown(f"**Formato:** {motor_actual['formato_importacion']}")
st.sidebar.markdown("**Columnas requeridas:**")
for c in motor_actual.get("columnas_requeridas", []):
    st.sidebar.markdown(f"- `{c}`")

# Etiqueta de formato de importación
st.info(f"**Formato de importación:** {motor_actual['formato_importacion']}")

# Subida de archivo
archivo_subido = st.file_uploader("Sube tu archivo (CSV o Excel):", type=["csv", "xlsx", "xls"])

if archivo_subido is not None:
    df_raw = cargar_archivo(archivo_subido)
    
    if df_raw is not None:
        # Copia de trabajo para aplicar transformaciones
        df = df_raw.copy()
        
        # Validar Columnas (case-insensitive)
        cols_requeridas = motor_actual["columnas_requeridas"]
        cols_archivo_lower = {str(c).strip().lower(): str(c) for c in df.columns}
        
        cols_faltantes = []
        mapa_columnas = {}
        
        for col in cols_requeridas:
            col_lower = col.strip().lower()
            if col_lower in cols_archivo_lower:
                mapa_columnas[col] = cols_archivo_lower[col_lower]
            else:
                cols_faltantes.append(col)
                
        if cols_faltantes:
            st.error(f"❌ **Faltan {len(cols_faltantes)} columnas requeridas:** {', '.join(cols_faltantes)}")
        else:
            st.success("✅ **Estructura correcta:** Todas las columnas requeridas están presentes.")
            
            # Ubicar columnas clave
            col_mat_real = mapa_columnas.get("Matricula")
            col_nom_real = mapa_columnas.get("NombreApellido")
            col_tel_real = mapa_columnas.get(motor_actual.get("columna_telefono", ""))

            # --- ANÁLISIS PREVIO DE ANOMALÍAS PARA CONTROLAR CHECKBOXES ---
            tiene_dup_nom_inicial = False
            if col_mat_real and col_nom_real:
                dup_mask_init = df.apply(
                    lambda row: str(row[col_nom_real]).strip().startswith(str(row[col_mat_real]).strip()) 
                    if pd.notna(row[col_mat_real]) and pd.notna(row[col_nom_real]) else False, 
                    axis=1
                )
                tiene_dup_nom_inicial = dup_mask_init.sum() > 0

            tiene_tel_inv_inicial = False
            if col_tel_real:
                patron_regex = motor_actual.get("regla_telefono", r"^\+")
                telefonos_init = df[col_tel_real].astype(str).str.strip()
                inv_mask_init = ~telefonos_init.str.contains(patron_regex, regex=True, na=False)
                tiene_tel_inv_inicial = inv_mask_init.sum() > 0

            # --- SECCIÓN DE HERRAMIENTAS DE CORRECCIÓN ---
            st.markdown("### 🛠️ Opciones de Limpieza Automática")
            st.markdown("Marca las casillas requeridas para procesar el archivo:")
            
            col_chk1, col_chk2 = st.columns(2)
            
            with col_chk1:
                chk_limpiar_nombre = st.checkbox(
                    "✂️ Eliminar matrícula del campo NombreApellido", 
                    value=False,
                    disabled=not tiene_dup_nom_inicial,
                    help="Se deshabilita automáticamente si no se detecta la matrícula en el nombre."
                )
                
            with col_chk2:
                chk_agregar_mas = st.checkbox(
                    "🪄 Agregar símbolo (+) a los teléfonos que no lo tengan", 
                    value=False,
                    disabled=not tiene_tel_inv_inicial,
                    help="Se deshabilita automáticamente si todos los teléfonos cumplen con el formato."
                )

            # --- APLICACIÓN DE CORRECCIONES ---
            if chk_limpiar_nombre and col_mat_real and col_nom_real:
                def remover_matricula(row):
                    mat = str(row[col_mat_real]).strip()
                    nom = str(row[col_nom_real]).strip()
                    if nom.startswith(mat):
                        return nom[len(mat):].strip()
                    return nom
                
                df[col_nom_real] = df.apply(remover_matricula, axis=1)

            if chk_agregar_mas and col_tel_real:
                def corregir_telefono(val):
                    val_str = str(val).strip()
                    if not val_str.startswith('+'):
                        num_limpio = "".join(filter(str.isdigit, val_str))
                        if num_limpio:
                            return f"+{num_limpio}"
                    return val_str
                
                df[col_tel_real] = df[col_tel_real].apply(corregir_telefono)

            # --- EVALUACIÓN DINÁMICA DE ANOMALÍAS POST-PROCESAMIENTO ---
            st.markdown("### ⚠️ Diagnóstico de la Base de Datos")
            
            # Evaluador de Matrícula en Nombre
            if col_mat_real and col_nom_real:
                duplicados_mask = df.apply(
                    lambda row: str(row[col_nom_real]).strip().startswith(str(row[col_mat_real]).strip()) 
                    if pd.notna(row[col_mat_real]) and pd.notna(row[col_nom_real]) else False, 
                    axis=1
                )
                cant_dup_nom = duplicados_mask.sum()
                if cant_dup_nom > 0:
                    st.warning(f"📌 **Matrícula duplicada en Nombre:** Se detectaron **{cant_dup_nom} registros** pendientes por corregir.")
                else:
                    st.success("✅ **NombreApellido:** Estructura correcta.")

            # Evaluador de Teléfonos
            cant_tel_inv = 0
            if col_tel_real:
                patron_regex = motor_actual.get("regla_telefono", r"^\+")
                telefonos_str = df[col_tel_real].astype(str).str.strip()
                invalidos_mask = ~telefonos_str.str.contains(patron_regex, regex=True, na=False)
                invalidos_df = df[invalidos_mask].copy()
                cant_tel_inv = len(invalidos_df)
                
                if cant_tel_inv > 0:
                    st.warning(f"📌 **Formato de Teléfono:** Se detectaron **{cant_tel_inv} registros** sin el símbolo `+` inicial o con formato incorrecto.")
                    
                    with st.expander(f"👁️ Ver tabla de registros con teléfono erróneo ({cant_tel_inv} pendientes)"):
                        st.dataframe(invalidos_df, use_container_width=True)
                else:
                    st.success("✅ **Teléfonos:** Todos los registros cumplen con el formato requerido.")

            # --- VISTA PREVIA DE DATOS PROCESADOS ---
            st.subheader("📋 Vista previa de los datos procesados (Primeros 10 registros)")
            st.dataframe(df.head(10), use_container_width=True)

            # Editor manual opcional
            with st.expander("✏️ Editar datos manualmente en la tabla"):
                df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

            # --- BOTONES DE DESCARGA CONDICIONALES ---
            st.divider()
            st.markdown("### 💾 Descargar Archivo Procesado")
            
            # Los botones se habilitan solo si no hay teléfonos pendientes de corregir o si no aplica
            permitir_descarga = (cant_tel_inv == 0)
            
            if not permitir_descarga:
                st.info("💡 **Aviso:** Marca la casilla `🪄 Agregar símbolo (+)...` para corregir los teléfonos pendientes y activar las opciones de descarga.")

            col_down1, col_down2 = st.columns(2)
            
            mime_excel = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

            with col_down1:
                excel_limpio = df_a_excel(df)
                st.download_button(
                    label="🚀 Descargar en Formato Excel (.xlsx)",
                    data=excel_limpio,
                    file_name=f"archivo_procesado_{motor_actual['motor']}.xlsx",
                    mime=mime_excel,
                    use_container_width=True,
                    disabled=not permitir_descarga
                )
                
            with col_down2:
                csv_limpio = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Descargar en Formato CSV (.csv)",
                    data=csv_limpio,
                    file_name=f"archivo_procesado_{motor_actual['motor']}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    disabled=not permitir_descarga
                )

# Pie de página con créditos del desarrollador
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666666; font-size: 14px; padding: 10px;'>"
    "🛠️ <b>Desarrollado por:</b> Brandon Montejo Sánchez"
    "</div>",
    unsafe_allow_html=True
)
