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

# Función ULTRA ROBUSTA para cargar CSV o Excel
def cargar_archivo(uploaded_file):
    nombre = uploaded_file.name
    try:
        if nombre.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded_file)
        
        elif nombre.endswith('.csv'):
            codificaciones = ['utf-8', 'latin-1', 'utf-8-sig', 'cp1252']
            delimitadores = [',', ';', '\t']

            for enc in codificaciones:
                for sep in delimitadores:
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
        st.error(f"❌ Error al procesar el archivo: {e}")
        return None
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
    <div class="header-subtitle">Selecciona el motor objetivo, sube tu base de datos y automat
