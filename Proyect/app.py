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

# 2. ESTILOS CSS PERSONALIZADOS (UI PRO)
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .header-box {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 24px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .header-title {
        font-size: 28px;
        font-weight: 700;
        margin: 0;
        color: #ffffff;
    }
    .header-subtitle {
        font-size: 15px;
        color: #e0e6ed;
        margin-top: 5px;
    }
    [data-testid="stSidebar"] {
        background-color: #111827;
        color: #ffffff;
    }
    [data-testid="stSidebar"] * {
        color: #e5e7eb !important;
    }
    .stButton>button, .stDownloadButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

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
st.sidebar.markdown("Consulta las reglas activas de los motores cargados.")

with st.sidebar.expander("📄 Ver Configuración JSON Completa"):
    st.json(config_motores)

# ENCABEZADO ESTILIZADO EN PANTALLA PRINCIPAL
st.markdown("""
<div class="header-box">
    <div class="header-title">⚡ Validador & Limpiador de Archivos</div>
    <div class="header-subtitle">Selecciona el motor objetivo, sube tu base de datos y automatiza la limpieza en segundos.</div>
</div>
""", unsafe_allow_html=True)

# Lista desplegable de motores
opciones_motores = [f"{m['motor']} ({m['formato_importacion']})" for m in config_motores]
seleccion = st.selectbox("🎯 **Selecciona el Motor / Formato:**", opciones_motores)

# Datos del motor seleccionado
indice_seleccionado = opciones_motores.index(seleccion)
motor_actual = config_motores[indice_seleccionado]

# Resumen en Sidebar del motor activo
st.sidebar.markdown("---")
st.sidebar.subheader(f"📌 Motor Activo: {motor_actual['motor']}")
st.sidebar.markdown(f"**Formato:** `{motor_actual['formato_importacion']}`")
st.sidebar.markdown("**Columnas requeridas:**")
for c in motor_actual.get("columnas_requeridas", []):
    st.sidebar.markdown(f"- `{c}`")

# Etiqueta de formato de importación
st.info(f"📋 **Formato de importación configurado:** `{motor_actual['formato_importacion']}`")

# Subida de archivo
archivo_subido = st.file_uploader("📂 **Sube tu archivo (CSV o Excel):**", type=["csv", "xlsx", "xls"])

if archivo_subido is not None:
    df_raw = cargar_archivo(archivo_subido)
    
    if df_raw is not None:
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

            # ANÁLISIS PREVIO DE ANOMALÍAS PARA CHECKBOXES
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
                tiene_
