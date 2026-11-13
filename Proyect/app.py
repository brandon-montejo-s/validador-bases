import os
import json
import io
import pandas as pd
import streamlit as st

# 1. Configuración de la página
st.set_page_config(
    page_title="Validador & Limpiador de Motores",
    page_icon="⚡",
    layout="wide"
)

# 2. Cargar configuración JSON
def cargar_configuracion():
    rutas = [
        os.path.join(os.path.dirname(__file__), "motores_config.json"),
        "motores_config.json"
    ]
    for r in rutas:
        if os.path.exists(r):
            with open(r, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("No se encontró el archivo 'motores_config.json'.")

# 3. Convertir DataFrame a Excel
def df_a_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# 4. Cargar CSV o Excel de forma segura
def cargar_archivo(uploaded_file):
    nombre = uploaded_file.name
    try:
        if nombre.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        elif nombre.endswith('.csv'):
            for enc in ['utf-8', 'latin-1', 'utf-8-sig', 'cp1252']:
                for sep in [',', ';', '\t']:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=sep, encoding=enc, on_bad_lines='skip')
                        if len(df.columns) > 1:
                            return df
                    except Exception:
                        continue
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        return None
    return None

# Cargar motores
try:
    config_motores = cargar_configuracion()
except Exception as e:
    st.error(f"Error al cargar la configuración: {e}")
    st.stop()

# ENCABEZADO
st.title("⚡ Validador & Limpiador de Archivos")
st.caption("")
st.divider()

# Selección de motor
opciones_motores = [f"{m['motor']} ({m['formato_importacion']})" for m in config_motores]
seleccion = st.selectbox("🎯 Selecciona el Motor / Formato:", opciones_motores)

indice_seleccionado = opciones_motores.index(seleccion)
motor_actual = config_motores[indice_seleccionado]

# Resumen en Sidebar (Solo lectura para operadores)
st.sidebar.subheader(f"📌 Motor Activo: {motor_actual['motor']}")
st.sidebar.write(f"**Formato:** `{motor_actual['formato_importacion']}`")
st.sidebar.write("**Columnas requeridas:**")
for c in motor_actual.get("columnas_requeridas", []):
    st.sidebar.write(f"- `{c}`")

st.info(f"Formato de importación configurado: {motor_actual['formato_importacion']}")

# Subida de archivo
archivo_subido = st.file_uploader("📂 Sube tu archivo (CSV o Excel):", type=["csv", "xlsx", "xls"])

if archivo_subido is not None:
    df_raw = cargar_archivo(archivo_subido)
    
    if df_raw is None:
        st.error("No se pudo leer la estructura del archivo. Verifica que no esté dañado o vacío.")
    else:
        df = df_raw.copy()
        df.columns = [str(col).strip() for col in df.columns]
        
        cols_requeridas = motor_actual["columnas_requeridas"]
        cols_archivo_lower = {str(c).lower(): str(c) for c in df.columns}
        
        cols_faltantes = []
        mapa_columnas = {}
        
        for col_req in cols_requeridas:
            col_req_lower = col_req.strip().lower()
            encontrada = False
            
            if col_req_lower in cols_archivo_lower:
                mapa_columnas[col_req] = cols_archivo_lower[col_req_lower]
                encontrada = True
            else:
                for col_real_lower, col_real_original in cols_archivo_lower.items():
                    if (col_real_lower.startswith(col_req_lower[:6]) or col_req_lower.startswith(col_real_lower[:6])) and len(col_real_lower) >= 4:
                        mapa_columnas[col_req] = col_real_original
                        encontrada = True
                        break
            
            if not encontrada:
                cols_faltantes.append(col_req)
                
        if cols_faltantes:
            st.error(f"Faltan {len(cols_faltantes)} columnas requeridas: {', '.join(cols_faltantes)}")
        else:
            st.success("Estructura correcta: Todas las columnas requeridas están presentes.")
            
            col_mat_real = mapa_columnas.get("Matricula")
            col_nom_real = mapa_columnas.get("NombreApellido") or mapa_columnas.get("name")
            col_tel_real = mapa_columnas.get(motor_actual.get("columna_telefono", ""))

            cant_dup_nom = 0
            cant_tel_inv = 0
            dup_df = pd.DataFrame()
            invalidos_df = pd.DataFrame()

            tiene_dup_nom_inicial = False
            if col_mat_real and col_nom_real:
                dup_mask_init = df.apply(
                    lambda r: pd.notna(r[col_mat_real]) and pd.notna(r[col_nom_real]) and str(r[col_nom_real]).strip().startswith(str(r[col_mat_real]).split('.')[0].strip()) and len(str(r[col_mat_real]).split('.')[0].strip()) > 0, 
                    axis=1
                )
                tiene_dup_nom_inicial = bool(dup_mask_init.sum() > 0)

            tiene_tel_inv_inicial = False
            if col_tel_real:
                patron_regex = motor_actual.get("regla_telefono", r"^\+")
                telefonos_init = df[col_tel_real].astype(str).str.strip()
                inv_mask_init = ~telefonos_init.str.contains(patron_regex, regex=True, na=False)
                tiene_tel_inv_inicial = bool(inv_mask_init.sum() > 0)

            # --- HERRAMIENTAS DE LIMPIEZA AUTOMÁTICA ---
            st.subheader("🛠️ Herramientas de Limpieza Automática")
            
            col_chk1, col_chk2 = st.columns(2)
            
            with col_chk1:
                chk_limpiar_nombre = st.checkbox(
                    "Eliminar matrícula del campo Nombre / NombreApellido", 
                    value=False,
                    disabled=not tiene_dup_nom_inicial,
                    help="Se habilita si se detectan matrículas al inicio del nombre."
                )
                
            with col_chk2:
                chk_agregar_mas = st.checkbox(
                    "Agregar símbolo (+) a teléfonos sin formato", 
                    value=False,
                    disabled=not tiene_tel_inv_inicial,
                    help="Se habilita si hay teléfonos sin prefijo +."
                )

            if chk_limpiar_nombre and col_mat_real and col_nom_real:
                def limpiar_nom(r):
                    if pd.isna(r[col_mat_real]) or pd.isna(r[col_nom_real]):
                        return r[col_nom_real]
                    mat = str(r[col_mat_real]).split('.')[0].strip()
                    nom = str(r[col_nom_real]).strip()
                    return nom[len(mat):].strip() if nom.startswith(mat) else nom

                df[col_nom_real] = df.apply(limpiar_nom, axis=1)

            if chk_agregar_mas and col_tel_real:
                def limpiar_tel(val):
                    val_str = str(val).strip()
                    if not val_str.startswith('+'):
                        num_limpio = "".join(filter(str.isdigit, val_str))
                        if num_limpio:
                            return f"+{num_limpio}"
                    return val_str

                df[col_tel_real] = df[col_tel_real].apply(limpiar_tel)

            # --- DIAGNÓSTICO Y ALERTAS EN TIEMPO REAL ---
            st.subheader("📊 Diagnóstico de Estado")
            
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Registros", f"{len(df):,}")

            if col_mat_real and col_nom_real:
                duplicados_mask = df.apply(
                    lambda row: str(row[col_nom_real]).strip().startswith(str(row[col_mat_real]).split('.')[0].strip()) if pd.notna(row[col_mat_real]) and pd.notna(row[col_nom_real]) else False, 
                    axis=1
                )
                dup_df = df[duplicados_mask].copy()
                cant_dup_nom = len(dup_df)
            
            col_m2.metric("Matrículas Duplicadas", cant_dup_nom)

            if col_tel_real:
                patron_regex = motor_actual.get("regla_telefono", r"^\+")
                telefonos_str = df[col_tel_real].astype(str).str.strip()
                invalidos_mask = ~telefonos_str.str.contains(patron_regex, regex=True, na=False)
                invalidos_df = df[invalidos_mask].copy()
                cant_tel_inv = len(invalidos_df)
                
            col_m3.metric("Teléfonos con Error", cant_tel_inv)

            if cant_dup_nom > 0:
                st.warning(f"📌 Matrículas duplicadas en Nombre: Se encontraron {cant_dup_nom} registros donde el nombre inicia con la matrícula.")
                with st.expander(f"👁️ Ver tabla de registros con matrícula duplicada ({cant_dup_nom})"):
                    st.dataframe(dup_df, use_container_width=True)
            else:
                st.success("✅ Nombre: Sin matrículas duplicadas en el campo de nombre.")

            if cant_tel_inv > 0:
                st.warning(f"📌 Teléfonos pendientes: Se encontraron {cant_tel_inv} registros sin el símbolo '+' inicial.")
                with st.expander(f"👁️ Ver tabla de registros con teléfono erróneo ({cant_tel_inv})"):
                    st.dataframe(invalidos_df, use_container_width=True)
            else:
                st.success("✅ Teléfonos: Registros con formato internacional correcto.")

            st.subheader("📋 Vista Previa de Datos Procesados (Primeros 10 registros)")
            st.dataframe(df.head(10), use_container_width=True)

            with st.expander("✏️ Edición Manual de Emergencia"):
                df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

            # --- DESCARGA FINAL ---
            st.divider()
            st.subheader("💾 Exportar Archivo Final")
            
            permitir_descarga = True if (cant_tel_inv == 0 or chk_agregar_mas or chk_limpiar_nombre) else False
            
            if not permitir_descarga:
                st.info("💡 Aviso: Activa alguna casilla de limpieza arriba para habilitar la descarga.")

            col_down1, col_down2 = st.columns(2)
            mime_excel = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )

            with col_down1:
                excel_limpio = df_a_excel(df)
                st.download_button(
                    label="🚀 Descargar Excel (.xlsx)",
                    data=excel_limpio,
                    file_name=f"archivo_procesado_{motor_actual['motor']}.xlsx",
                    mime=mime_excel,
                    use_container_width=True,
                    disabled=not permitir_descarga
                )
                
            with col_down2:
                separador_csv = ";" if motor_actual.get("formato_importacion") == "Cobranza_LTM" else ","
                csv_limpio = df.to_csv(index=False, sep=separador_csv).encode('utf-8')
                st.download_button(
                    label="📄 Descargar CSV (.csv)",
                    data=csv_limpio,
                    file_name=f"archivo_procesado_{motor_actual['motor']}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    disabled=not permitir_descarga
                )

# Pie de página
st.divider()
st.caption("⚡ Plataforma desarrollada por: Brandon Montejo Sánchez")
