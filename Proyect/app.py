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
        [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0e1117 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #161b22 !important;
        }
        h1, h2, h3, .stMarkdown p, label {
            color: #f0f6fc !important;
        }
        div[data-testid="stAlert"] * {
            color: #1c1917 !important;
        }
        [data-testid="stFileUploadDropzone"] {
            background-color: #161b22 !important;
            border-color: #30363d !important;
        }
        [data-testid="stFileUploadDropzone"] * {
            color: #f0f6fc !important;
        }
    </style>
    """, unsafe_allow_html=True)

# Estilo para etiquetas de código
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
st.sidebar.markdown(f"**Formato:** `{motor_actual['formato_importacion']}`")
st.sidebar.markdown("**Columnas requeridas:**")
for c in motor_actual.get("columnas_requeridas", []):
    st.sidebar.markdown(f"- `{c}`")

# Etiqueta de formato de importación
st.info(f"**Formato de importación:** `{motor_actual['formato_importacion']}`")

# Subida de archivo
archivo_subido = st.file_uploader("Sube tu archivo (CSV o Excel):", type=["csv", "xlsx", "xls"])

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

            # --- SECCIÓN DE HERRAMIENTAS DE CORRECCIÓN ---
            st.markdown("### 🛠️ Opciones de Limpieza Automática")
            st.markdown("Marca las casillas si deseas aplicar las correcciones antes de evaluar o descargar:")
            
            col_chk1, col_chk2 = st.columns(2)
            
            with col_chk1:
                chk_limpiar_nombre = st.checkbox(
                    "✂️ Eliminar matrícula del campo NombreApellido", 
                    value=False,
                    help="Remueve la matrícula duplicada al inicio del nombre."
                )
                
            with col_chk2:
                chk_agregar_mas = st.checkbox(
                    "🪄 Agregar símbolo (+) a los teléfonos que no lo tengan", 
                    value=False,
                    help="Antepone el signo + respetando el número existente."
                )

            # --- APLICACIÓN DE CORRECCIONES ---
            if chk_limpiar_nombre and col_mat_real and col_nom_real:
                mats = df[col_mat_real].astype(str).str.strip()
                noms = df[col_nom_real].astype(str).str.strip()
                
                # Mascara donde el nombre inicia con la matricula
                mask = noms.str.startswith(mats, na=False)
                # Remueve la matricula en
