import sqlite3
import io
from flask import Flask, request, redirect, url_for, render_template_string, send_file, abort
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
DB_NAME = "payroll.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                base_salary REAL NOT NULL,
                allowances REAL DEFAULT 0,
                deductions REAL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payroll_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                month TEXT,
                gross_pay REAL,
                total_deductions REAL,
                net_pay REAL,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        ''')
        conn.commit()

init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Local Payroll System</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background-color: #f4f6f8; }
        .container { max-width: 950px; margin: auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h2, h3 { color: #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f0f2f5; }
        form { margin-bottom: 25px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
        input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        button { grid-column: span 2; padding: 10px; background-color: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        button:hover { background-color: #004c99; }
        .btn-run { background-color: #28a745; padding: 4px 8px; color: white; text-decoration: none; border-radius: 4px; font-size: 13px; }
        .btn-run:hover { background-color: #1e7e34; }
        .btn-pdf { background-color: #dc3545; padding: 4px 8px; color: white; text-decoration: none; border-radius: 4px; font-size: 13px; }
        .btn-pdf:hover { background-color: #bd2130; }
    </style>
</head>
<body>
<div class="container">
    <h2>Payroll & Employee Management</h2>
    
    <h3>Add New Employee</h3>
    <form action="/add_employee" method="POST">
        <input type="text" name="name" placeholder="Full Name" required>
        <input type="text" name="department" placeholder="Department" required>
        <input type="number" step="0.01" name="base_salary" placeholder="Base Salary" required>
        <input type="number" step="0.01" name="allowances" placeholder="Allowances" required>
        <input type="number" step="0.01" name="deductions" placeholder="Statutory/Tax Deductions" required>
        <button type="submit">Save Employee</button>
    </form>

    <h3>Active Employees</h3>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Base</th>
                <th>Allowances</th>
                <th>Deductions</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for emp in employees %}
            <tr>
                <td>{{ emp[0] }}</td>
                <td>{{ emp[1] }}</td>
                <td>{{ emp[2] }}</td>
                <td>${{ "{:,.2f}".format(emp[3]) }}</td>
                <td>${{ "{:,.2f}".format(emp[4]) }}</td>
                <td>${{ "{:,.2f}".format(emp[5]) }}</td>
                <td><a class="btn-run" href="/process_payroll/{{ emp[0] }}">Run Payroll</a></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <h3 style="margin-top: 40px;">Payroll History & Payslips</h3>
    <table>
        <thead>
            <tr>
                <th>Record ID</th>
                <th>Employee Name</th>
                <th>Month</th>
                <th>Gross Pay</th>
                <th>Deductions</th>
                <th>Net Pay</th>
                <th>Payslip</th>
            </tr>
        </thead>
        <tbody>
            {% for rec in records %}
            <tr>
                <td>{{ rec[0] }}</td>
                <td>{{ rec[1] }}</td>
                <td>{{ rec[2] }}</td>
                <td>${{ "{:,.2f}".format(rec[3]) }}</td>
                <td>${{ "{:,.2f}".format(rec[4]) }}</td>
                <td><strong>${{ "{:,.2f}".format(rec[5]) }}</strong></td>
                <td><a class="btn-pdf" href="/download_payslip/{{ rec[0] }}">PDF Payslip</a></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
</body>
</html>
"""

@app.route("/")
def index():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees")
        employees = cursor.fetchall()
        cursor.execute('''
            SELECT p.id, e.name, p.month, p.gross_pay, p.total_deductions, p.net_pay 
            FROM payroll_records p 
            JOIN employees e ON p.employee_id = e.id
            ORDER BY p.id DESC
        ''')
        records = cursor.fetchall()
    return render_template_string(HTML_TEMPLATE, employees=employees, records=records)

@app.route("/add_employee", methods=["POST"])
def add_employee():
    name = request.form["name"]
    dept = request.form["department"]
    base = float(request.form["base_salary"])
    allowances = float(request.form["allowances"] or 0)
    deductions = float(request.form["deductions"] or 0)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO employees (name, department, base_salary, allowances, deductions) VALUES (?, ?, ?, ?, ?)",
            (name, dept, base, allowances, deductions)
        )
        conn.commit()
    return redirect(url_for("index"))

@app.route("/process_payroll/<int:emp_id>")
def process_payroll(emp_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT base_salary, allowances, deductions FROM employees WHERE id = ?", (emp_id,))
        emp = cursor.fetchone()
        
        if emp:
            base, allowances, deductions = emp
            gross_pay = base + allowances
            net_pay = gross_pay - deductions
            month = "September 2026"

            cursor.execute(
                "INSERT INTO payroll_records (employee_id, month, gross_pay, total_deductions, net_pay) VALUES (?, ?, ?, ?, ?)",
                (emp_id, month, gross_pay, deductions, net_pay)
            )
            conn.commit()
    return redirect(url_for("index"))

@app.route("/download_payslip/<int:record_id>")
def download_payslip(record_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.month, p.gross_pay, p.total_deductions, p.net_pay,
                   e.name, e.department, e.base_salary, e.allowances, e.deductions
            FROM payroll_records p
            JOIN employees e ON p.employee_id = e.id
            WHERE p.id = ?
        ''', (record_id,))
        record = cursor.fetchone()

    if not record:
        abort(404, description="Record not found")

    rec_id, month, gross, total_ded, net, name, dept, base, allowances, deductions = record

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor("#4A5568"),
        alignment=1
    )
    
    story.append(Paragraph("<b>COMPANY PAYSLIP</b>", title_style))
    story.append(Paragraph(f"Period: {month} | Payslip #{rec_id:04d}", subtitle_style))
    story.append(Spacer(1, 20))

    emp_info_data = [
        [Paragraph(f"<b>Employee Name:</b> {name}", styles['Normal']), Paragraph(f"<b>Department:</b> {dept}", styles['Normal'])],
        [Paragraph(f"<b>Pay Date:</b> 01/09/2026", styles['Normal']), Paragraph(f"<b>Currency:</b> USD ($)", styles['Normal'])]
    ]
    emp_table = Table(emp_info_data, colWidths=[260, 260])
    emp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 20))

    breakdown_data = [
        ["Earnings", "Amount", "Deductions", "Amount"],
        ["Base Salary", f"${base:,.2f}", "Statutory / Taxes", f"${deductions:,.2f}"],
        ["Allowances", f"${allowances:,.2f}", "", ""],
        ["Gross Pay", f"${gross:,.2f}", "Total Deductions", f"${total_ded:,.2f}"],
        ["", "", "NET TAKE-HOME", f"${net:,.2f}"]
    ]

    breakdown_table = Table(breakdown_data, colWidths=[160, 100, 160, 100])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0, 3), (1, 3), colors.HexColor("#EDF2F7")),
        ('BACKGROUND', (2, 3), (3, 3), colors.HexColor("#EDF2F7")),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('BACKGROUND', (2, 4), (3, 4), colors.HexColor("#C6F6D5")),
        ('FONTNAME', (2, 4), (3, 4), 'Helvetica-Bold'),
        ('GRID', (2, 4), (3, 4), 1, colors.HexColor("#38A169")),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(breakdown_table)

    doc.build(story)
    buffer.seek(0)

    filename = f"Payslip_{name.replace(' ', '_')}_{month.replace(' ', '_')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)