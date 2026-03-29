from flask import Flask, render_template, request, jsonify, make_response
import sqlite3
import os
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ahpc_escribanias.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as t FROM registros")
    total = cur.fetchone()['t']
    cur.execute("SELECT MIN(CAST(anio AS INTEGER)) as mn, MAX(CAST(anio AS INTEGER)) as mx FROM registros WHERE anio IS NOT NULL AND anio != ''")
    rango = cur.fetchone()
    cur.execute("SELECT COUNT(DISTINCT causa) as t FROM registros WHERE causa IS NOT NULL AND causa != ''")
    tipos = cur.fetchone()['t']
    cur.execute("SELECT serie, COUNT(*) as t FROM registros WHERE serie IS NOT NULL GROUP BY serie ORDER BY serie")
    por_serie = [dict(r) for r in cur.fetchall()]
    conn.close()
    return render_template('index.html',
        total=total, anio_inicio=rango['mn'], anio_fin=rango['mx'],
        tipos=tipos, por_serie=por_serie)

@app.route('/buscar')
def buscar():
    return render_template('buscar.html')

@app.route('/api/buscar')
def api_buscar():
    partes  = request.args.get('partes', '').strip()
    causa   = request.args.get('causa', '').strip()
    serie   = request.args.get('serie', '').strip()
    anio_desde = request.args.get('anio_desde', '').strip()
    anio_hasta = request.args.get('anio_hasta', '').strip()
    legajo  = request.args.get('legajo', '').strip()
    texto   = request.args.get('texto', '').strip()
    page    = int(request.args.get('page', 1))
    per_page = 50
    offset  = (page - 1) * per_page

    if texto:
        sql = """
            SELECT r.id, r.anio, r.serie, r.legajo, r.expediente, r.partes, r.causa
            FROM registros r
            WHERE r.id IN (SELECT rowid FROM registros_fts WHERE registros_fts MATCH ?)
            ORDER BY CAST(r.anio AS INTEGER) ASC
            LIMIT ? OFFSET ?
        """
        count_sql = """SELECT COUNT(*) as t FROM registros r
            WHERE r.id IN (SELECT rowid FROM registros_fts WHERE registros_fts MATCH ?)"""
        rows = query(sql, (texto, per_page, offset))
        count_row = query(count_sql, (texto,))
    else:
        conditions = ["1=1"]
        params = []
        if partes:
            conditions.append("partes LIKE ?")
            params.append(f"%{partes}%")
        if causa:
            conditions.append("causa LIKE ?")
            params.append(f"%{causa}%")
        if serie:
            conditions.append("serie = ?")
            params.append(serie)
        if anio_desde:
            conditions.append("CAST(anio AS INTEGER) >= ?")
            params.append(int(anio_desde))
        if anio_hasta:
            conditions.append("CAST(anio AS INTEGER) <= ?")
            params.append(int(anio_hasta))
        if legajo:
            conditions.append("legajo = ?")
            params.append(legajo)
        where = " AND ".join(conditions)
        sql = f"""SELECT id, anio, serie, legajo, expediente, partes, causa
                  FROM registros WHERE {where}
                  ORDER BY CAST(anio AS INTEGER) ASC LIMIT ? OFFSET ?"""
        count_sql = f"SELECT COUNT(*) as t FROM registros WHERE {where}"
        rows = query(sql, params + [per_page, offset])
        count_row = query(count_sql, params)

    total = count_row[0]['t'] if count_row else 0
    registros = [dict(r) for r in rows]
    return jsonify({'total': total, 'page': page, 'per_page': per_page, 'registros': registros})

@app.route('/detalle/<int:rid>')
def detalle(rid):
    rows = query("SELECT * FROM registros WHERE id = ?", (rid,))
    if not rows:
        return "Registro no encontrado", 404
    return render_template('detalle.html', reg=dict(rows[0]))

@app.route('/estadisticas')
def estadisticas():
    conn = get_db()
    cur = conn.cursor()

    # Por siglo
    cur.execute("""
        SELECT (CAST(anio AS INTEGER) / 100 * 100) as siglo,
               COUNT(*) as total
        FROM registros WHERE anio IS NOT NULL AND CAST(anio AS INTEGER) > 0
        GROUP BY siglo ORDER BY siglo
    """)
    por_siglo = [dict(r) for r in cur.fetchall()]

    # Por decada
    cur.execute("""
        SELECT (CAST(anio AS INTEGER) / 10 * 10) as decada, COUNT(*) as total
        FROM registros WHERE anio IS NOT NULL AND CAST(anio AS INTEGER) > 0
        GROUP BY decada ORDER BY decada
    """)
    por_decada = [dict(r) for r in cur.fetchall()]

    # Por serie
    cur.execute("""
        SELECT serie, COUNT(*) as total FROM registros
        WHERE serie IS NOT NULL AND serie != ''
        GROUP BY serie ORDER BY serie
    """)
    por_serie = [dict(r) for r in cur.fetchall()]

    # Top causas
    cur.execute("""
        SELECT causa, COUNT(*) as total FROM registros
        WHERE causa IS NOT NULL AND causa != ''
        GROUP BY causa ORDER BY total DESC LIMIT 25
    """)
    top_causas = [dict(r) for r in cur.fetchall()]

    # Top partes
    cur.execute("""
        SELECT partes, COUNT(*) as total FROM registros
        WHERE partes IS NOT NULL AND partes != ''
        GROUP BY partes ORDER BY total DESC LIMIT 20
    """)
    top_partes = [dict(r) for r in cur.fetchall()]

    conn.close()
    return render_template('estadisticas.html',
        por_siglo=por_siglo, por_decada=por_decada,
        por_serie=por_serie, top_causas=top_causas, top_partes=top_partes)

@app.route('/api/exportar-pdf')
def exportar_pdf():
    partes  = request.args.get('partes', '').strip()
    causa   = request.args.get('causa', '').strip()
    serie   = request.args.get('serie', '').strip()
    anio_desde = request.args.get('anio_desde', '').strip()
    anio_hasta = request.args.get('anio_hasta', '').strip()
    texto   = request.args.get('texto', '').strip()

    if texto:
        sql = """SELECT id, anio, serie, legajo, expediente, partes, causa FROM registros
                 WHERE id IN (SELECT rowid FROM registros_fts WHERE registros_fts MATCH ?)
                 ORDER BY CAST(anio AS INTEGER) ASC LIMIT 500"""
        rows = query(sql, (texto,))
    else:
        conditions = ["1=1"]; params = []
        if partes:  conditions.append("partes LIKE ?");  params.append(f"%{partes}%")
        if causa:   conditions.append("causa LIKE ?");   params.append(f"%{causa}%")
        if serie:   conditions.append("serie = ?");      params.append(serie)
        if anio_desde: conditions.append("CAST(anio AS INTEGER) >= ?"); params.append(int(anio_desde))
        if anio_hasta: conditions.append("CAST(anio AS INTEGER) <= ?"); params.append(int(anio_hasta))
        where = " AND ".join(conditions)
        rows = query(f"""SELECT id, anio, serie, legajo, expediente, partes, causa
                         FROM registros WHERE {where}
                         ORDER BY CAST(anio AS INTEGER) ASC LIMIT 500""", params)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    cell_style  = ParagraphStyle('cell', fontSize=7, leading=9)
    title_style = ParagraphStyle('title', fontSize=13, leading=16, alignment=TA_CENTER, fontName='Helvetica-Bold')
    sub_style   = ParagraphStyle('sub',   fontSize=8,  leading=11, alignment=TA_CENTER)

    elements = [
        Paragraph("ARCHIVO HISTÓRICO DE LA PROVINCIA DE CÓRDOBA", title_style),
        Paragraph("Escribanías Judiciales 1, 2, 3 y 4 — Índice de Expedientes (1574–1882)", sub_style),
        Spacer(1, 0.2*inch),
    ]

    data = [['Año', 'Serie', 'Legajo', 'Expte.', 'Partes', 'Causa']]
    for r in rows:
        data.append([
            str(r['anio'] or ''),
            str(r['serie'] or ''),
            str(r['legajo'] or ''),
            str(r['expediente'] or ''),
            Paragraph(str(r['partes'] or ''), cell_style),
            Paragraph(str(r['causa'] or ''), cell_style),
        ])

    t = Table(data, colWidths=[35, 65, 38, 35, 185, 197])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c1a0e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#d4a853')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (4,1), (5,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fdf6e3')]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t)
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    resp = make_response(pdf)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'inline; filename=ahpc_escribanias.pdf'
    return resp

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
