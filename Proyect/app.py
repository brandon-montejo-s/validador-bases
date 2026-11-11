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

# 2. ESTILOS CSS PERSONALIZADOS (UI PRO Y CONTRASTE EN SIDEBAR)
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
    
    /* Personalización de la Sidebar */
    [data-testid="stSidebar"] {
        background-color: #111827;
        color: #ffffff;
    }
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] div {
        color: #e5e7eb;
    }
    
    /* Legibilidad para etiquetas code en la Sidebar */
    [data-testid="stSidebar"] code {
        background-color: #1f2937 !important;
        color: #60a5fa !important;
        border: 1px solid #374151 !important;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
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

# Función segura para cargar la configuración JSON
def cargar_configuracion():
    rutas_posibles = [
        os.path.join(os.path.dirname(__file__), "motores_config.json"),
        "motores_config.json"
    ]
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("No se encontró el archivo 'motores_config.json'.")

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
                df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8')
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='latin-1')
        elif nombre.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file)
        else:
            return None
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return None

# Intentar cargar la configuración
try:
    config_motores = cargar_configuracion()
except Exception as e:
    st.error(f"❌ **Error al cargar la configuración:** {e}")
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
        
        # Limpieza de espacios blancos invisibles en los nombres de columna del archivo
        df.columns = [str(col).strip() for col in df.columns]
        
        # Mapeo flexible de columnas (case-insensitive y tolerante a espacios/recortes)
        cols_requeridas = motor_actual["columnas_requeridas"]
        cols_archivo_lower = {str(c).lower(): str(c) for c in df.columns}
        
        cols_faltantes = []
        mapa_columnas = {}
        
        for col_req in cols_requeridas:
            col_req_lower = col_req.strip().lower()
            encontrada = False
            
            # 1. Co
