import os
import json
import io
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Validador y Limpiador de Archivos",
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

# Selector de Tema Oscuro / Claro en Sidebar
modo_oscuro = st.sidebar.toggle("🌙 Modo Oscuro", value=False)

if modo_oscuro:
    st.markdown("""
    <style>
        /* Fondo general en modo oscuro */
        [data-testid="stAppViewContainer"] {
            background-color: #0e1117 !important;
        }
        [data-testid="stHeader"] {
            background-color: #0e1117 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #161b22 !important;
        }
        
        /* Textos principales en blanco */
        h1, h2, h3, .stMarkdown p, label {
            color: #f0f6fc !important;
        }
        
        /* Cajas de Alertas e Info */
        div[data-testid="stAlert"] * {
            color: #1c1917 !important;
        }
        
        /* Cajas de subida de archivos */
        [data-testid="stFileUploadDropzone"] {
            background-color: #161b22 !important;
            border-color: #30363d !important;
        }
        [data-testid="stFileUploadDropzone"] * {
            color: #f0f6fc !important;
        }
    </style>
    """, unsafe_allow_html=True)

# Estilo permanente para que las etiquetas de código (Sidebar e Info) siempre sean legibles
st.markdown("""
<style>
    code {
        color: #0f172a !important;
        background-color: #e2e8f0 !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# Expander para ver el JSON en la Sidebar
with st.
