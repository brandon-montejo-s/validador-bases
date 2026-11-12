import os
import json
import streamlit as st

st.set_page_config(
    page_title="Administración de Motores",
    page_icon="🔐",
    layout="wide"
)

# --- CONTROL DE ACCESO ---
def verificar_acceso():
    if st.session_state.get("admin_autenticado", False):
        return True

    st.title("🔐 Panel de Administración Restringido")
    st.info("Esta sección permite modificar la estructura de los motores y reglas del sistema.")

    with st.form("login_admin"):
        clave_ingresada = st.text_input("Contraseña de Administrador:", type="password")
        submit = st.form_submit_button("Ingresar")

        if submit:
            # Lee la clave desde Streamlit Secrets (con respaldo por defecto si aún no se configura)
            clave_correcta = st.secrets.get("ADMIN_PASSWORD", "admin2026")
            if clave_ingresada == clave_correcta:
                st.session_state["admin_autenticado"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    return False

if not verificar_acceso():
    st.stop()

# --- GESTIÓN DE ARCHIVO JSON ---
def obtener_ruta_config():
    ruta_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "motores_config.json"))
    return ruta_raiz if os.path.exists(ruta_raiz) else "motores_config.json"

def cargar_configuracion():
    ruta = obtener_ruta_config()
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_configuracion(nueva_config):
    ruta = obtener_ruta_config()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(nueva_config, f, indent=2, ensure_ascii=False)

config_motores = cargar_configuracion()

# --- INTERFAZ DE ADMINISTRADOR ---
col_top1, col_top2 = st.columns([4, 1])
with col_top1:
    st.title("⚙️ Panel de Control de Motores")
    st.caption("Administra altas, bajas y reglas de validación de forma centralizada.")
with col_top2:
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state["admin_autenticado"] = False
        st.rerun()

st.divider()

col_izq, col_der = st.columns(2)

# 1. Agregar Motor
with col_izq:
    st.subheader("➕ Agregar Nuevo Motor")
    with st.form("form_alta_motor", clear_on_submit=True):
        nuevo_nombre = st.text_input("Nombre del Motor", placeholder="Ej: M8 o Motor E")
        nuevo_formato = st.text_input("Formato de Importación", placeholder="Ej: Cobranza_LTM")
        nueva_col_tel = st.text_input("Columna de Teléfono", value="Telefono")
        nueva_regla_tel = st.text_input("Expresión Regular Teléfono", value="^\\+")
        nuevas_cols_txt = st.text_area(
            "Columnas Requeridas (separadas por coma)",
            placeholder="Matricula, NombreApellido, Telefono, Email"
        )
        btn_guardar = st.form_submit_button("Guardar Nuevo Motor", type="primary", use_container_width=True)

        if btn_guardar:
            if not nuevo_nombre.strip() or not nuevo_formato.strip() or not nuevas_cols_txt.strip():
                st.error("Completa todos los campos obligatorios.")
            elif any(m["motor"].lower() == nuevo_nombre.strip().lower() for m in config_motores):
                st.warning("Ya existe un motor con ese nombre.")
            else:
                lista_cols = [c.strip() for c in nuevas_cols_txt.split(",") if c.strip()]
                config_motores.append({
                    "motor": nuevo_nombre.strip(),
                    "formato_importacion": nuevo_formato.strip(),
                    "columna_telefono": nueva_col_tel.strip(),
                    "columnas_requeridas": lista_cols,
                    "regla_telefono": nueva_regla_tel.strip()
                })
                guardar_configuracion(config_motores)
                st.success(f"Motor '{nuevo_nombre.strip()}' registrado correctamente.")
                st.rerun()

# 2. Eliminar o Respaldar
with col_der:
    st.subheader("🗑️ Eliminar Motor Existente")
    if len(config_motores) <= 1:
        st.info("Debe permanecer al menos un motor activo.")
    else:
        nombres = [m["motor"] for m in config_motores]
        seleccion_borrar = st.selectbox("Selecciona el motor a eliminar:", nombres)
        if st.button("Eliminar Motor", use_container_width=True):
            config_motores = [m for m in config_motores if m["motor"] != seleccion_borrar]
            guardar_configuracion(config_motores)
            st.success(f"Motor '{seleccion_borrar}' eliminado.")
            st.rerun()

    st.divider()
    st.subheader("💾 Respaldo para GitHub")
    st.write("Descarga el archivo actualizado para subirlo a tu repositorio y hacer los cambios permanentes:")
    json_str = json.dumps(config_motores, indent=2, ensure_ascii=False)
    st.download_button(
        label="⬇️ Descargar motores_config.json",
        data=json_str.encode("utf-8"),
        file_name="motores_config.json",
        mime="application/json",
        use_container_width=True
    )

# 3. Editor avanzado directo del JSON
st.divider()
with st.expander("🛠️ Editor Avanzado de Configuración (JSON Directo)"):
    st.caption("Modifica directamente nombres de columnas, formatos o reglas de motores existentes.")
    json_editado = st.text_area("Contenido JSON:", value=json_str, height=400)
    if st.button("Aplicar Cambios del Editor JSON"):
        try:
            datos_validados = json.loads(json_editado)
            if isinstance(datos_validados, list) and len(datos_validados) > 0:
                guardar_configuracion(datos_validados)
                st.success("Configuración JSON actualizada correctamente.")
                st.rerun()
            else:
                st.error("El JSON debe ser una lista con al menos un motor.")
        except json.JSONDecodeError as err:
            st.error(f"Error de sintaxis en el JSON: {err}")