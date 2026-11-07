import os
import json
import re
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Validador de Archivos de Motores",
    page_icon="🔍",
    layout="wide"
)

# Cargar la configuración leyendo el JSON desde la misma carpeta donde está app.py
@st.cache_data(ttl=60)
def cargar_configuracion():
    # os.path.dirname(__file__) resuelve la ruta relativa en cualquier servidor/nube
    ruta_base = os.path.dirname(__file__)
    ruta_json = os.path.join(ruta_base, "motores_config.json")
    
    with open(ruta_json, "r", encoding="utf-8") as f:
        return json.load(f)

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

# Cargar lista de motores
try:
    config_motores = cargar_configuracion()
except Exception as e:
    st.error(f"Error crítico al cargar 'motores_config.json': {e}")
    st.stop()

# Interfaz Principal
st.title("🔍 Validador de Archivos por Motor")
st.markdown("Selecciona el motor correspondiente y sube el archivo a validar.")

# Crear lista desplegable de motores
opciones_motores = [f"{m['motor']} ({m['formato_importacion']})" for m in config_motores]
seleccion = st.selectbox("Selecciona el Motor / Formato:", opciones_motores)

# Obtener los datos del motor seleccionado
indice_seleccionado = opciones_motores.index(seleccion)
motor_actual = config_motores[indice_seleccionado]

st.info(f"**Formato esperado:** {motor_actual['formato_importacion']}")

# Subida de archivo
archivo_subido = st.file_uploader(
    "Sube tu archivo (CSV o Excel):", 
    type=["csv", "xlsx", "xls"]
)

if archivo_subido is not None:
    df = cargar_archivo(archivo_subido)
    
    if df is not None:
        st.subheader("📋 Vista previa de los datos")
        st.dataframe(df.head(10))
        
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
                
        # Validación de Columnas Requeridas
        if cols_faltantes:
            st.error(f"❌ **Faltan {len(cols_faltantes)} columnas requeridas:** {', '.join(cols_faltantes)}")
        else:
            st.success("✅ **Estructura correcta:** Todas las columnas requeridas están presentes.")
            
            # Validación de Teléfonos (si está configurada la regla)
            if "columna_telefono" in motor_actual and "regla_telefono" in motor_actual:
                nombre_col_tel_req = motor_actual["columna_telefono"]
                
                if nombre_col_tel_req in mapa_columnas:
                    col_tel_real = mapa_columnas[nombre_col_tel_req]
                    patron_regex = motor_actual["regla_telefono"]
                    
                    # Convertir a texto y evaluar regex
                    serie_telefonos = df[col_tel_real].astype(str).str.strip()
                    masca_validos = serie_telefonos.str.contains(patron_regex, regex=True, na=False)
                    
                    invalidos_df = df[~masca_validos]
                    cant_invalidos = len(invalidos_df)
                    
                    if cant_invalidos > 0:
                        st.warning(f"⚠️ Se encontraron **{cant_invalidos} registros** con formato de teléfono incorrecto en la columna `{col_tel_real}`.")
                        with st.expander("Ver filas con teléfonos inválidos"):
                            st.dataframe(invalidos_df)
                    else:
                        st.success(f"✅ Todos los números telefónicos en la columna `{col_tel_real}` cumplen con el formato.")
