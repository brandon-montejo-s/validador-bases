import io
import json
import os
import re
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Validador y Dashboard de Operaciones", layout="wide")

# ==============================================================================
# CONFIGURACIÓN DE ENLACES EN LÍNEA (PEGA AQUÍ TUS LINKS DE GOOGLE SHEETS)
# ==============================================================================
URL_CONTROL_CARGAS = ""  # Ej: "https://docs.google.com/spreadsheets/d/1aTGNResGD8S9PIyIw3J9-PXj1zPOnLiT/edit?usp=sharing&ouid=109570566825591874970&rtpof=true&sd=true"
URL_CONTROL_JIRAS = ""   # Ej: "https://docs.google.com/spreadsheets/d/12eRy0PgOsYEbJayhHDNbytORBTrizmpVODvO-PKRyPM/edit?usp=sharing"

def convertir_link_gsheets(url):
    """Convierte un enlace normal de Google Sheets en URL de descarga directa .xlsx"""
    if not url:
        return None
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        file_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    return url

@st.cache_data(ttl=300)  # Se actualiza automáticamente cada 5 minutos
def cargar_excel_desde_url(url_export):
    return pd.ExcelFile(url_export)

@st.cache_data
def cargar_configuracion():
    ruta_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_json = os.path.join(ruta_actual, "motores_config.json")
    with open(ruta_json, "r", encoding="utf-8") as f:
        return json.load(f)

config_motores = cargar_configuracion()

st.title("🛠️ Asistente de Operaciones y Validación de Motores")

# Menú lateral
opcion = st.sidebar.selectbox(
    "Selecciona una opción",
    [
        "Validar Layout de Archivo",
        "📊 Dashboard de Control de Cargas",
        "🎫 Dashboard de Control de JIRAS",
        "Consultar Manual de Procesos",
    ],
)

# ==============================================================================
# OPCIÓN 1: VALIDADOR DE LAYOUT, LIMPIEZA Y DESCARGA
# ==============================================================================
if opcion == "Validar Layout de Archivo":
    st.header("Validación Automática y Limpieza de Base de Datos")

    nombres_motores = [m["motor"] for m in config_motores]
    motor_seleccionado = st.selectbox("Selecciona el motor de destino", nombres_motores)
    datos_motor = next(m for m in config_motores if m["motor"] == motor_seleccionado)

    st.markdown(
        f"""
        <div style="background-color: #1E293B; padding: 15px; border-radius: 8px; border-left: 5px solid #3B82F6; margin-bottom: 20px;">
            <h4 style="margin: 0; color: #F8FAFC;">📌 Formato de Importación Requerido:</h4>
            <h2 style="margin: 5px 0 0 0; color: #60A5FA;">{datos_motor['formato_importacion']}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    archivo = st.file_uploader("Sube tu archivo (Excel o CSV)", type=["csv", "xlsx"])

    if archivo is not None:
        try:
            if archivo.name.endswith(".csv"):
                try:
                    df = pd.read_csv(archivo, encoding="utf-8", dtype=str)
                except UnicodeDecodeError:
                    archivo.seek(0)
                    df = pd.read_csv(archivo, encoding="latin-1", dtype=str)
            else:
                df = pd.read_excel(archivo, dtype=str)
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            st.stop()

        df.columns = [str(c).strip() for c in df.columns]

        st.subheader("Vista previa de los datos originales")
        st.dataframe(df.head(5), use_container_width=True)

        errores = []
        columnas_archivo = list(df.columns)
        columnas_archivo_lower = [c.lower() for c in columnas_archivo]

        columnas_faltantes = [
            col for col in datos_motor["columnas_requeridas"]
            if col.strip().lower() not in columnas_archivo_lower
        ]

        if columnas_faltantes:
            errores.append(f"❌ **Faltan las siguientes columnas obligatorias:** `{', '.join(columnas_faltantes)}`")

        col_tel_buscada = datos_motor.get("columna_telefono", "telefono").strip().lower()
        col_telefono_real = next((col for col in columnas_archivo if col.lower() == col_tel_buscada), None)
        col_matricula_real = next((col for col in columnas_archivo if "matricula" in col.lower()), None)
        col_nombre_real = next(
            (col for col in columnas_archivo if col.lower() in ["nombreapellido", "name", "nombre"]),
            None,
        )

        mask_tel_invalido = pd.Series(False, index=df.index)
        if col_telefono_real:
            regex_tel = re.compile(datos_motor["regla_telefono"])
            serie_tel = df[col_telefono_real].fillna("").astype(str).str.strip()
            mask_tel_invalido = ~serie_tel.str.match(regex_tel, na=False)
            cant_tel_err = int(mask_tel_invalido.sum())

            if cant_tel_err > 0:
                errores.append(
                    f"⚠️ **Se encontraron {cant_tel_err} registros sin signo '+' o con teléfono inválido** "
                    f"en la columna `{col_telefono_real}`."
                )
        else:
            errores.append(f"❌ **No se encontró la columna de teléfono esperada:** `{datos_motor.get('columna_telefono')}`")

        mask_mat_en_nombre = pd.Series(False, index=df.index)
        if col_matricula_real and col_nombre_real:
            def tiene_matricula_pegada(row):
                mat = str(row[col_matricula_real]).strip() if pd.notna(row[col_matricula_real]) else ""
                nom = str(row[col_nombre_real]).strip() if pd.notna(row[col_nombre_real]) else ""
                if mat and mat.lower() != "nan" and nom.startswith(mat):
                    return True
                return False

            mask_mat_en_nombre = df.apply(tiene_matricula_pegada, axis=1)
            cant_mat_nombre = int(mask_mat_en_nombre.sum())

            if cant_mat_nombre > 0:
                errores.append(
                    f"⚠️ **Se detectaron {cant_mat_nombre} registros con la matrícula duplicada dentro de `{col_nombre_real}`** "
                    f"(ej. `{df.loc[mask_mat_en_nombre, col_nombre_real].iloc[0]}`)."
                )

        st.divider()
        mask_cualquier_error = mask_tel_invalido | mask_mat_en_nombre

        if errores:
            st.error("### Observaciones detectadas en el archivo:")
            for err in errores:
                st.markdown(err)

            if mask_cualquier_error.any():
                df_errores_preview = df[mask_cualquier_error].copy()
                motivos = []
                for idx in df_errores_preview.index:
                    m_fila = []
                    if mask_mat_en_nombre.loc[idx]:
                        m_fila.append("Matrícula pegada en Nombre")
                    if mask_tel_invalido.loc[idx]:
                        m_fila.append("Teléfono sin '+' o inválido")
                    motivos.append(" | ".join(m_fila))

                df_errores_preview.insert(0, "⚠️ Motivo_Error", motivos)

                with st.expander(
                    f"🔍 Vista previa de registros con errores ({len(df_errores_preview)} filas detectadas)",
                    expanded=True,
                ):
                    st.dataframe(df_errores_preview, use_container_width=True)
        else:
            st.success("✅ **¡El archivo cumple con el layout y no tiene errores en nombres ni teléfonos!**")

        st.divider()
        st.subheader("🧹 Limpieza Automática y Descarga de Base")

        hay_error_tel = bool(mask_tel_invalido.any())
        hay_error_mat_nombre = bool(mask_mat_en_nombre.any())

        col_chk1, col_chk2 = st.columns(2)
        with col_chk1:
            agregar_mas = st.checkbox(
                f"➕ Agregar signo '+' a teléfonos ({int(mask_tel_invalido.sum())} detectados)",
                value=hay_error_tel,
                disabled=not hay_error_tel,
            )
        with col_chk2:
            limpiar_matricula_nombre = st.checkbox(
                f"✂️ Quitar matrícula duplicada de `{col_nombre_real}` ({int(mask_mat_en_nombre.sum())} detectados)"
                if col_nombre_real else "✂️ Quitar matrícula duplicada en Nombre",
                value=hay_error_mat_nombre,
                disabled=not hay_error_mat_nombre,
            )

        df_procesado = df.copy()

        if agregar_mas and hay_error_tel and col_telefono_real:
            def normalizar_telefono(val):
                if pd.isna(val):
                    return val
                texto = str(val).strip()
                if texto == "" or texto.lower() == "nan":
                    return ""
                texto_limpio = re.sub(r"[\s\-()]", "", texto)
                if not texto_limpio.startswith("+") and texto_limpio.isdigit():
                    return f"+{texto_limpio}"
                return texto_limpio

            df_procesado[col_telefono_real] = df_procesado[col_telefono_real].apply(normalizar_telefono)

        if limpiar_matricula_nombre and hay_error_mat_nombre and col_matricula_real and col_nombre_real:
            def remover_prefijo_matricula(row):
                mat = str(row[col_matricula_real]).strip() if pd.notna(row[col_matricula_real]) else ""
                nom = str(row[col_nombre_real]).strip() if pd.notna(row[col_nombre_real]) else ""
                if mat and mat.lower() != "nan" and nom.startswith(mat):
                    return nom[len(mat):].strip()
                return nom

            df_procesado[col_nombre_real] = df_procesado.apply(remover_prefijo_matricula, axis=1)

        corregidos_tel = int(mask_tel_invalido.sum()) if (agregar_mas and hay_error_tel) else 0
        corregidos_nom = int(mask_mat_en_nombre.sum()) if (limpiar_matricula_nombre and hay_error_mat_nombre) else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total de Registros", f"{len(df_procesado):,}")
        m2.metric("Teléfonos Corregidos (+)", f"{corregidos_tel:,}")
        m3.metric("Nombres Limpiados", f"{corregidos_nom:,}")

        with st.expander("👀 Vista previa de la base procesada lista para descargar", expanded=True):
            st.dataframe(df_procesado.head(10), use_container_width=True)

        nombre_base = os.path.splitext(archivo.name)[0]
        nombre_salida_xlsx = f"{nombre_base}_{motor_seleccionado}_LISTO.xlsx"
        nombre_salida_csv = f"{nombre_base}_{motor_seleccionado}_LISTO.csv"

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_procesado.to_excel(writer, index=False, sheet_name="Base_Limpia")
        datos_excel = buffer_excel.getvalue()

        datos_csv = df_procesado.to_csv(index=False).encode("utf-8-sig")

        btn1, btn2 = st.columns(2)
        with btn1:
            st.download_button(
                label="📥 Descargar Base Lista (.XLSX)",
                data=datos_excel,
                file_name=nombre_salida_xlsx,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with btn2:
            st.download_button(
                label="📥 Descargar Base Lista (.CSV)",
                data=datos_csv,
                file_name=nombre_salida_csv,
                mime="text/csv",
                use_container_width=True,
            )

# ==============================================================================
# OPCIÓN 2: DASHBOARD Y GRÁFICAS DE CONTROL DE CARGAS
# ==============================================================================
elif opcion == "📊 Dashboard de Control de Cargas":
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.header("📊 Análisis Operativo de Lotes y Contactos")
    with col_t2:
        if st.button("🔄 Actualizar datos", key="btn_ref_cargas", use_container_width=True):
            cargar_excel_desde_url.clear()
            st.rerun()

    with st.expander("🔗 Configurar enlace en línea o subir archivo manual (.xlsx)", expanded=not bool(URL_CONTROL_CARGAS)):
        link_cargas_input = st.text_input(
            "Enlace de Google Sheets (Control de Cargas):",
            value=URL_CONTROL_CARGAS,
            placeholder="Pega aquí el enlace compartido de Google Sheets...",
        )
        archivo_control = st.file_uploader(
            "O sube un archivo Excel local (.xlsx) si deseas analizar una copia manual:",
            type=["xlsx"],
            key="ctrl_cargas",
        )

    excel_file = None
    try:
        if archivo_control is not None:
            excel_file = pd.ExcelFile(archivo_control)
            st.caption("📂 Fuente activa: **Archivo local cargado manualmente**")
        elif link_cargas_input.strip():
            url_export = convertir_link_gsheets(link_cargas_input.strip())
            excel_file = cargar_excel_desde_url(url_export)
            st.caption("🌐 Fuente activa: **Google Sheets conectado en línea**")
    except Exception as e:
        st.error(f"No se pudo conectar con el enlace de Google Sheets. Verifica que el archivo esté compartido como 'Cualquier persona con el enlace'. Detalle: {e}")

    if excel_file is not None:
        try:
            hoja = "BD_Cargas" if "BD_Cargas" in excel_file.sheet_names else excel_file.sheet_names[0]
            df_ctrl = pd.read_excel(excel_file, sheet_name=hoja)

            cols = list(df_ctrl.columns)
            if len(cols) >= 3:
                cols[0] = "Periodo"
                cols[1] = "Turno"
                cols[2] = "Dia_Semana"
            df_ctrl.columns = [str(c).strip() for c in cols]

            cols_numericas = ["# registros a cargar", "# registros cargados", "# registros cancelados"]
            for col in cols_numericas:
                if col in df_ctrl.columns:
                    df_ctrl[col] = (
                        df_ctrl[col]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.replace(",", "", regex=False)
                    )
                    df_ctrl[col] = pd.to_numeric(df_ctrl[col], errors="coerce").fillna(0)

            if "# registros a cargar" in df_ctrl.columns:
                df_ctrl = df_ctrl[df_ctrl["# registros a cargar"] > 0]

            if "Fecha de Activacion" in df_ctrl.columns:
                df_ctrl["Fecha_Dt"] = pd.to_datetime(df_ctrl["Fecha de Activacion"], dayfirst=True, errors="coerce")

            st.subheader("Filtros de Análisis")
            f1, f2, f3, f4 = st.columns(4)

            with f1:
                if "MES" in df_ctrl.columns:
                    meses = ["Todos"] + sorted(df_ctrl["MES"].dropna().astype(str).unique().tolist())
                    mes_sel = st.selectbox("Mes", meses)
                    if mes_sel != "Todos":
                        df_ctrl = df_ctrl[df_ctrl["MES"].astype(str) == mes_sel]

            with f2:
                if "Turno" in df_ctrl.columns:
                    turnos = ["Todos"] + sorted(df_ctrl["Turno"].dropna().astype(str).unique().tolist())
                    turno_sel = st.selectbox("Turno", turnos)
                    if turno_sel != "Todos":
                        df_ctrl = df_ctrl[df_ctrl["Turno"].astype(str) == turno_sel]

            with f3:
                if "analista" in df_ctrl.columns:
                    analistas = ["Todos"] + sorted(df_ctrl["analista"].dropna().astype(str).unique().tolist())
                    analista_sel = st.selectbox("Analista", analistas)
                    if analista_sel != "Todos":
                        df_ctrl = df_ctrl[df_ctrl["analista"].astype(str) == analista_sel]

            with f4:
                if "Campaña a Carga" in df_ctrl.columns:
                    campanas = ["Todas"] + sorted(df_ctrl["Campaña a Carga"].dropna().astype(str).unique().tolist())
                    campana_sel = st.selectbox("Campaña", campanas)
                    if campana_sel != "Todas":
                        df_ctrl = df_ctrl[df_ctrl["Campaña a Carga"].astype(str) == campana_sel]

            st.divider()

            tot_a_cargar = int(df_ctrl["# registros a cargar"].sum()) if "# registros a cargar" in df_ctrl.columns else 0
            tot_cargados = int(df_ctrl["# registros cargados"].sum()) if "# registros cargados" in df_ctrl.columns else 0
            tot_cancelados = int(df_ctrl["# registros cancelados"].sum()) if "# registros cancelados" in df_ctrl.columns else 0
            tot_lotes = len(df_ctrl)
            tasa_efectividad = (tot_cargados / tot_a_cargar * 100) if tot_a_cargar > 0 else 0

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("📦 Lotes Procesados", f"{tot_lotes:,}")
            k2.metric("📥 A Cargar", f"{tot_a_cargar:,}")
            k3.metric("✅ Cargados", f"{tot_cargados:,}")
            k4.metric("🚫 Cancelados", f"{tot_cancelados:,}")
            k5.metric("📈 Efectividad", f"{tasa_efectividad:.1f}%")

            st.divider()

            if "Fecha_Dt" in df_ctrl.columns and not df_ctrl["Fecha_Dt"].dropna().empty:
                st.subheader("📅 Evolución Diaria de Registros Cargados vs. Cancelados")
                df_diario = (
                    df_ctrl.groupby("Fecha_Dt")[["# registros cargados", "# registros cancelados"]]
                    .sum()
                    .reset_index()
                    .sort_values("Fecha_Dt")
                )
                fig_diario = px.bar(
                    df_diario,
                    x="Fecha_Dt",
                    y=["# registros cargados", "# registros cancelados"],
                    barmode="stack",
                    labels={"Fecha_Dt": "Fecha de Activación", "value": "Cantidad de Registros", "variable": "Estatus"},
                    color_discrete_map={"# registros cargados": "#3B82F6", "# registros cancelados": "#EF4444"},
                )
                st.plotly_chart(fig_diario, use_container_width=True)

            g1, g2 = st.columns(2)

            with g1:
                if "analista" in df_ctrl.columns:
                    st.subheader("👤 Productividad por Analista")
                    df_analista = (
                        df_ctrl.groupby("analista")[["# registros cargados", "# registros cancelados"]]
                        .sum()
                        .reset_index()
                    )
                    fig_analista = px.bar(
                        df_analista,
                        x="analista",
                        y=["# registros cargados", "# registros cancelados"],
                        barmode="group",
                        color_discrete_map={"# registros cargados": "#10B981", "# registros cancelados": "#F59E0B"},
                    )
                    st.plotly_chart(fig_analista, use_container_width=True)

            with g2:
                if "Campaña a Carga" in df_ctrl.columns:
                    st.subheader("🎯 Volumen por Campaña")
                    df_campana = (
                        df_ctrl.groupby("Campaña a Carga")["# registros cargados"]
                        .sum()
                        .reset_index()
                        .sort_values(by="# registros cargados", ascending=True)
                    )
                    fig_campana = px.bar(
                        df_campana,
                        x="# registros cargados",
                        y="Campaña a Carga",
                        orientation="h",
                        color_discrete_sequence=["#6366F1"],
                    )
                    st.plotly_chart(fig_campana, use_container_width=True)

            g3, g4 = st.columns(2)

            with g3:
                if "Turno" in df_ctrl.columns:
                    st.subheader("🌓 Distribución por Turno")
                    df_turno = df_ctrl.groupby("Turno")["# registros cargados"].sum().reset_index()
                    fig_turno = px.pie(
                        df_turno,
                        names="Turno",
                        values="# registros cargados",
                        hole=0.4,
                        color_discrete_sequence=["#3B82F6", "#8B5CF6", "#EC4899"],
                    )
                    st.plotly_chart(fig_turno, use_container_width=True)

            with g4:
                if "Dia_Semana" in df_ctrl.columns:
                    st.subheader("📆 Carga por Día de la Semana")
                    orden_dias = ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES", "SABADO", "DOMINGO"]
                    df_dias = df_ctrl.groupby("Dia_Semana")["# registros cargados"].sum().reset_index()
                    df_dias["Dia_Semana"] = df_dias["Dia_Semana"].astype(str).str.upper().str.strip()
                    df_dias["Orden"] = df_dias["Dia_Semana"].apply(lambda x: orden_dias.index(x) if x in orden_dias else 99)
                    df_dias = df_dias.sort_values("Orden")

                    fig_dias = px.bar(
                        df_dias,
                        x="Dia_Semana",
                        y="# registros cargados",
                        color_discrete_sequence=["#14B8A6"],
                    )
                    st.plotly_chart(fig_dias, use_container_width=True)

            with st.expander("📋 Ver detalle de lotes filtrados"):
                st.dataframe(df_ctrl.drop(columns=["Fecha_Dt"], errors="ignore"), use_container_width=True)

        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo de control: {e}")

# ==============================================================================
# OPCIÓN 3: DASHBOARD Y GRÁFICAS DE CONTROL DE JIRAS
# ==============================================================================
elif opcion == "🎫 Dashboard de Control de JIRAS":
    col_j1, col_j2 = st.columns([4, 1])
    with col_j1:
        st.header("🎫 Análisis Operativo de Tickets e Incidencias (JIRA)")
    with col_j2:
        if st.button("🔄 Actualizar datos", key="btn_ref_jiras", use_container_width=True):
            cargar_excel_desde_url.clear()
            st.rerun()

    with st.expander("🔗 Configurar enlace en línea o subir archivo manual (.xlsx)", expanded=not bool(URL_CONTROL_JIRAS)):
        link_jiras_input = st.text_input(
            "Enlace de Google Sheets (Control de JIRAS):",
            value=URL_CONTROL_JIRAS,
            placeholder="Pega aquí el enlace compartido de Google Sheets...",
        )
        archivo_jiras = st.file_uploader(
            "O sube un archivo Excel local (.xlsx) si deseas analizar una copia manual:",
            type=["xlsx"],
            key="ctrl_jiras",
        )

    excel_jiras = None
    try:
        if archivo_jiras is not None:
            excel_jiras = pd.ExcelFile(archivo_jiras)
            st.caption("📂 Fuente activa: **Archivo local cargado manualmente**")
        elif link_jiras_input.strip():
            url_export_j = convertir_link_gsheets(link_jiras_input.strip())
            excel_jiras = cargar_excel_desde_url(url_export_j)
            st.caption("🌐 Fuente activa: **Google Sheets conectado en línea**")
    except Exception as e:
        st.error(f"No se pudo conectar con el enlace de Google Sheets. Verifica que el archivo esté compartido como 'Cualquier persona con el enlace'. Detalle: {e}")

    if excel_jiras is not None:
        try:
            hoja_j = "Jiras" if "Jiras" in excel_jiras.sheet_names else excel_jiras.sheet_names[0]
            df_jiras = pd.read_excel(excel_jiras, sheet_name=hoja_j)

            df_jiras.columns = [str(c).strip() for c in df_jiras.columns]
            col_incidencia = next((c for c in df_jiras.columns if c.lower() == "incidencia"), "Incidencia")

            if "JIRA" in df_jiras.columns:
                df_jiras = df_jiras[df_jiras["JIRA"].notna() & (df_jiras["JIRA"].astype(str).str.strip() != "")]

            cols_texto = ["Mes", "Area", "Estatus en Jira", "Prioridad", col_incidencia, "Quien reporta"]
            for c in cols_texto:
                if c in df_jiras.columns:
                    df_jiras[c] = df_jiras[c].fillna("Sin especificar").astype(str).str.strip()

            if "Fecha Inicio" in df_jiras.columns:
                df_jiras["Fecha_Inicio_Dt"] = pd.to_datetime(df_jiras["Fecha Inicio"], dayfirst=True, errors="coerce")

            st.subheader("Filtros de Análisis")
            jf1, jf2, jf3, jf4 = st.columns(4)

            with jf1:
                if "Mes" in df_jiras.columns:
                    meses_j = ["Todos"] + sorted(df_jiras["Mes"].unique().tolist())
                    mes_j_sel = st.selectbox("Mes", meses_j, key="j_mes")
                    if mes_j_sel != "Todos":
                        df_jiras = df_jiras[df_jiras["Mes"] == mes_j_sel]

            with jf2:
                if "Area" in df_jiras.columns:
                    areas_j = ["Todas"] + sorted(df_jiras["Area"].unique().tolist())
                    area_j_sel = st.selectbox("Área", areas_j, key="j_area")
                    if area_j_sel != "Todas":
                        df_jiras = df_jiras[df_jiras["Area"] == area_j_sel]

            with jf3:
                if "Prioridad" in df_jiras.columns:
                    prios_j = ["Todas"] + sorted(df_jiras["Prioridad"].unique().tolist())
                    prio_j_sel = st.selectbox("Prioridad", prios_j, key="j_prio")
                    if prio_j_sel != "Todas":
                        df_jiras = df_jiras[df_jiras["Prioridad"] == prio_j_sel]

            with jf4:
                if "Quien reporta" in df_jiras.columns:
                    rep_j = ["Todos"] + sorted(df_jiras["Quien reporta"].unique().tolist())
                    rep_j_sel = st.selectbox("Quien reporta", rep_j, key="j_rep")
                    if rep_j_sel != "Todos":
                        df_jiras = df_jiras[df_jiras["Quien reporta"] == rep_j_sel]

            st.divider()

            total_tickets = len(df_jiras)
            resueltos = int((df_jiras["Estatus en Jira"].str.lower() == "resuelto").sum()) if "Estatus en Jira" in df_jiras.columns else 0
            pendientes = total_tickets - resueltos
            alta_prio = int((df_jiras["Prioridad"].str.lower() == "alta").sum()) if "Prioridad" in df_jiras.columns else 0
            tasa_resolucion = (resueltos / total_tickets * 100) if total_tickets > 0 else 0

            jk1, jk2, jk3, jk4, jk5 = st.columns(5)
            jk1.metric("🎫 Total JIRAS", f"{total_tickets:,}")
            jk2.metric("✅ Resueltos", f"{resueltos:,}")
            jk3.metric("⏳ Abiertos / Otros", f"{pendientes:,}")
            jk4.metric("🔥 Prioridad Alta", f"{alta_prio:,}")
            jk5.metric("📈 Tasa Resolución", f"{tasa_resolucion:.1f}%")

            st.divider()

            jg1, jg2 = st.columns([2, 1])

            with jg1:
                if col_incidencia in df_jiras.columns:
                    st.subheader("🚨 Top Tipos de Incidencia")
                    df_inc = df_jiras[col_incidencia].value_counts().reset_index()
                    df_inc.columns = ["Incidencia", "Cantidad"]
                    df_inc = df_inc.sort_values("Cantidad", ascending=True)

                    fig_inc = px.bar(
                        df_inc,
                        x="Cantidad",
                        y="Incidencia",
                        orientation="h",
                        color_discrete_sequence=["#EF4444"],
                    )
                    st.plotly_chart(fig_inc, use_container_width=True)

            with jg2:
                if "Prioridad" in df_jiras.columns:
                    st.subheader("⚡ Tickets por Prioridad")
                    df_prio = df_jiras["Prioridad"].value_counts().reset_index()
                    df_prio.columns = ["Prioridad", "Cantidad"]

                    fig_prio = px.pie(
                        df_prio,
                        names="Prioridad",
                        values="Cantidad",
                        hole=0.45,
                        color="Prioridad",
                        color_discrete_map={
                            "Alta": "#DC2626",
                            "Media": "#D97706",
                            "Normal": "#2563EB",
                            "Baja": "#64748B",
                        },
                    )
                    st.plotly_chart(fig_prio, use_container_width=True)

            jg3, jg4 = st.columns(2)

            with jg3:
                if "Area" in df_jiras.columns:
                    st.subheader("🏢 Tickets por Área")
                    df_area = df_jiras["Area"].value_counts().reset_index()
                    df_area.columns = ["Area", "Cantidad"]

                    fig_area = px.bar(
                        df_area,
                        x="Area",
                        y="Cantidad",
                        color_discrete_sequence=["#6366F1"],
                    )
                    st.plotly_chart(fig_area, use_container_width=True)

            with jg4:
                if "Quien reporta" in df_jiras.columns:
                    st.subheader("👤 Tickets Reportados por Analista")
                    df_rep = df_jiras["Quien reporta"].value_counts().reset_index()
                    df_rep.columns = ["Analista", "Cantidad"]

                    fig_rep = px.bar(
                        df_rep,
                        x="Analista",
                        y="Cantidad",
                        color_discrete_sequence=["#10B981"],
                    )
                    st.plotly_chart(fig_rep, use_container_width=True)

            if "Fecha_Inicio_Dt" in df_jiras.columns and not df_jiras["Fecha_Inicio_Dt"].dropna().empty:
                st.subheader("📅 Evolución Diaria de Tickets Levantados")
                df_j_diario = (
                    df_jiras.groupby("Fecha_Inicio_Dt")
                    .size()
                    .reset_index(name="Tickets")
                    .sort_values("Fecha_Inicio_Dt")
                )
                fig_j_diario = px.line(
                    df_j_diario,
                    x="Fecha_Inicio_Dt",
                    y="Tickets",
                    markers=True,
                    labels={"Fecha_Inicio_Dt": "Fecha de Inicio", "Tickets": "Cantidad de JIRAS"},
                    color_discrete_sequence=["#3B82F6"],
                )
                st.plotly_chart(fig_j_diario, use_container_width=True)

            with st.expander("📋 Ver detalle de tickets JIRAS filtrados", expanded=False):
                cols_mostrar = [c for c in df_jiras.columns if c != "Fecha_Inicio_Dt"]
                st.dataframe(df_jiras[cols_mostrar], use_container_width=True)

        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo de JIRAS: {e}")

# ==============================================================================
# OPCIÓN 4: MANUAL DE PROCESOS
# ==============================================================================
elif opcion == "Consultar Manual de Procesos":
    st.header("🤖 Consultar Manual de Usuario")
    pregunta = st.text_input("¿Qué proceso necesitas consultar?")
    if pregunta:
        st.info(f"Mostrando procedimiento para: **{pregunta}**")
