import io
import json
import os
import re
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Validador y Dashboard de Motores", layout="wide")

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

        # Limpiar nombres de columnas de espacios accidentales
        df.columns = [str(c).strip() for c in df.columns]

        st.subheader("Vista previa de los datos originales")
        st.dataframe(df.head(5), use_container_width=True)

        errores = []
        columnas_archivo = list(df.columns)
        columnas_archivo_lower = [c.lower() for c in columnas_archivo]

        # 1. Validar columnas requeridas
        columnas_faltantes = [
            col for col in datos_motor["columnas_requeridas"]
            if col.strip().lower() not in columnas_archivo_lower
        ]

        if columnas_faltantes:
            errores.append(f"❌ **Faltan las siguientes columnas obligatorias:** `{', '.join(columnas_faltantes)}`")

        # 2. Identificar columna de teléfono y columna de matrícula (si existe)
        col_tel_buscada = datos_motor.get("columna_telefono", "telefono").strip().lower()
        col_telefono_real = next((col for col in columnas_archivo if col.lower() == col_tel_buscada), None)
        col_matricula_real = next((col for col in columnas_archivo if "matricula" in col.lower()), None)

        df_telefonos_invalidos = pd.DataFrame()
        if col_telefono_real:
            regex_tel = re.compile(datos_motor["regla_telefono"])
            serie_tel = df[col_telefono_real].fillna("").astype(str).str.strip()
            mask_invalidos = ~serie_tel.str.match(regex_tel, na=False)
            df_telefonos_invalidos = df[mask_invalidos]

            if not df_telefonos_invalidos.empty:
                errores.append(
                    f"⚠️ **Se encontraron {len(df_telefonos_invalidos)} registros con teléfono inválido** "
                    f"en la columna `{col_telefono_real}` (deben empezar con '+' seguido de dígitos)."
                )
        else:
            errores.append(f"❌ **No se encontró la columna de teléfono esperada:** `{datos_motor.get('columna_telefono')}`")

        # 3. Detectar duplicados
        col_clave_dup = col_matricula_real if col_matricula_real else col_telefono_real
        total_duplicados = 0
        if col_clave_dup:
            total_duplicados = int(df.duplicated(subset=[col_clave_dup]).sum())
            if total_duplicados > 0:
                errores.append(
                    f"⚠️ **Se detectaron {total_duplicados} registros duplicados** tomando como referencia `{col_clave_dup}`."
                )

        # Despliegue de diagnósticos
        st.divider()
        if errores:
            st.error("### El archivo contiene observaciones:")
            for err in errores:
                st.markdown(err)

            if not df_telefonos_invalidos.empty and col_telefono_real:
                with st.expander("🔍 Ver detalle de registros con teléfonos incorrectos", expanded=False):
                    st.dataframe(
                        df_telefonos_invalidos[[col_telefono_real] + [c for c in df.columns if c != col_telefono_real]],
                        use_container_width=True,
                    )
        else:
            st.success("✅ **¡El archivo cumple con el layout y las validaciones correctamente!**")

        # ======================================================================
        # HERRAMIENTAS DE LIMPIEZA Y DESCARGA DE BASE
        # ======================================================================
        st.divider()
        st.subheader("🧹 Limpieza Automática y Descarga de Base")

        col_chk1, col_chk2 = st.columns(2)
        with col_chk1:
            agregar_mas = st.checkbox(
                "➕ Agregar signo '+' automáticamente a los teléfonos que no lo tengan",
                value=True,
            )
        with col_chk2:
            quitar_duplicados = st.checkbox(
                f"🗑️ Eliminar registros duplicados ({total_duplicados} detectados)"
                if col_clave_dup else "🗑️ Eliminar filas completamente duplicadas",
                value=False,
            )

        df_procesado = df.copy()

        # Aplicar corrección de '+' en teléfonos
        if agregar_mas and col_telefono_real:
            def normalizar_telefono(val):
                if pd.isna(val):
                    return val
                texto = str(val).strip()
                if texto == "" or texto.lower() == "nan":
                    return ""
                # Quitar espacios o guiones internos
                texto_limpio = re.sub(r"[\s\-()]", "", texto)
                if not texto_limpio.startswith("+") and texto_limpio.isdigit():
                    return f"+{texto_limpio}"
                return texto_limpio

            df_procesado[col_telefono_real] = df_procesado[col_telefono_real].apply(normalizar_telefono)

        # Aplicar eliminación de duplicados
        if quitar_duplicados:
            if col_clave_dup:
                df_procesado = df_procesado.drop_duplicates(subset=[col_clave_dup], keep="first")
            else:
                df_procesado = df_procesado.drop_duplicates(keep="first")

        # Métricas resumen de la base lista para descargar
        m1, m2, m3 = st.columns(3)
        m1.metric("Registros Originales", f"{len(df):,}")
        m2.metric("Registros Finales Listos", f"{len(df_procesado):,}")
        m3.metric("Registros Eliminados", f"{len(df) - len(df_procesado):,}")

        with st.expander("👀 Vista previa de la base procesada lista para descargar"):
            st.dataframe(df_procesado.head(10), use_container_width=True)

        # Preparar archivos para descarga
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
    st.header("📊 Análisis Operativo de Lotes y Contactos")
    st.markdown("Sube tu archivo **`Control_Integrado_Lotes_Contactos.xlsx`** para generar el análisis automático.")

    archivo_control = st.file_uploader("Sube el archivo de Control de Lotes (.xlsx)", type=["xlsx"])

    if archivo_control is not None:
        try:
            excel_file = pd.ExcelFile(archivo_control)
            hoja = "BD_Cargas" if "BD_Cargas" in excel_file.sheet_names else excel_file.sheet_names[0]
            df_ctrl = pd.read_excel(archivo_control, sheet_name=hoja)

            # Renombrar las primeras 3 columnas por posición (A, B, C)
            cols = list(df_ctrl.columns)
            if len(cols) >= 3:
                cols[0] = "Periodo"
                cols[1] = "Turno"
                cols[2] = "Dia_Semana"
            df_ctrl.columns = [str(c).strip() for c in cols]

            # Limpiar separadores de miles y convertir a numérico
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

            # Filtrar filas válidas
            if "# registros a cargar" in df_ctrl.columns:
                df_ctrl = df_ctrl[df_ctrl["# registros a cargar"] > 0]

            # Procesar fecha de activación
            if "Fecha de Activacion" in df_ctrl.columns:
                df_ctrl["Fecha_Dt"] = pd.to_datetime(df_ctrl["Fecha de Activacion"], dayfirst=True, errors="coerce")

            # --- BARRA DE FILTROS ---
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

            # --- TARJETAS DE KPIs ---
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

            # --- FILA 1 DE GRÁFICAS: EVOLUCIÓN DIARIA ---
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

            # --- FILA 2 DE GRÁFICAS: ANALISTA Y CAMPAÑA ---
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

            # --- FILA 3 DE GRÁFICAS: TURNO Y DÍA DE LA SEMANA ---
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

            # Tabla resumen inferior
            with st.expander("📋 Ver detalle de lotes filtrados"):
                st.dataframe(df_ctrl.drop(columns=["Fecha_Dt"], errors="ignore"), use_container_width=True)

        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo de control: {e}")

# ==============================================================================
# OPCIÓN 3: MANUAL DE PROCESOS
# ==============================================================================
elif opcion == "Consultar Manual de Procesos":
    st.header("🤖 Consultar Manual de Usuario")
    pregunta = st.text_input("¿Qué proceso necesitas consultar?")
    if pregunta:
        st.info(f"Mostrando procedimiento para: **{pregunta}**")
