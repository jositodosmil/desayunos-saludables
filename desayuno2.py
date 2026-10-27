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

        if not menu_dict:
            menu_defecto = [
                {"dia": "Lunes", "desayuno": "🥛 Lácteo / 🍎 Fruta"},
                {"dia": "Martes", "desayuno": "🥪 Bocadillo/Sándwich"},
                {"dia": "Miércoles", "desayuno": "🥛 Lácteo / 🍎 Fruta"},
                {"dia": "Jueves", "desayuno": "🥪 Bocadillo/Sándwich"},
                {"dia": "Viernes", "desayuno": "🎉Desayuno Libre 🍇🍌"}
            ]
            try:
                supabase.table("menu").upsert(menu_defecto, on_conflict="dia").execute()
                menu_dict = {item["dia"]: item["desayuno"] for item in menu_defecto}
            except Exception:
                menu_dict = {item["dia"]: item["desayuno"] for item in menu_defecto}

        return menu_dict

    @staticmethod
    def actualizar_menu(menu_dict):
        try:
            datos_upsert = [{"dia": dia, "desayuno": desayuno} for dia, desayuno in menu_dict.items()]
            supabase.table("menu").upsert(datos_upsert, on_conflict="dia").execute()
        except Exception:
            pass

    @staticmethod
    def obtener_alumnos():
        try:
            res = supabase.table("alumnos").select("id, nombre").order("nombre").execute()
            return [(item["id"], item["nombre"]) for item in res.data]
        except Exception:
            return []

    @staticmethod
    def agregar_alumno(nombre):
        try:
            nombre_limpio = nombre.strip()
            res = supabase.table("alumnos").insert({"nombre": nombre_limpio}).execute()
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
                registros[aid][item["dia"]] = {
                    "estado": item.get("estado", "NINGUNO"),
                    "calidad": item.get("calidad", False)
                }
            return registros
        except Exception:
            return {}

    @staticmethod
    def cambiar_estado_registro(alumno_id, dia, nuevo_estado, calidad=False):
        try:
            if nuevo_estado == "NINGUNO":
                supabase.table("registro").delete().eq("alumno_id", alumno_id).eq("dia", dia).execute()
            else:
                supabase.table("registro").upsert({
                    "alumno_id": alumno_id,
                    "dia": dia,
                    "estado": nuevo_estado,
                    "calidad": calidad
                }, on_conflict="alumno_id, dia").execute()
        except Exception:
            pass

    @staticmethod
    def resetear_registros():
        try:
            supabase.table("registro").delete().neq("alumno_id", 0).execute()
        except Exception:
            pass

    @staticmethod
    def archivar_semana_actual(etiqueta_semana, alumnos, registros, dias):
        try:
            datos_historial = []
            for aid, nombre in alumnos:
                dias_cumplidos = 0
                puntos_calidad = 0
                for dia in dias:
                    reg = registros.get(aid, {}).get(dia, {})
                    if reg.get("estado") == "EXITO":
                        dias_cumplidos += 1
                        if reg.get("calidad"):
                            puntos_calidad += 1
                
                if dias_cumplidos > 0:
                    datos_historial.append({
                        "semana_etiqueta": etiqueta_semana,
                        "alumno_nombre": nombre,
                        "dias_cumplidos": dias_cumplidos,
                        "puntos_calidad": puntos_calidad
                    })

            if datos_historial:
                supabase.table("historial_semanas").insert(datos_historial).execute()
            
            # Limpiar tabla de registros para la nueva semana
            DesayunosSupabase.resetear_registros()
            return True
        except Exception:
            return False

    @staticmethod
    def obtener_historial_semanas():
        try:
            res = supabase.table("historial_semanas").select("*").order("fecha_archivado", desc=True).execute()
            return res.data
        except Exception:
            return []


# ==========================================
# GENERADOR DE DIPLOMAS INDIVIDUALES (PDF)
# ==========================================
def generar_diploma_pdf(nombre_alumno, premio_titulo, fecha_str):
    if not HAS_REPORTLAB:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DipTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#1B5E20"),
        alignment=1,
        spaceAfter=15,
    )

    sub_style = ParagraphStyle(
        "DipSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#333333"),
        alignment=1,
        spaceAfter=20,
    )

    name_style = ParagraphStyle(
        "DipName",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        textColor=colors.HexColor("#0D47A1"),
        alignment=1,
        spaceAfter=15,
    )

    text_style = ParagraphStyle(
        "DipText",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#555555"),
        alignment=1,
        spaceAfter=25,
    )

    elements = []
    
    # Tabla como marco decorativo
    contenido_diploma = [
        [Paragraph("🏅 DIPLOMA DE SUPER DESAYUNADOR/A 🏅", title_style)],
        [Paragraph("Se otorga con orgullo y gran alegría este reconocimiento a:", sub_style)],
        [Paragraph(f"<b>{nombre_alumno}</b>", name_style)],
        [Paragraph(f"Por su excelente constancia y esfuerzo comiendo saludable en 3º de Primaria.<br/><b>{premio_titulo}</b>", text_style)],
        [Paragraph(f"Fecha: {fecha_str} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Firma del Tutor/a: _______________________", sub_style)]
    ]

    t_diploma = Table(contenido_diploma, colWidths=[720])
    t_diploma.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F8E9")),
        ("BOX", (0, 0), (-1, -1), 4, colors.HexColor("#2E7D32")),
        ("INNERGRID", (0, 0), (-1, -1), 1, colors.HexColor("#C8E6C9")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 15),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
    ]))

    elements.append(t_diploma)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# GENERADOR DE INFORMES PDF SEMANALES
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

    headers = ["Alumno / a"] + dias + ["Puntuación Total"]
    table_data = [[Paragraph(f"<b>{h}</b>", cell_header_style) for h in headers]]

    alumnos = db.obtener_alumnos()
    registros = db.obtener_registros()
    totales_exito_clase = 0

    for alumno_id, nombre in alumnos:
        row = [Paragraph(f"<b>{nombre}</b>", ParagraphStyle("N", fontName="Helvetica", fontSize=9, alignment=0))]
        puntos_alumno = 0

        for dia in dias:
            reg_dia = registros.get(alumno_id, {}).get(dia, {"estado": "NINGUNO", "calidad": False})
            est = reg_dia.get("estado", "NINGUNO")
            es_calidad = reg_dia.get("calidad", False)

            if est == "EXITO":
                puntos_alumno += 1
                totales_exito_clase += 1
                if es_calidad:
                    puntos_alumno += 1
                    txt = "<font color='#2E7D32'><b>LOGRADO ⭐ (+1 🥇)</b></font>"
                else:
                    txt = "<font color='#2E7D32'><b>LOGRADO ⭐</b></font>"
            elif est == "NO_TRAIDO":
                txt = "<font color='#C62828'><b>NO TRAÍDO</b></font>"
            else:
                txt = "<font color='#9E9E9E'>-</font>"
            row.append(Paragraph(txt, cell_text_style))

        row.append(Paragraph(f"<b>{puntos_alumno} Pts</b>", cell_text_style))
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

alumnos = db.obtener_alumnos()
registros = db.obtener_registros()
menu_semanal = db.obtener_menu()

# --- BARRA DE PROGRESO COOPERATIVA / RETO DE CLASE ---
total_puntos_clase = 0
for aid, _ in alumnos:
    for dia in dias:
        reg = registros.get(aid, {}).get(dia, {})
        if reg.get("estado") == "EXITO":
            total_puntos_clase += 1
            if reg.get("calidad"):
                total_puntos_clase += 1

meta_reto = 100
progreso_ratio = min(total_puntos_clase / meta_reto, 1.0)

st.subheader("🎯 Reto Cooperativo de Clase: ¡Alcanzar 100 Puntos Saludables!")
st.progress(progreso_ratio)
col_r1, col_r2 = st.columns([3, 1])
col_r1.write(f"🌟 **Puntos colectivos acumulados esta semana:** `{total_puntos_clase} / {meta_reto}`")
if total_puntos_clase >= meta_reto:
    col_r2.success("🎉 ¡RETO COMPLETO!")
    st.balloons()
st.divider()


# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Panel de Control")

    # Diplomas Semanales
    st.subheader("🏅 Generar Diploma Semanal")
    if alumnos:
        nombres_alumnos = [nombre for _, nombre in alumnos]
        alumno_diploma = st.selectbox("Seleccionar alumno/a:", nombres_alumnos)
        mencion_diploma = st.text_input("Premio / Mención:", value="¡Campeón/a de los Desayunos Saludables!")
        
        pdf_dip = generar_diploma_pdf(alumno_diploma, mencion_diploma, date.today().strftime('%d/%m/%Y'))
        if pdf_dip:
            st.download_button(
                label=f"🎓 Descargar Diploma de {alumno_diploma}",
                data=pdf_dip,
                file_name=f"Diploma_{alumno_diploma.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    st.divider()

    # Archivador de Semanas
    st.subheader("📁 Archivar Semana Actual")
    with st.expander("Archivar y limpiar"):
        etiqueta_sem = st.text_input("Nombre de la semana:", value=f"Semana del {date.today().strftime('%d/%m')}")
        if st.button("📁 Guardar en Historial y Limpiar", use_container_width=True):
            if db.archivar_semana_actual(etiqueta_sem, alumnos, registros, dias):
                st.success("¡Semana archivada con éxito!")
                st.rerun()
            else:
                st.error("No se pudo archivar la semana.")

    st.divider()

    # Exportación PDF Registro
    st.subheader("🖨️ Exportar Registro PDF")
    col_f1, col_f2 = st.columns(2)
    fecha_inicio_pdf = col_f1.date_input("Desde:", value=date.today())
    fecha_fin_pdf = col_f2.date_input("Hasta:", value=date.today())

    pdf_bytes = generar_pdf_bytes(db, dias, fecha_inicio_pdf, fecha_fin_pdf)
    if pdf_bytes:
        st.download_button(
            label="📥 Descargar Registro PDF",
            data=pdf_bytes,
            file_name=f"Registro_Desayunos_{fecha_inicio_pdf.strftime('%d%m')}_al_{fecha_fin_pdf.strftime('%d%m')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    # Edición del Menú
    st.subheader("📋 Configurar Menú")
    nuevo_menu = {}
    with st.form("form_menu"):
        for dia in dias:
            nuevo_menu[dia] = st.text_input(f"Día {dia}", value=menu_semanal.get(dia, ""))
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

    st.write("---")
    if alumnos:
        opciones_eliminar = {nombre: aid for aid, nombre in alumnos}
        alumno_a_borrar = st.selectbox("Eliminar alumno:", list(opciones_eliminar.keys()))
        if st.button("🗑️ Eliminar de la Lista", use_container_width=True):
            db.eliminar_alumno(opciones_eliminar[alumno_a_borrar])
            st.success(f"Alumno {alumno_a_borrar} eliminado.")
            st.rerun()


# --- PANEL PRINCIPAL CON 3 PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["📊 Registro Diario y Menú", "🏆 Podio y Clasificación", "🗄️ Historial de Semanas"])

# PESTAÑA 1: REGISTRO DIARIO
with tab1:
    total_desayunos_logrados = 0
    total_puntos_calidad = 0
    total_posibles = len(alumnos) * len(dias) if alumnos else 1

    for aid, _ in alumnos:
        for dia in dias:
            reg_dia = registros.get(aid, {}).get(dia, {"estado": "NINGUNO", "calidad": False})
            if reg_dia.get("estado") == "EXITO":
                total_desayunos_logrados += 1
                if reg_dia.get("calidad"):
                    total_puntos_calidad += 1

    porcentaje_exito = int((total_desayunos_logrados / total_posibles) * 100)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("🏆 Desayunos Cumplidos", f"{total_desayunos_logrados} ⭐", delta=f"{porcentaje_exito}% de la clase")
    col_m2.metric("🥇 Puntos Extra Calidad Top", f"{total_puntos_calidad} 🌟", delta="Desempate nutricional")
    col_m3.metric("📅 Día Activo", f"{dias[datetime.now().weekday() if datetime.now().weekday() < 5 else 0]}")

    st.write("")
    
    with st.expander("💡 ¿Cómo otorgar el Punto de Calidad Nutricional (+1 🥇)?"):
        st.markdown("""
        * **🥛 Día de Lácteos:** Otorgar **+1 🥇** si trae yogur natural/griego sin azúcar o leche en lugar de batidos o lácteos azucarados.
        * **🍎 Día de Fruta:** Otorgar **+1 🥇** si trae fruta fresca entera de temporada en lugar de zumos o fruta procesada.
        * **🥪 Día de Bocadillo:** Otorgar **+1 🥇** si trae pan integral con ingredientes saludables (aceite, tomate, queso, atún) en lugar de pan de molde blanco o embutidos.
        """)

    st.subheader("📋 Menú Establecido para esta Semana")
    cols_menu = st.columns(5)
    for i, dia in enumerate(dias):
        with cols_menu[i]:
            st.info(f"**{dia}**\n\n{menu_semanal.get(dia, '-')}")

    st.divider()
    st.subheader("📊 Control Semanal del Alumnado")

    if not alumnos:
        st.info("No hay alumnos registrados. Puedes añadir a tus alumnos desde el panel lateral izquierdo.")
    else:
        cols_header = st.columns([2, 2, 2, 2, 2, 2])
        cols_header[0].markdown("**Alumno / a**")
        for j, dia in enumerate(dias):
            cols_header[j + 1].markdown(f"**{dia}**")

        st.write("---")

        opciones_estado = ["➖ Sin marcar", "⭐ ¡Logrado!", "❌ No traído"]
        mapa_estado = {"NINGUNO": "➖ Sin marcar", "EXITO": "⭐ ¡Logrado!", "NO_TRAIDO": "❌ No traído"}
        mapa_inverso = {v: k for k, v in mapa_estado.items()}

        for alumno_id, nombre in alumnos:
            cols_fila = st.columns([2, 2, 2, 2, 2, 2])
            cols_fila[0].markdown(f"### {nombre}")

            for j, dia in enumerate(dias):
                reg_dia = registros.get(alumno_id, {}).get(dia, {"estado": "NINGUNO", "calidad": False})
                estado_db = reg_dia.get("estado", "NINGUNO")
                calidad_db = reg_dia.get("calidad", False)
                estado_label = mapa_estado.get(estado_db, "➖ Sin marcar")

                col_celda = cols_fila[j + 1]
                
                nuevo_label = col_celda.selectbox(
                    label=f"{nombre}_{dia}",
                    options=opciones_estado,
                    index=opciones_estado.index(estado_label),
                    key=f"sel_{alumno_id}_{dia}",
                    label_visibility="collapsed",
                )

                nuevo_estado_db = mapa_inverso[nuevo_label]

                nueva_calidad = calidad_db
                if nuevo_estado_db == "EXITO":
                    nueva_calidad = col_celda.checkbox(
                        "🥇 +1 Calidad",
                        value=calidad_db,
                        key=f"cal_{alumno_id}_{dia}"
                    )

                if nuevo_estado_db != estado_db or nueva_calidad != calidad_db:
                    db.cambiar_estado_registro(alumno_id, dia, nuevo_estado_db, nueva_calidad)
                    st.rerun()

        st.divider()

        # Gráfico de Progreso
        st.subheader("📈 Progreso Diario de la Clase")
        conteo_dias = {dia: 0 for dia in dias}
        for aid, _ in alumnos:
            for dia in dias:
                reg = registros.get(aid, {}).get(dia, {})
                if reg.get("estado") == "EXITO":
                    conteo_dias[dia] += 1

        df_progreso = pd.DataFrame({
            "Día": list(conteo_dias.keys()),
            "Desayunos Saludables Logrados": list(conteo_dias.values())
        })

        df_progreso["Día"] = pd.Categorical(df_progreso["Día"], categories=dias, ordered=True)
        df_progreso = df_progreso.sort_values("Día")

        st.bar_chart(df_progreso, x="Día", y="Desayunos Saludables Logrados", color="#4CAF50")


# PESTAÑA 2: RANKING Y PODIO
with tab2:
    st.subheader("🏆 Podio de los Mejores Desayunadores")
    st.caption("Clasificación por Días Cumplidos (⭐) y Puntos de Calidad Nutricional (🥇)")

    if not alumnos:
        st.info("Aún no hay alumnos registrados en la clase.")
    else:
        puntuaciones = []
        for aid, nombre in alumnos:
            dias_cumplidos = 0
            puntos_calidad = 0
            for dia in dias:
                reg = registros.get(aid, {}).get(dia, {})
                if reg.get("estado") == "EXITO":
                    dias_cumplidos += 1
                    if reg.get("calidad"):
                        puntos_calidad += 1
            
            puntuacion_total = dias_cumplidos + puntos_calidad
            puntuaciones.append({
                "Alumno": nombre,
                "Días Cumplidos ⭐": dias_cumplidos,
                "Puntos Calidad 🥇": puntos_calidad,
                "Puntuación Total 🏆": puntuacion_total
            })

        df_ranking = pd.DataFrame(puntuaciones)

        if "Puntuación Total 🏆" in df_ranking.columns and df_ranking["Puntuación Total 🏆"].max() > 0:
            df_ranking = df_ranking.sort_values(by=["Puntuación Total 🏆", "Puntos Calidad 🥇"], ascending=[False, False])
            
            top_alumnos = df_ranking[df_ranking["Puntuación Total 🏆"] > 0].head(3).values.tolist()

            col_p1, col_p2, col_p3 = st.columns(3)
            colores = ["#FFF176", "#E0E0E0", "#FFCC80"]
            medallas = ["🥇 1º Puesto (ORO)", "🥈 2º Puesto (PLATA)", "🥉 3º Puesto (BRONCE)"]
            cols_podio = [col_p1, col_p2, col_p3]

            for idx, item in enumerate(top_alumnos):
                nombre = item[0]
                d_cumplidos = item[1]
                p_calidad = item[2]
                p_total = item[3]

                with cols_podio[idx]:
                    st.markdown(
                        f"""
                        <div style="background-color: {colores[idx]}; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid #888;">
                            <h3>{medallas[idx]}</h3>
                            <h2>{nombre}</h2>
                            <p style="font-size: 18px; margin-bottom: 2px;"><b>{p_total} Puntos Totales</b></p>
                            <p style="font-size: 14px; color: #444;">({d_cumplidos} ⭐ Días + {p_calidad} 🥇 Extra)</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.write("")
            st.divider()
            st.subheader("📋 Clasificación General de la Clase")
            st.dataframe(df_ranking, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay puntos acumulados en la semana.")


# PESTAÑA 3: HISTORIAL DE SEMANAS ARCHIVADAS
with tab3:
    st.subheader("🗄️ Historial de Semanas Pasadas")
    st.caption("Consulta los resultados guardados en semanas anteriores.")

    historial_data = db.obtener_historial_semanas()
    if historial_data:
        df_historial = pd.DataFrame(historial_data)
        
        # Filtro por semana
        semanas_unicas = df_historial["semana_etiqueta"].unique()
        semana_sel = st.selectbox("Seleccionar Semana Archivada:", semanas_unicas)

        df_filtro = df_historial[df_historial["semana_etiqueta"] == semana_sel][["alumno_nombre", "dias_cumplidos", "puntos_calidad"]]
        df_filtro.columns = ["Alumno", "Días Cumplidos ⭐", "Puntos Calidad 🥇"]
        df_filtro["Puntuación Total 🏆"] = df_filtro["Días Cumplidos ⭐"] + df_filtro["Puntos Calidad 🥇"]
        df_filtro = df_filtro.sort_values(by="Puntuación Total 🏆", ascending=False)

        st.dataframe(df_filtro, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay semanas archivadas en el historial. Puedes archivar la semana actual desde la barra lateral.")
