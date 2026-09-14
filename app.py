from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Settings
DATABASE = "database.db"
UPLOAD_FOLDER = "uploads"
PAYMENT_FOLDER = "payment_receipts"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PAYMENT_FOLDER"] = PAYMENT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Prices
HOURLY_RATE = 500

LOCATIONS = {
    "11:11": 500,
    "University of Calabar": 300,
    "Marina Resort": 1000
}


# Create / update database
def init_db():

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            customer_photo TEXT NOT NULL,
            location TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            hours INTEGER NOT NULL,
            hourly_cost INTEGER NOT NULL,
            transport_fee INTEGER NOT NULL,
            total_cost INTEGER NOT NULL,
            payment_receipt TEXT,
            payment_status TEXT DEFAULT 'Pending'
        )
    """)

    # Add payment columns if they don't exist
    columns = [
        row[1]
        for row in conn.execute("PRAGMA table_info(bookings)").fetchall()
    ]

    if "payment_receipt" not in columns:
        conn.execute(
            "ALTER TABLE bookings ADD COLUMN payment_receipt TEXT"
        )

    if "payment_status" not in columns:
        conn.execute(
            "ALTER TABLE bookings ADD COLUMN payment_status TEXT DEFAULT 'Pending'"
        )

    conn.commit()
    conn.close()


# Home page
@app.route("/")
def home():
    return render_template(
        "index.html",
        locations=LOCATIONS,
        hourly_rate=HOURLY_RATE
    )


# Booking page
@app.route("/book", methods=["GET", "POST"])
def book():

    if request.method == "POST":

        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        location = request.form.get("location")
        booking_date = request.form.get("booking_date")
        start_time = request.form.get("start_time")
        hours = request.form.get("hours")

        photo = request.files.get("customer_photo")
        payment_receipt = request.files.get("payment_receipt")

        # Check required information
        if not all([
            full_name,
            phone,
            location,
            booking_date,
            start_time,
            hours,
            photo,
            payment_receipt
        ]):
            return "Please complete all fields and upload your payment receipt."

        # Check location
        if location not in LOCATIONS:
            return "Invalid location."

        # Check hours
        try:
            hours = int(hours)
        except ValueError:
            return "Invalid number of hours."

        if hours < 1:
            return "Hours must be at least 1."

        # Allowed image types
        allowed_extensions = {
            "jpg",
            "jpeg",
            "png",
            "webp"
        }

        # -------------------------
        # Customer photo
        # -------------------------

        filename = secure_filename(photo.filename)

        if "." not in filename:
            return "Please upload a valid customer image."

        extension = filename.rsplit(".", 1)[1].lower()

        if extension not in allowed_extensions:
            return "Customer photo must be JPG, JPEG, PNG or WEBP."

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        photo_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        photo.save(photo_path)

        # -------------------------
        # Payment receipt
        # -------------------------

        receipt_filename = secure_filename(
            payment_receipt.filename
        )

        if "." not in receipt_filename:
            return "Please upload a valid payment receipt."

        receipt_extension = receipt_filename.rsplit(".", 1)[1].lower()

        if receipt_extension not in allowed_extensions:
            return "Payment receipt must be JPG, JPEG, PNG or WEBP."

        os.makedirs(PAYMENT_FOLDER, exist_ok=True)

        receipt_path = os.path.join(
            app.config["PAYMENT_FOLDER"],
            receipt_filename
        )

        payment_receipt.save(receipt_path)

        # -------------------------
        # Calculate price
        # -------------------------

        hourly_cost = hours * HOURLY_RATE

        transport_fee = LOCATIONS[location]

        total_cost = hourly_cost + transport_fee

        # -------------------------
        # Save booking
        # -------------------------

        conn = sqlite3.connect(DATABASE)

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO bookings (
                full_name,
                phone,
                customer_photo,
                location,
                booking_date,
                start_time,
                hours,
                hourly_cost,
                transport_fee,
                total_cost,
                payment_receipt,
                payment_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            phone,
            filename,
            location,
            booking_date,
            start_time,
            hours,
            hourly_cost,
            transport_fee,
            total_cost,
            receipt_filename,
            "Pending"
        ))

        booking_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return redirect(
            url_for(
                "success",
                booking_id=booking_id
            )
        )

    return render_template(
        "book.html",
        locations=LOCATIONS,
        hourly_rate=HOURLY_RATE
    )


# Booking status page
@app.route("/success/<int:booking_id>")
def success(booking_id):

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,)
    ).fetchone()

    conn.close()

    if booking is None:
        return "Booking not found."

    return render_template(
        "success.html",
        booking=booking
    )


# Admin page
@app.route("/admin")
def admin():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    bookings = conn.execute(
        "SELECT * FROM bookings ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        bookings=bookings
    )


# Approve payment
@app.route("/admin/approve/<int:booking_id>", methods=["POST"])
def approve_payment(booking_id):

    conn = sqlite3.connect(DATABASE)

    conn.execute(
        """
        UPDATE bookings
        SET payment_status = 'Approved'
        WHERE id = ?
        """,
        (booking_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin"))


# Display uploaded customer photos
@app.route("/uploads/<filename>")
def uploaded_file(filename):

    from flask import send_from_directory

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# Display payment receipts
@app.route("/payment_receipts/<filename>")
def payment_receipt(filename):

    from flask import send_from_directory

    return send_from_directory(
        app.config["PAYMENT_FOLDER"],
        filename
    )


if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )
init_db()

if __name__ == "__main__":

    app.run(
        debug=True
    )
