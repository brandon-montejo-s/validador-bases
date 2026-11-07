import json
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Validador de Motores", layout="wide")

# Cargar configuración de motores
@st.cache_data
def cargar_configuracion():
    with open("motores_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config_motores = cargar_configuracion()

st.title("🛠️ Asistente de Operaciones y Validación de Motores")

# Menú lateral
opcion = st.sidebar.selectbox(
    "Selecciona una opción",
    ["Validar Layout de Archivo", "Consultar Manual de Procesos"],
)

if opcion == "Validar Layout de Archivo":
    st.header("Validación Automática de Base de Datos")

    # Seleccionar el motor
    nombres_motores = [m["motor"] for m in config_motores]
    motor_seleccionado = st.selectbox("Selecciona el motor de destino", nombres_motores)

    # Buscar la configuración del motor seleccionado
    datos_motor = next(m for m in config_motores if m["motor"] == motor_seleccionado)

    # Mostrar de forma destacada el Formato de Importación requerido
    st.markdown(
        f"""
        <div style="background-color: #1E293B; padding: 15px; border-radius: 8px; border-left: 5px solid #3B82F6; margin-bottom: 20px;">
            <h4 style="margin: 0; color: #F8FAFC;">📌 Formato de Importación Requerido:</h4>
            <h2 style="margin: 5px 0 0 0; color: #60A5FA;">{datos_motor['formato_importacion']}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Cargar archivo
    archivo = st.file_uploader("Sube tu archivo (Excel o CSV)", type=["csv", "xlsx"])

    if archivo is not None:
        try:
            if archivo.name.endswith(".csv"):
                try:
                    df = pd.read_csv(archivo, encoding="utf-8")
                except UnicodeDecodeError:
                    archivo.seek(0)
                    df = pd.read_csv(archivo, encoding="latin-1")
            else:
                df = pd.read_excel(archivo)
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            st.stop()

        st.subheader("Vista previa de los datos")
        st.dataframe(df.head(5), use_container_width=True)

        errores = []

        # 1. Validar columnas requeridas (insensible a mayúsculas/minúsculas)
        columnas_archivo = list(df.columns)
        columnas_archivo_lower = [c.strip().lower() for c in columnas_archivo]
        
        columnas_faltantes = []
        for col in datos_motor["columnas_requeridas"]:
            if col.strip().lower() not in columnas_archivo_lower:
                columnas_faltantes.append(col)

        if columnas_faltantes:
            errores.append(f"❌ **Faltan las siguientes columnas obligatorias:** `{', '.join(columnas_faltantes)}`")

        # 2. Validar formato de teléfono
        col_tel_buscada = datos_motor.get("columna_telefono", "telefono").strip().lower()
        col_telefono_real = next((col for col in columnas_archivo if col.strip().lower() == col_tel_buscada), None)

        df_telefonos_invalidos = pd.DataFrame()
        if col_telefono_real:
            regex_tel = re.compile(datos_motor["regla_telefono"])
            
            # Filtrar registros que no cumplen la regla
            mask_invalidos = ~df[col_telefono_real].astype(str).str.strip().str.match(regex_tel, na=False)
            df_telefonos_invalidos = df[mask_invalidos]

            if not df_telefonos_invalidos.empty:
                errores.append(
                    f"⚠️ **Se encontraron {len(df_telefonos_invalidos)} registros con teléfono inválido** "
                    f"en la columna `{col_telefono_real}` (deben empezar con '+' seguido de dígitos)."
                )
        else:
            errores.append(f"❌ **No se encontró la columna de teléfono esperada:** `{datos_motor.get('columna_telefono')}`")

        # Despliegue de Resultados
        st.divider()
        if errores:
            st.error("### El archivo contiene errores de validación:")
            for err in errores:
                st.markdown(err)

            # Mostrar tabla detallada de teléfonos erróneos si existen
            if not df_telefonos_invalidos.empty and col_telefono_real:
                with st.expander("🔍 Ver detalle de registros con teléfonos incorrectos", expanded=True):
                    st.dataframe(
                        df_telefonos_invalidos[[col_telefono_real] + [c for c in df.columns if c != col_telefono_real]],
                        use_container_width=True
                    )
        else:
            st.success("✅ **¡El archivo cumple con el layout y las validaciones correctamente!**")

elif opcion == "Consultar Manual de Procesos":
    st.header("🤖 Consultar Manual de Usuario")
    pregunta = st.text_input("¿Qué proceso necesitas consultar?")
    if pregunta:
        st.info(f"Mostrando procedimiento para: **{pregunta}**")