from flask import Flask, render_template, request, redirect, Response
from flask_mysqldb import MySQL
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from config import Config
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

@app.route("/")
def home():
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM water_usage")
    total_records = cur.fetchone()["total"]

    cur.execute("SELECT IFNULL(SUM(liters_used),0) AS liters FROM water_usage")
    total_liters = cur.fetchone()["liters"]

    cur.execute("SELECT COUNT(*) AS today FROM water_usage WHERE usage_date=CURDATE()")
    today_records = cur.fetchone()["today"]

    cur.execute("SELECT IFNULL(AVG(liters_used),0) AS average_usage FROM water_usage")
    average_usage = round(cur.fetchone()["average_usage"], 2)
    cur.close()

    if average_usage >= 500:
        water_tip = "⚠️ Water usage is high. Try reducing unnecessary consumption."
    elif average_usage >= 250:
        water_tip = "💧 Your water usage is moderate. Keep monitoring regularly."
    else:
        water_tip = "🌱 Great job! Your water usage is efficient. Keep it up!"

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT username,SUM(liters_used) AS total
        FROM water_usage
        GROUP BY username
        ORDER BY username
    """)
    chart_data = cur.fetchall()
    labels = [r["username"] for r in chart_data]
    values = [r["total"] for r in chart_data]

    cur.execute("""
        SELECT purpose,SUM(liters_used) AS total
        FROM water_usage
        GROUP BY purpose
        ORDER BY purpose
    """)
    purpose_data = cur.fetchall()
    purpose_labels = [r["purpose"] for r in purpose_data]
    purpose_values = [r["total"] for r in purpose_data]

    cur.execute("""
        SELECT username,SUM(liters_used) AS total_usage
        FROM water_usage
        GROUP BY username
        ORDER BY total_usage DESC
        LIMIT 1
    """)
    highest_consumer = cur.fetchone()

    cur.execute("""
        SELECT username,SUM(liters_used) AS total_usage
        FROM water_usage
        GROUP BY username
        ORDER BY total_usage ASC
        LIMIT 1
    """)
    lowest_consumer = cur.fetchone()

    cur.execute("""
        SELECT username,location,liters_used,usage_date
        FROM water_usage
        ORDER BY usage_date DESC,id DESC
        LIMIT 5
    """)
    recent_records = cur.fetchall()
    cur.execute("""
        SELECT IFNULL(SUM(liters_used), 0) AS monthly_usage
        FROM water_usage
        WHERE MONTH(usage_date) = MONTH(CURDATE())
        AND YEAR(usage_date) = YEAR(CURDATE())
    """)

    monthly_usage = cur.fetchone()["monthly_usage"]
    monthly_target = 5000

    progress = min(round((monthly_usage / monthly_target) * 100), 100)
    cur.execute("""
        SELECT username,
                SUM(liters_used) AS total_usage
        FROM water_usage
        GROUP BY username
        ORDER BY total_usage DESC
        LIMIT 5
    """)

    top_consumers = cur.fetchall()
    cur.execute("""
      SELECT COUNT(DISTINCT username) AS total_users
      FROM water_usage
    """)
    total_users = cur.fetchone()["total_users"]

    cur.execute("""
       SELECT COUNT(DISTINCT location) AS total_locations
       FROM water_usage
    """)
    total_locations = cur.fetchone()["total_locations"]

    cur.execute("""
       SELECT COUNT(DISTINCT purpose) AS total_purposes
       FROM water_usage
    """)
    total_purposes = cur.fetchone()["total_purposes"]
    system_status = "🟢 Online"
    generated_time = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    cur.close()

    return render_template(
        "index.html",
        total_records=total_records,
        total_liters=total_liters,
        today_records=today_records,
        average_usage=average_usage,
        labels=labels,
        values=values,
        purpose_labels=purpose_labels,
        purpose_values=purpose_values,
        highest_consumer=highest_consumer,
        lowest_consumer=lowest_consumer,
        water_tip=water_tip,
        recent_records=recent_records,
        monthly_usage=monthly_usage,
        monthly_target=monthly_target,
        progress=progress,
        top_consumers=top_consumers,
        total_users=total_users,
        total_locations=total_locations,
        total_purposes=total_purposes,
        generated_time=generated_time,
        system_status=system_status,

    )



@app.route("/add", methods=["GET", "POST"])
def add_usage():

    if request.method == "POST":

        username = request.form["username"]
        location = request.form["location"]
        usage_date = request.form["usage_date"]
        liters_used = request.form["liters_used"]
        purpose = request.form["purpose"]

        cur = mysql.connection.cursor()

        cur.execute("""
        INSERT INTO water_usage
        (username, location, usage_date, liters_used, purpose)

        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            username,
            location,
            usage_date,
            liters_used,
            purpose
        ))

        mysql.connection.commit()

        cur.close()

        return redirect("/view")

    return render_template("add_usage.html")
@app.route('/view')
def view_usage():

    search = request.args.get("search", "")
    from_date = request.args.get("from_date", "")
    to_date = request.args.get("to_date", "")

    cur = mysql.connection.cursor()

    query = "SELECT * FROM water_usage WHERE 1=1"
    values = []

    # Search Filter
    if search:
        query += """
        AND (
            username LIKE %s
            OR location LIKE %s
            OR purpose LIKE %s
        )
        """
        keyword = "%" + search + "%"
        values.extend([keyword, keyword, keyword])

    # Date Filter
    if from_date and to_date:
        query += " AND usage_date BETWEEN %s AND %s"
        values.extend([from_date, to_date])

    query += " ORDER BY usage_date DESC"

    cur.execute(query, tuple(values))
    data = cur.fetchall()

    cur.close()

    return render_template(
        "view_usage.html",
        data=data,
        search=search,
        from_date=from_date,
        to_date=to_date
    )
@app.route("/edit/<int:id>", methods=["GET","POST"])
def edit_usage(id):

    cur = mysql.connection.cursor()

    if request.method == "POST":

        username = request.form["username"]
        location = request.form["location"]
        usage_date = request.form["usage_date"]
        liters_used = request.form["liters_used"]
        purpose = request.form["purpose"]

        cur.execute("""
        UPDATE water_usage

        SET
        username=%s,
        location=%s,
        usage_date=%s,
        liters_used=%s,
        purpose=%s

        WHERE id=%s
        """,

        (
            username,
            location,
            usage_date,
            liters_used,
            purpose,
            id
        ))

        mysql.connection.commit()

        cur.close()

        return redirect("/view")

    cur.execute("SELECT * FROM water_usage WHERE id=%s",(id,))

    record = cur.fetchone()

    cur.close()

    return render_template(
        "edit_usage.html",
        record=record
    )
@app.route("/export")
def export_csv():

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT username, liters_used, purpose, usage_date
        FROM water_usage
        ORDER BY usage_date DESC
    """)

    data = cursor.fetchall()
    cursor.close()

    csv_data = "Username,Liters Used,Purpose,Usage Date\n"

    for row in data:
        csv_data += (
            f"{row['username']},"
            f"{row['liters_used']},"
            f"{row['purpose']},"
            f"{row['usage_date']}\n"
        )

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=water_usage.csv"
        }
    )
@app.route("/export_pdf")
def export_pdf():

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT username, location, usage_date, liters_used, purpose
        FROM water_usage
        ORDER BY usage_date DESC
    """)

    data = cursor.fetchall()
    cursor.close()

    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer, pagesize=letter)

    table_data = [
        ["Username", "Location", "Date", "Liters", "Purpose"]
    ]

    for row in data:
        table_data.append([
            row["username"],
            row["location"],
            str(row["usage_date"]),
            str(row["liters_used"]),
            row["purpose"]
        ])

    table = Table(table_data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    pdf.build([table])

    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=water_usage_report.pdf"
        }
    )
@app.route("/delete/<int:id>")
def delete_usage(id):

    cur = mysql.connection.cursor()

    cur.execute("DELETE FROM water_usage WHERE id=%s", (id,))

    mysql.connection.commit()

    cur.close()

    return redirect("/view")
 
if __name__ == "__main__":
    app.run(debug=True)