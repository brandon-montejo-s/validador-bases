import os
import json
import io
import re
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

# Interfaz Principal
st.title("🔍 Validador y Limpiador de Archivos por Motor")
st.markdown("Selecciona el motor correspondiente, sube tu archivo y corrige automáticamente o descarga tus datos procesados.")

# Lista desplegable de motores
opciones_motores = [f"{m['motor']} ({m['formato_importacion']})" for m in config_motores]
seleccion = st.selectbox("Selecciona el Motor / Formato:", opciones_motores)

# Datos del motor seleccionado
indice_seleccionado = opciones_motores.index(seleccion)
motor_actual = config_motores[indice_seleccionado]

# Etiqueta de formato de importación
st.info(f"**Formato de importación:** {motor_actual['formato_importacion']}")

# Subida de archivo
archivo_subido = st.file_uploader("Sube tu archivo (CSV o Excel):", type=["csv", "xlsx", "xls"])

if archivo_subido is not None:
    df = cargar_archivo(archivo_subido)
    
    if df is not None:
        # AJUSTE 1: Siempre mostrar los primeros 10 registros en la vista previa
        st.subheader("📋 Vista previa de los datos (Primeros 10 registros)")
        st.dataframe(df.head(10), use_container_width=True)
        
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
            
            # AJUSTE 2: Detección y cuadro de países involucrados
            if "columna_telefono" in motor_actual and motor_actual["columna_telefono"] in mapa_columnas:
                col_tel_real = mapa_columnas[motor_actual["columna_telefono"]]
                
                # Buscar prefijos internacionales en los teléfonos (ej. +52, +1, +34)
                telefonos_str = df[col_tel_real].astype(str).str.strip()
                prefijos_encontrados = telefonos_str.str.extract(r'(\+\d{1,3})')[0].dropna().unique()
                
                st.markdown("### 🌎 Análisis de Países / Prefijos en la Base")
                if len(prefijos_encontrados) > 0:
                    lista_prefijos = ", ".join(sorted(prefijos_encontrados))
                    st.warning(f"📌 **Se detectaron {len(prefijos_encontrados)} prefijo(s) internacional(es) en la base:** `{lista_prefijos}`")
                else:
                    st.info("ℹ️ No se detectaron símbolos `+` con prefijo de país en la columna de teléfonos o aún falta aplicarlo.")

            # Validación y corrección de Teléfonos
            if "columna_telefono" in motor_actual and "regla_telefono" in motor_actual:
                nombre_col_req = motor_actual["columna_telefono"]
                
                if nombre_col_req in mapa_columnas:
                    col_tel_real = mapa_columnas[nombre_col_req]
                    patron_regex = motor_actual["regla_telefono"]
                    
                    # Evaluar registros
                    serie_tel = df[col_tel_real].astype(str).str.strip()
                    mascara_validos = serie_tel.str.contains(patron_regex, regex=True, na=False)
                    
                    invalidos_df = df[~mascara_validos].copy()
                    cant_invalidos = len(invalidos_df)
                    
                    # Métricas en pantalla
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total de Registros", len(df))
                    col2.metric("Teléfonos Válidos", len(df) - cant_invalidos)
                    col3.metric("Teléfonos con Formato Incorrecto", cant_invalidos)
                    
                    if cant_invalidos > 0:
                        st.warning(f"⚠️ Se encontraron **{cant_invalidos} registros** sin el formato telefónico requerido en la columna `{col_tel_real}`.")
                        
                        # --- SECCIÓN DE AUTO-CORRECCIÓN INTERNACIONAL ---
                        st.markdown("### 🛠️ Herramientas de Corrección Rápida")
                        
                        col_prefijo, col_btn = st.columns([2, 2])
                        with col_prefijo:
                            prefijo = st.text_input("Prefijo o símbolo a agregar al inicio:", value="+")
                        
                        with col_btn:
                            st.write("") # Espaciador visual
                            if st.button("🪄 Agregar prefijo a números inválidos"):
                                def corregir_numero(val):
                                    val_str = str(val).strip()
                                    if not val_str.startswith('+'):
                                        num_limpio = "".join(filter(str.isdigit, val_str))
                                        if num_limpio:
                                            return f"{prefijo}{num_limpio}"
                                    return val_str
                                
                                df[col_tel_real] = df[col_tel_real].apply(corregir_numero)
                                st.success("✅ ¡Formato corregido exitosamente!")
                                st.rerun()

                        # Pestañas para ver o editar datos
                        tab1, tab2 = st.tabs(["👁️ Ver Filas con Error", "✏️ Editar Manualmente"])
                        
                        with tab1:
                            st.dataframe(invalidos_df, use_container_width=True)
                            # Descargar solo errores
                            bytes_err = df_a_excel(invalidos_df)
                            st.download_button(
                                label="📥 Descargar Reporte de Errores (Excel)",
                                data=bytes_err,
                                file_name="reporte_errores.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        with tab2:
                            st.info("Puedes modificar cualquier celda directamente en esta tabla antes de descargar:")
                            df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
                    else:
                        st.success(f"✅ Todos los números telefónicos en la columna `{col_tel_real}` cumplen con el formato.")

            # --- BOTÓN PARA DESCARGAR ARCHIVO FINAL LIMPIO ---
            st.divider()
            st.markdown("### 💾 Descargar Archivo Procesado")
            excel_limpio = df_a_excel(df)
            st.download_button(
                label="🚀 Descargar Archivo Completo (Excel)",
                data=excel_limpio,
                file_name=f"archivo_procesado_{motor_actual['motor']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# AJUSTE 3: Pie de página con los créditos del desarrollador
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666666; font-size: 14px; padding: 10px;'>"
    "🛠️ <b>Desarrollado por:</b> Brandon Montejo Sánchez"
    "</div>",
    unsafe_allow_html=True
)
