from datetime import datetime, date
import io
import pandas as pd
import streamlit as st
from supabase import create_client

# Librerías para generación de PDF
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


# ==========================================
# CONEXIÓN CON SUPABASE
# ==========================================
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


try:
    supabase = init_supabase()
except Exception:
    st.error("Asegúrate de configurar los 'Secrets' (SUPABASE_URL y SUPABASE_KEY) en Streamlit.")
    st.stop()


class DesayunosSupabase:

    @staticmethod
    def obtener_menu():
        try:
            res = supabase.table("menu").select("*").execute()
            menu_dict = {item["dia"]: item["desayuno"] for item in res.data}
        except Exception:
            menu_dict = {}

        # Si el menú está vacío en Supabase, insertar los valores por defecto de una sola vez
        if not menu_dict:
            menu_defecto = [
                {"dia": "Lunes", "desayuno": "🥛 Lácteo / 🍎 Fruta fresca"},
                {
                    "dia": "Martes",
                    "desayuno": "🥪 Bocadillo o Sándwich",
                },
                {
                    "dia": "Miércoles",
                    "desayuno": "🥛 Lácteo / 🍎 Fruta fresca",
                },
                {
                    "dia": "Jueves",
                    "desayuno": "🥪 Bocadillo o Sándwich",
                },
                {
                    "dia": "Viernes",
                    "desayuno": (
                        "🎉 ¡Viernes Especial! (Desayuno Libre"
                        " 🍇🍌)"
                    ),
                },
            ]
            try:
                supabase.table("menu").upsert(
                    menu_defecto, on_conflict="dia"
                ).execute()
                menu_dict = {
                    item["dia"]: item["desayuno"] for item in menu_defecto
                }
            except Exception:
                # Si falla la escritura en Supabase, devolver el diccionario local
                menu_dict = {
                    item["dia"]: item["desayuno"] for item in menu_defecto
                }

        return menu_dict

    @staticmethod
    def actualizar_menu(menu_dict):
        datos_upsert = [
            {"dia": dia, "desayuno": desayuno}
            for dia, desayuno in menu_dict.items()
        ]
        supabase.table("menu").upsert(
            datos_upsert, on_conflict="dia"
        ).execute()

    @staticmethod
    def obtener_alumnos():
        try:
            res = (
                supabase.table("alumnos")
                .select("id, nombre")
                .order("nombre")
                .execute()
            )
            return [(item["id"], item["nombre"]) for item in res.data]
        except Exception:
            return []

    @staticmethod
    def agregar_alumno(nombre):
        try:
            nombre_limpio = nombre.strip()
            res = (
                supabase.table("alumnos")
                .insert({"nombre": nombre_limpio})
                .execute()
            )
            return True if res.data else False
        except Exception:
            return False

    @staticmethod
    def eliminar_alumno(alumno_id):
        try:
            supabase.table("alumnos").delete().eq("id", alumno_id).execute()
        except Exception:
            pass

    @staticmethod
    def obtener_registros():
        try:
            res = supabase.table("registro").select("*").execute()
            registros = {}
            for item in res.data:
                aid = item["alumno_id"]
                if aid not in registros:
                    registros[aid] = {}
                registros[aid][item["dia"]] = item["estado"]
            return registros
        except Exception:
            return {}

    @staticmethod
    def cambiar_estado_registro(alumno_id, dia, nuevo_estado):
        try:
            if nuevo_estado == "NINGUNO":
                supabase.table("registro").delete().eq(
                    "alumno_id", alumno_id
                ).eq("dia", dia).execute()
            else:
                supabase.table("registro").upsert(
                    {
                        "alumno_id": alumno_id,
                        "dia": dia,
                        "estado": nuevo_estado,
                    },
                    on_conflict="alumno_id, dia",
                ).execute()
        except Exception:
            pass

    @staticmethod
    def resetear_registros():
        try:
            supabase.table("registro").delete().neq("alumno_id", 0).execute()
        except Exception:
            pass

# ==========================================
# GENERADOR DE INFORMES PDF
# ==========================================
def generar_pdf_bytes(db, dias, fecha_inicio, fecha_fin):
    if not HAS_REPORTLAB:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#2E7D32"),
        alignment=1,
        spaceAfter=5,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#555555"),
        alignment=1,
        spaceAfter=15,
    )

    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=10,
        spaceAfter=5,
    )

    cell_header_style = ParagraphStyle(
        "CellHeader",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1,
    )

    cell_text_style = ParagraphStyle(
        "CellText",
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        alignment=1,
    )

    elements = []
    elements.append(Paragraph("CAMPEONATO DE DESAYUNOS SALUDABLES", title_style))
    f_str_i = fecha_inicio.strftime("%d/%m/%Y")
    f_str_f = fecha_fin.strftime("%d/%m/%Y")
    elements.append(Paragraph(f"Informe de Registro Semanal ({f_str_i} al {f_str_f})", subtitle_style))

    # Menú
    elements.append(Paragraph("Menú Saludable Establecido", h2_style))
    menu_data = db.obtener_menu()

    menu_table_data = [
        [Paragraph(f"<b>{dia}</b>", cell_header_style) for dia in dias],
        [Paragraph(menu_data.get(dia, "-"), ParagraphStyle("M", alignment=1, fontSize=9, fontName="Helvetica-Bold")) for dia in dias],
    ]

    t_menu = Table(menu_table_data, colWidths=[150] * 5)
    t_menu.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E8F5E9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A5D6A7")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_menu)
    elements.append(Spacer(1, 15))

    # Registro Alumnos
    elements.append(Paragraph("Control de Asistencia y Desayunos", h2_style))
    headers = ["Alumno / a"] + dias + ["Total Consecución"]
    table_data = [[Paragraph(f"<b>{h}</b>", cell_header_style) for h in headers]]

    alumnos = db.obtener_alumnos()
    registros = db.obtener_registros()
    totales_exito_clase = 0

    for alumno_id, nombre in alumnos:
        row = [Paragraph(f"<b>{nombre}</b>", ParagraphStyle("N", fontName="Helvetica", fontSize=9, alignment=0))]
        exitos_alumno = 0

        for dia in dias:
            est = registros.get(alumno_id, {}).get(dia, "NINGUNO")
            if est == "EXITO":
                txt = "<font color='#2E7D32'><b>LOGRADO</b></font>"
                exitos_alumno += 1
                totales_exito_clase += 1
            elif est == "NO_TRAIDO":
                txt = "<font color='#C62828'><b>NO TRAÍDO</b></font>"
            else:
                txt = "<font color='#9E9E9E'>-</font>"
            row.append(Paragraph(txt, cell_text_style))

        pct = f"{exitos_alumno}/{len(dias)} ({int(exitos_alumno/len(dias)*100)}%)"
        row.append(Paragraph(f"<b>{pct}</b>", cell_text_style))
        table_data.append(row)

    col_widths = [160] + [100] * 5 + [120]
    t_registro = Table(table_data, colWidths=col_widths)
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E88E5")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0BEC5")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F5F5")))

    t_registro.setStyle(TableStyle(t_style))
    elements.append(t_registro)

    elements.append(Spacer(1, 15))
    resumen_text = f"<b>Resumen del periodo:</b> Se han alcanzado un total de <b>{totales_exito_clase}</b> desayunos saludables en la clase."
    elements.append(Paragraph(resumen_text, ParagraphStyle("Res", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#333333"))))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.set_page_config(page_title="¡Desayunos Saludables! 🍎", page_icon="🍌", layout="wide")

db = DesayunosSupabase()
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🌟 CAMPEONATO DE DESAYUNOS SALUDABLES 🌟</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px; color: #555;'>3º de Educación Primaria - ¡Cuidamos nuestra salud comiendo sano!</p>", unsafe_allow_html=True)
st.divider()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Panel de Control")

    # Exportación PDF
    st.subheader("🖨️ Exportar Registro PDF")
    col_f1, col_f2 = st.columns(2)
    fecha_inicio_pdf = col_f1.date_input("Desde:", value=date.today())
    fecha_fin_pdf = col_f2.date_input("Hasta:", value=date.today())

    pdf_bytes = generar_pdf_bytes(db, dias, fecha_inicio_pdf, fecha_fin_pdf)
    if pdf_bytes:
        st.download_button(
            label="📥 Descargar PDF",
            data=pdf_bytes,
            file_name=f"Registro_Desayunos_{fecha_inicio_pdf.strftime('%d%m')}_al_{fecha_fin_pdf.strftime('%d%m')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    # Edición del Menú
    st.subheader("📋 Configurar Menú")
    menu_actual = db.obtener_menu()
    nuevo_menu = {}
    with st.form("form_menu"):
        for dia in dias:
            nuevo_menu[dia] = st.text_input(f"Día {dia}", value=menu_actual.get(dia, ""))
        btn_actualizar_menu = st.form_submit_button("💾 Actualizar Menú")
        if btn_actualizar_menu:
            db.actualizar_menu(nuevo_menu)
            st.success("¡Menú guardado!")
            st.rerun()

    st.divider()

    # Gestión de Alumnado
    st.subheader("👦👧 Alumnado de Clase")
    nuevo_alumno = st.text_input("Nombre del nuevo alumno/a:")
    if st.button("➕ Añadir a Clase", use_container_width=True):
        if nuevo_alumno.strip():
            if db.agregar_alumno(nuevo_alumno.strip()):
                st.success(f"¡{nuevo_alumno} registrado/a!")
                st.rerun()
            else:
                st.warning("No se pudo añadir (es posible que ya exista).")

    st.write("---")
    alumnos_lista = db.obtener_alumnos()
    if alumnos_lista:
        opciones_eliminar = {nombre: aid for aid, nombre in alumnos_lista}
        alumno_a_borrar = st.selectbox("Eliminar alumno:", list(opciones_eliminar.keys()))
        if st.button("🗑️ Eliminar de la Lista", use_container_width=True):
            db.eliminar_alumno(opciones_eliminar[alumno_a_borrar])
            st.success(f"Alumno {alumno_a_borrar} eliminado.")
            st.rerun()

    st.divider()

    # Reseteo
    st.subheader("⚠️ Zona de Reinicio")
    with st.expander("Resetear registros"):
        st.warning("Borra las marcas semanales para iniciar un nuevo torneo.")
        if st.button("🔥 Reiniciar Marcadores", type="primary", use_container_width=True):
            db.resetear_registros()
            st.success("¡Marcadores reiniciados!")
            st.rerun()


# --- PANEL PRINCIPAL CON PESTAÑAS ---
tab1, tab2 = st.tabs(["📊 Registro Diario y Menú", "🏆 Podio de Super Desayunadores"])

alumnos = db.obtener_alumnos()
registros = db.obtener_registros()
menu_semanal = db.obtener_menu()

# PESTAÑA 1: REGISTRO DIARIO
with tab1:
    total_desayunos_logrados = 0
    total_posibles = len(alumnos) * len(dias) if alumnos else 1

    for aid, _ in alumnos:
        for dia in dias:
            if registros.get(aid, {}).get(dia) == "EXITO":
                total_desayunos_logrados += 1

    porcentaje_exito = int((total_desayunos_logrados / total_posibles) * 100)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🏆 Desayunos Saludables Conseguidos", f"{total_desayunos_logrados} ⭐", delta=f"{porcentaje_exito}% de la clase")
    col_m2.metric("👦👧 Alumnos Registrados", len(alumnos))
    col_m3.metric("📅 Día Activo", f"{dias[datetime.now().weekday() if datetime.now().weekday() < 5 else 0]}")

    st.write("")
    st.subheader("📋 Menú Establecido para esta Semana")
    cols_menu = st.columns(5)
    for i, dia in enumerate(dias):
        with cols_menu[i]:
            st.info(f"**{dia}**\n\n{menu_semanal.get(dia, '-')}")

    st.divider()
    st.subheader("📊 Control Semanal del Alumnado")

    if not alumnos:
        st.info("No hay alumnos registrados. Puedes añadir a tus alumnos desde el panel lateral izquierdo en '👦👧 Alumnado de Clase'.")
    else:
        cols_header = st.columns([2, 2, 2, 2, 2, 2])
        cols_header[0].markdown("**Alumno / a**")
        for j, dia in enumerate(dias):
            cols_header[j + 1].markdown(f"**{dia}**")

        st.write("---")

        opciones_estado = ["➖ Sin marcar", "⭐ ¡Logrado!", "❌ No traído"]
        mapa_estado = {"NINGUNO": "➖ Sin marcar", "EXITO": "⭐ ¡Logrado!", "NO_TRAIDO": "❌ No traído"}
        mapa_inverso = {v: k for k, v in mapa_estado.items()}

        consecucion_completa_semana = False

        for alumno_id, nombre in alumnos:
            cols_fila = st.columns([2, 2, 2, 2, 2, 2])
            cols_fila[0].markdown(f"### {nombre}")

            exitos_semana = 0

            for j, dia in enumerate(dias):
                estado_db = registros.get(alumno_id, {}).get(dia, "NINGUNO")
                estado_label = mapa_estado.get(estado_db, "➖ Sin marcar")

                nuevo_label = cols_fila[j + 1].selectbox(
                    label=f"{nombre}_{dia}",
                    options=opciones_estado,
                    index=opciones_estado.index(estado_label),
                    key=f"sel_{alumno_id}_{dia}",
                    label_visibility="collapsed",
                )

                nuevo_estado_db = mapa_inverso[nuevo_label]
                if nuevo_estado_db != estado_db:
                    db.cambiar_estado_registro(alumno_id, dia, nuevo_estado_db)
                    st.rerun()

                if nuevo_estado_db == "EXITO":
                    exitos_semana += 1

            if exitos_semana == len(dias):
                consecucion_completa_semana = True

        if consecucion_completa_semana:
            st.balloons()

        st.divider()

        st.subheader("📈 Progreso Diario de la Clase")
        conteo_dias = {dia: 0 for dia in dias}
        for aid, _ in alumnos:
            for dia in dias:
                if registros.get(aid, {}).get(dia) == "EXITO":
                    conteo_dias[dia] += 1

        df_progreso = pd.DataFrame({
            "Día": list(conteo_dias.keys()),
            "Desayunos Saludables Logrados": list(conteo_dias.values())
        })

        st.bar_chart(df_progreso, x="Día", y="Desayunos Saludables Logrados", color="#4CAF50")


# PESTAÑA 2: RANKING Y PODIO
with tab2:
    st.subheader("🏆 Podio de los Mejores Desayunadores")
    st.caption("¡Recompensamos el esfuerzo y la constancia de comer saludable!")

    if not alumnos:
        st.info("Aún no hay alumnos registrados en la clase. Añádelos en la barra lateral para generar la clasificación.")
    else:
        puntuaciones = []
        for aid, nombre in alumnos:
            puntos = 0
            for dia in dias:
                if registros.get(aid, {}).get(dia) == "EXITO":
                    puntos += 1
            puntuaciones.append({"Alumno": nombre, "Desayunos Saludables ⭐": puntos})

        df_ranking = pd.DataFrame(puntuaciones)

        if "Desayunos Saludables ⭐" in df_ranking.columns and df_ranking["Desayunos Saludables ⭐"].max() > 0:
            df_ranking = df_ranking.sort_values(by="Desayunos Saludables ⭐", ascending=False)
            
            top_alumnos = df_ranking[df_ranking["Desayunos Saludables ⭐"] > 0].head(3).values.tolist()

            col_p1, col_p2, col_p3 = st.columns(3)
            colores = ["#FFF176", "#E0E0E0", "#FFCC80"]
            medallas = ["🥇 1º Puesto (ORO)", "🥈 2º Puesto (PLATA)", "🥉 3º Puesto (BRONCE)"]
            cols_podio = [col_p1, col_p2, col_p3]

            for idx, (nombre, puntos) in enumerate(top_alumnos):
                with cols_podio[idx]:
                    st.markdown(
                        f"""
                        <div style="background-color: {colores[idx]}; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #888;">
                            <h3>{medallas[idx]}</h3>
                            <h2>{nombre}</h2>
                            <p style="font-size: 20px;"><b>{puntos} ⭐ Conseguidos</b></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.write("")
            st.divider()
            st.subheader("📋 Clasificación General de la Clase")
            st.dataframe(df_ranking, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay puntos acumulados en la semana. ¡Empieza a marcar los desayunos en la primera pestaña!")
