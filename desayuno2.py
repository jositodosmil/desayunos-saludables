from datetime import datetime
import io
import os
import sqlite3
import pandas as pd
import streamlit as st

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
# GESTIÓN DE LA BASE DE DATOS (SQLITE)
# ==========================================
class DesayunosDB:

    def __init__(self, db_name="desayunos_saludables.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alumnos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT UNIQUE NOT NULL
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS menu (
                    dia TEXT PRIMARY KEY,
                    desayuno TEXT NOT NULL
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS registro (
                    alumno_id INTEGER,
                    dia TEXT,
                    estado TEXT NOT NULL,
                    PRIMARY KEY (alumno_id, dia),
                    FOREIGN KEY (alumno_id) REFERENCES alumnos(id) ON DELETE CASCADE
                )
            """
            )

            # Cargar o actualizar el menú escolar establecido
            menu_establecido = [
                ("Lunes", "🥛/🍎 Lácteos y/o fruta"),
                ("Martes", "🥪 Bocadillo o sándwich"),
                ("Miércoles", "🥛/🍎 Lácteos y/o fruta"),
                ("Jueves", "🥪 Bocadillo o sándwich"),
                ("Viernes", "🎉 Libre"),
            ]
            cursor.executemany(
                "REPLACE INTO menu (dia, desayuno) VALUES (?, ?)",
                menu_establecido,
            )

            # Alumnos por defecto si la tabla está vacía
            cursor.execute("SELECT COUNT(*) FROM alumnos")
            if cursor.fetchone()[0] == 0:
                alumnos_defecto = [
                    ("Lucía",),
                    ("Mateo",),
                    ("Sofía",),
                    ("Hugo",),
                    ("Emma",),
                ]
                cursor.executemany(
                    "INSERT INTO alumnos (nombre) VALUES (?)", alumnos_defecto
                )

            conn.commit()

    def obtener_menu(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT dia, desayuno FROM menu")
            return dict(cursor.fetchall())

    def actualizar_menu(self, menu_dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for dia, desayuno in menu_dict.items():
                cursor.execute(
                    "REPLACE INTO menu (dia, desayuno) VALUES (?, ?)",
                    (dia, desayuno),
                )
            conn.commit()

    def obtener_alumnos(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre FROM alumnos ORDER BY nombre ASC")
            return cursor.fetchall()

    def agregar_alumno(self, nombre):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO alumnos (nombre) VALUES (?)", (nombre,)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def eliminar_alumno(self, alumno_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM alumnos WHERE id = ?", (alumno_id,))
            cursor.execute(
                "DELETE FROM registro WHERE alumno_id = ?", (alumno_id,)
            )
            conn.commit()

    def obtener_registros(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alumno_id, dia, estado FROM registro")
            registros = {}
            for alumno_id, dia, estado in cursor.fetchall():
                if alumno_id not in registros:
                    registros[alumno_id] = {}
                registros[alumno_id][dia] = estado
            return registros

    def cambiar_estado_registro(self, alumno_id, dia, nuevo_estado):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if nuevo_estado == "NINGUNO":
                cursor.execute(
                    "DELETE FROM registro WHERE alumno_id = ? AND dia = ?",
                    (alumno_id, dia),
                )
            else:
                cursor.execute(
                    "REPLACE INTO registro (alumno_id, dia, estado) VALUES (?, ?, ?)",
                    (alumno_id, dia, nuevo_estado),
                )
            conn.commit()


# ==========================================
# GENERADOR DE INFORMES PDF (REPORTLAB)
# ==========================================
def generar_pdf_bytes(db, dias):
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
        spaceAfter=10,
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
    elements.append(
        Paragraph("CAMPEONATO DE DESAYUNOS SALUDABLES", title_style)
    )
    fecha_str = datetime.now().strftime("%d/%m/%Y")
    elements.append(
        Paragraph(
            f"Registro de Educación Primaria - Fecha de emisión: {fecha_str}",
            subtitle_style,
        )
    )

    # Menú
    elements.append(Paragraph("Menú Saludable de la Semana", h2_style))
    menu_data = db.obtener_menu()

    menu_table_data = [
        [Paragraph(f"<b>{dia}</b>", cell_header_style) for dia in dias],
        [
            Paragraph(
                menu_data.get(dia, "-"),
                ParagraphStyle(
                    "M", alignment=1, fontSize=9, fontName="Helvetica-Bold"
                ),
            )
            for dia in dias
        ],
    ]

    t_menu = Table(menu_table_data, colWidths=[150] * 5)
    t_menu.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4CAF50")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E8F5E9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A5D6A7")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(t_menu)
    elements.append(Spacer(1, 15))

    # Registro Alumnos
    elements.append(Paragraph("Control de Asistencia y Desayunos", h2_style))
    headers = ["Alumno / a"] + dias + ["Total Consecución"]
    table_data = [
        [Paragraph(f"<b>{h}</b>", cell_header_style) for h in headers]
    ]

    alumnos = db.obtener_alumnos()
    registros = db.obtener_registros()
    totales_exito_clase = 0

    for alumno_id, nombre in alumnos:
        row = [
            Paragraph(
                f"<b>{nombre}</b>",
                ParagraphStyle(
                    "N", fontName="Helvetica", fontSize=9, alignment=0
                ),
            )
        ]
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
            t_style.append(
                ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F5F5"))
            )

    t_registro.setStyle(TableStyle(t_style))
    elements.append(t_registro)

    elements.append(Spacer(1, 15))
    resumen_text = f"<b>Resumen de la semana:</b> Se han alcanzado un total de <b>{totales_exito_clase}</b> desayunos saludables en el grupo."
    elements.append(
        Paragraph(
            resumen_text,
            ParagraphStyle(
                "Res",
                fontName="Helvetica",
                fontSize=10,
                textColor=colors.HexColor("#333333"),
            ),
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# INTERFAZ STREAMLIT
# ==========================================
st.set_page_config(
    page_title="¡Desayunos Saludables! 🍎", page_icon="🍌", layout="wide"
)

# Inicializar Base de Datos
db = DesayunosDB()
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

# --- ENCABEZADO Y TÍTULO ---
st.markdown(
    "<h1 style='text-align: center; color: #2E7D32;'>🌟 CAMPEONATO DE DESAYUNOS SALUDABLES 🌟</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; font-size: 18px; color: #555;'>3º de Educación Primaria - ¡Cuidamos nuestra salud comiendo sano!</p>",
    unsafe_allow_html=True,
)
st.divider()

# --- BARRA LATERAL (CONFIGURACIÓN Y PDF) ---
with st.sidebar:
    st.header("⚙️ Panel de Control")

    # Botón PDF
    st.subheader("🖨️ Informe PDF")
    pdf_bytes = generar_pdf_bytes(db, dias)
    if pdf_bytes:
        st.download_button(
            label="📥 Descargar Registro PDF",
            data=pdf_bytes,
            file_name=f"Registro_Desayunos_{datetime.now().strftime('%Y_%m_%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.divider()

    # Gestión del Menú
    st.subheader("📋 Menú Semanal")
    menu_actual = db.obtener_menu()
    nuevo_menu = {}
    with st.form("form_menu"):
        for dia in dias:
            nuevo_menu[dia] = st.text_input(
                f"Día {dia}", value=menu_actual.get(dia, "")
            )
        btn_actualizar_menu = st.form_submit_button("💾 Guardar Menú")
        if btn_actualizar_menu:
            db.actualizar_menu(nuevo_menu)
            st.success("¡Menú actualizado correctamente!")
            st.rerun()

    st.divider()

    # Gestión de Alumnado
    st.subheader("👦👧 Gestión de Alumnos")
    nuevo_alumno = st.text_input("Añadir nuevo/a alumno/a:")
    if st.button("➕ Añadir Alumno", use_container_width=True):
        if nuevo_alumno.strip():
            if db.agregar_alumno(nuevo_alumno.strip()):
                st.success(f"¡{nuevo_alumno} añadido/a!")
                st.rerun()
            else:
                st.warning("Ya existe un alumno con ese nombre.")

    st.write("---")
    alumnos_lista = db.obtener_alumnos()
    if alumnos_lista:
        opciones_eliminar = {nombre: aid for aid, nombre in alumnos_lista}
        alumno_a_borrar = st.selectbox(
            "Eliminar alumno:", list(opciones_eliminar.keys())
        )
        if st.button("🗑️ Eliminar Seleccionado", use_container_width=True):
            db.eliminar_alumno(opciones_eliminar[alumno_a_borrar])
            st.success(f"Alumno {alumno_a_borrar} eliminado.")
            st.rerun()


# --- PANEL PRINCIPAL DE METRICAS Y PROGRESO ---
alumnos = db.obtener_alumnos()
registros = db.obtener_registros()
menu_semanal = db.obtener_menu()

total_desayunos_logrados = 0
total_posibles = len(alumnos) * len(dias) if alumnos else 1

for aid, _ in alumnos:
    for dia in dias:
        if registros.get(aid, {}).get(dia) == "EXITO":
            total_desayunos_logrados += 1

porcentaje_exito = int((total_desayunos_logrados / total_posibles) * 100)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric(
    "🏆 Total Desayunos Saludables",
    f"{total_desayunos_logrados} ⭐",
    delta=f"{porcentaje_exito}% de la clase",
)
col_m2.metric("👦👧 Alumnos Registrados", len(alumnos))
col_m3.metric(
    "📅 Día Activo",
    f"{dias[datetime.now().weekday() if datetime.now().weekday() < 5 else 0]}",
)

st.write("")

# --- VISUALIZACIÓN DEL MENÚ ACTUAL ---
st.subheader("📋 Menú Establecido para esta Semana")
cols_menu = st.columns(5)
for i, dia in enumerate(dias):
    with cols_menu[i]:
        st.info(f"**{dia}**\n\n{menu_semanal.get(dia, '-')}")

st.divider()

# --- TABLA INTERACTIVA DE REGISTRO ---
st.subheader("📊 Registro de Desayunos del Alumnado")
st.caption(
    "Selecciona en cada casilla si el alumno/a ha traído el desayuno establecido:"
)

if not alumnos:
    st.info(
        "No hay alumnos registrados. Añade alumnos en el menú lateral para empezar."
    )
else:
    # Encabezados de la Tabla
    cols_header = st.columns([2, 2, 2, 2, 2, 2])
    cols_header[0].markdown("**Alumno / a**")
    for j, dia in enumerate(dias):
        cols_header[j + 1].markdown(f"**{dia}**")

    st.write("---")

    opciones_estado = ["➖ Sin marcar", "⭐ ¡Logrado!", "❌ No traído"]
    mapa_estado = {
        "NINGUNO": "➖ Sin marcar",
        "EXITO": "⭐ ¡Logrado!",
        "NO_TRAIDO": "❌ No traído",
    }
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

    # Fiesta de celebración de globos si algún alumno completa los 5 días
    if consecucion_completa_semana:
        st.balloons()

    st.divider()

    # --- GRÁFICO DE PROGRESO DE LA CLASE ---
    st.subheader("📈 Progreso Diario de la Clase")

    conteo_dias = {dia: 0 for dia in dias}
    for aid, _ in alumnos:
        for dia in dias:
            if registros.get(aid, {}).get(dia) == "EXITO":
                conteo_dias[dia] += 1

    df_progreso = pd.DataFrame(
        {
            "Día": list(conteo_dias.keys()),
            "Desayunos Saludables Logrados": list(conteo_dias.values()),
        }
    )

    st.bar_chart(
        df_progreso,
        x="Día",
        y="Desayunos Saludables Logrados",
        color="#4CAF50",
    )