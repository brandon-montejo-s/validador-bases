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
            # Probar varias combinaciones de codificación y delimitador
            codificaciones = ['utf-8', 'latin-1', 'utf-8-sig', 'cp1252']
            delimitadores = [',', ';', '\t']

            for enc in codificaciones:
                for sep in delimitadores:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=sep, encoding=enc, on_bad_lines='skip')
                        # Si leyó correctamente más de una columna, encontramos la estructura
                        if len(df.columns) > 1:
                            return df
                    except Exception:
                        continue

            # Último intento con engine python autodect
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
    
    if df_raw is None:
        st.error("⚠️ No se pudo leer la estructura del archivo. Verifica que no esté dañado o vacío.")
    else:
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
            
            # 1. Coincidencia exacta limpia
            if col_req_lower in cols_archivo_lower:
                mapa_columnas[col_req] = cols_archivo_lower[col_req_lower]
                encontrada = True
            else:
                # 2. Coincidencia por subcadena/prefijo
                for col_real_lower, col_real_original in cols_archivo_lower.items():
                    if (col_real_lower.startswith(col_req_lower[:6]) or col_req_lower.startswith(col_real_lower[:6])) and len(col_real_lower) >= 4:
                        mapa_columnas[col_req] = col_real_original
                        encontrada = True
                        break
            
            if not encontrada:
                cols_faltantes.append(col_req)
                
        if cols_faltantes:
            st.error(f"❌ **Faltan {len(cols_faltantes)} columnas requeridas:** {', '.join(cols_faltantes)}")
        else:
            st.success("✅ **Estructura correcta:** Todas las columnas requeridas están presentes.")
            
            # Ubicar columnas clave
            col_mat_real = mapa_columnas.get("Matricula")
            col_nom_real = mapa_columnas.get("NombreApellido") or mapa_columnas.get("name")
            col_tel_real = mapa_columnas.get(motor_actual.get("columna_telefono", ""))

            # ANÁLISIS PREVIO DE ANOMALÍAS
            tiene_dup_nom_inicial = False
            if col_mat_real and col_nom_real:
                def es_duplicado(row):
                    if pd.isna(row[col_mat_real]) or pd.isna(row[col_nom_real]):
                        return False
                    mat_str = str(row[col_mat_real]).split('.')[0].strip()
                    nom_str = str(row[col_nom_real]).strip()
                    return nom_str.startswith(mat_str) and len(mat_str) > 0
                
                dup_mask_init = df.apply(es_duplicado, axis=1)
                tiene_dup_nom_inicial = bool(dup_mask_init.sum() > 0)

            tiene_tel_inv_inicial = False
            if col_tel_real:
                patron_regex = motor_actual.get("regla_telefono", r"^\+")
                telefonos_init = df[col_tel_real].astype(str).str.strip()
                inv_mask_init = ~telefonos_init.str.contains(patron_regex, regex=True, na=False)
                tiene_tel_inv_inicial = bool(inv_mask_init.sum() > 0)

            # HERRAMIENTAS DE CORRECCIÓN
            st.markdown("### 🛠️ Herramientas de Limpieza Automática")
            
            col_chk1, col_chk2 = st.columns(2)
            
            with col_chk1:
                chk_limpiar_nombre = st.checkbox(
                    "✂️ Eliminar matrícula del campo Nombre / NombreApellido", 
                    value=False,
                    disabled=not tiene_dup_nom_inicial,
                    help="Se habilita automáticamente si se detectan matrículas al inicio del nombre."
                )
                
            with col_chk2:
                chk_agregar_mas = st.checkbox(
                    "🪄 Agregar símbolo (+) a teléfonos sin formato", 
                    value=False,
                    disabled=not tiene_tel_inv_inicial,
                    help="Se habilita automáticamente si hay teléfonos sin el prefijo +."
                )

            # APLICACIÓN DE CORRECCIONES
            if chk_limpiar_nombre and col_mat_real and col_nom_real:
                def remover_matricula(row):
                    if pd.isna(row[col_mat_real]) or pd.isna(row[col_nom_real]):
                        return row[col_nom_real]
                    mat = str(row[col_mat_real]).split('.')[0].strip()
                    nom = str(row[col_nom_real]).strip()
                    if nom.startswith(mat):
                        return nom[len(mat):].strip()
                    return nom
                
                df[col_nom_real] = df.apply(remover_matricula, axis=1)

            if chk_agregar_mas and col_tel_real:
                def corregir_
