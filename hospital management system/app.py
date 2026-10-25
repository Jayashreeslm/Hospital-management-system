"""
app.py — Flask application for Hospital Management System.
Team 15 DBMS Capstone Project.
"""

import os
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hospital-mgmt-team15-secret-key-2026')
app.config['WTF_CSRF_ENABLED'] = True


# ── Helpers ─────────────────────────────────────────────────────────────

def login_required(f):
    """Decorator to protect routes that need authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_connection():
    """Get or create a database connection for the current request."""
    if 'db' not in g:
        g.db = get_db()
    return g.db


@app.teardown_appcontext
def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Auth Routes ─────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_connection()
        user = db.execute("SELECT * FROM User WHERE Username = ?", (username,)).fetchone()
        if user and check_password_hash(user['Password'], password):
            session['user_id'] = user['User_ID']
            session['username'] = user['Username']
            session['role'] = user['Role']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# ── Dashboard ───────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    db = get_connection()
    today = date.today().isoformat()
    stats = {
        'total_patients': db.execute("SELECT COUNT(*) FROM Patient").fetchone()[0],
        'total_doctors': db.execute("SELECT COUNT(*) FROM Doctor").fetchone()[0],
        'today_appointments': db.execute(
            "SELECT COUNT(*) FROM Appointment WHERE DATE(DateTime) = ?", (today,)
        ).fetchone()[0],
        'completed_appointments': db.execute(
            "SELECT COUNT(*) FROM Appointment WHERE Status = 'Completed'"
        ).fetchone()[0],
    }
    recent_appointments = db.execute("""
        SELECT a.Appointment_ID, p.Name AS patient_name, d.Name AS doctor_name,
               a.DateTime, a.Status
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        ORDER BY a.DateTime DESC LIMIT 5
    """).fetchall()
    recent_patients = db.execute(
        "SELECT * FROM Patient ORDER BY Patient_ID DESC LIMIT 5"
    ).fetchall()
    status_summary = db.execute("""
        SELECT Status, COUNT(*) as cnt FROM Appointment GROUP BY Status
    """).fetchall()
    return render_template('dashboard.html', stats=stats,
                           recent_appointments=recent_appointments,
                           recent_patients=recent_patients,
                           status_summary=status_summary)


# ── Patient Management ──────────────────────────────────────────────────

@app.route('/patients')
@login_required
def patients():
    db = get_connection()
    search = request.args.get('search', '').strip()
    gender_filter = request.args.get('gender', '').strip()
    query = "SELECT * FROM Patient WHERE 1=1"
    params = []
    if search:
        query += " AND (Name LIKE ? OR Phone LIKE ? OR CAST(Patient_ID AS TEXT) LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if gender_filter:
        query += " AND Gender = ?"
        params.append(gender_filter)
    query += " ORDER BY Patient_ID DESC"
    patients_list = db.execute(query, params).fetchall()
    return render_template('patients.html', patients=patients_list,
                           search=search, gender_filter=gender_filter)


@app.route('/patients/add', methods=['POST'])
@login_required
def add_patient():
    name = request.form.get('name', '').strip()
    age = request.form.get('age', '').strip()
    gender = request.form.get('gender', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    if not all([name, age, gender, phone, address]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('patients'))
    try:
        age = int(age)
        if age <= 0 or age >= 150:
            raise ValueError
    except ValueError:
        flash('Age must be a valid number between 1 and 149.', 'danger')
        return redirect(url_for('patients'))
    if gender not in ('Male', 'Female', 'Other'):
        flash('Invalid gender.', 'danger')
        return redirect(url_for('patients'))
    db = get_connection()
    db.execute(
        "INSERT INTO Patient (Name, Age, Gender, Phone, Address) VALUES (?, ?, ?, ?, ?)",
        (name, age, gender, phone, address)
    )
    db.commit()
    flash(f'Patient "{name}" added successfully!', 'success')
    return redirect(url_for('patients'))


@app.route('/patients/edit/<int:patient_id>', methods=['POST'])
@login_required
def edit_patient(patient_id):
    name = request.form.get('name', '').strip()
    age = request.form.get('age', '').strip()
    gender = request.form.get('gender', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    if not all([name, age, gender, phone, address]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('patients'))
    try:
        age = int(age)
        if age <= 0 or age >= 150:
            raise ValueError
    except ValueError:
        flash('Age must be a valid number between 1 and 149.', 'danger')
        return redirect(url_for('patients'))
    db = get_connection()
    db.execute(
        "UPDATE Patient SET Name=?, Age=?, Gender=?, Phone=?, Address=? WHERE Patient_ID=?",
        (name, age, gender, phone, address, patient_id)
    )
    db.commit()
    flash(f'Patient "{name}" updated successfully!', 'success')
    return redirect(url_for('patients'))


@app.route('/patients/delete/<int:patient_id>', methods=['POST'])
@login_required
def delete_patient(patient_id):
    db = get_connection()
    patient = db.execute("SELECT Name FROM Patient WHERE Patient_ID = ?", (patient_id,)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients'))
    try:
        db.execute("DELETE FROM Patient WHERE Patient_ID = ?", (patient_id,))
        db.commit()
        flash(f'Patient "{patient["Name"]}" deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete patient with existing appointments or records.', 'danger')
    return redirect(url_for('patients'))


@app.route('/patients/view/<int:patient_id>')
@login_required
def view_patient(patient_id):
    db = get_connection()
    patient = db.execute("SELECT * FROM Patient WHERE Patient_ID = ?", (patient_id,)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients'))
    appointments = db.execute("""
        SELECT a.*, d.Name AS doctor_name FROM Appointment a
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        WHERE a.Patient_ID = ? ORDER BY a.DateTime DESC
    """, (patient_id,)).fetchall()
    records = db.execute("""
        SELECT r.*, d.Name AS doctor_name FROM Medical_Record r
        JOIN Doctor d ON r.Doctor_ID = d.Doctor_ID
        WHERE r.Patient_ID = ? ORDER BY r.Record_Date DESC
    """, (patient_id,)).fetchall()
    bills = db.execute(
        "SELECT * FROM Bill WHERE Patient_ID = ? ORDER BY Bill_Date DESC", (patient_id,)
    ).fetchall()
    insurance = db.execute(
        "SELECT * FROM Insurance WHERE Patient_ID = ?", (patient_id,)
    ).fetchall()
    return render_template('view_patient.html', patient=patient,
                           appointments=appointments, records=records,
                           bills=bills, insurance=insurance)


# ── Doctor Management ───────────────────────────────────────────────────

@app.route('/doctors')
@login_required
def doctors():
    db = get_connection()
    search = request.args.get('search', '').strip()
    spec_filter = request.args.get('specialization', '').strip()
    query = "SELECT * FROM Doctor WHERE 1=1"
    params = []
    if search:
        query += " AND (Name LIKE ? OR Specialization LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if spec_filter:
        query += " AND Specialization = ?"
        params.append(spec_filter)
    query += " ORDER BY Doctor_ID DESC"
    doctors_list = db.execute(query, params).fetchall()
    specializations = db.execute("SELECT DISTINCT Specialization FROM Doctor ORDER BY Specialization").fetchall()
    return render_template('doctors.html', doctors=doctors_list,
                           specializations=specializations, search=search,
                           spec_filter=spec_filter)


@app.route('/doctors/add', methods=['POST'])
@login_required
def add_doctor():
    name = request.form.get('name', '').strip()
    specialization = request.form.get('specialization', '').strip()
    phone = request.form.get('phone', '').strip()
    availability = request.form.get('availability', 'Available').strip()
    if not all([name, specialization, phone]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('doctors'))
    db = get_connection()
    db.execute(
        "INSERT INTO Doctor (Name, Specialization, Phone, Availability) VALUES (?, ?, ?, ?)",
        (name, specialization, phone, availability)
    )
    db.commit()
    flash(f'Doctor "{name}" added successfully!', 'success')
    return redirect(url_for('doctors'))


@app.route('/doctors/edit/<int:doctor_id>', methods=['POST'])
@login_required
def edit_doctor(doctor_id):
    name = request.form.get('name', '').strip()
    specialization = request.form.get('specialization', '').strip()
    phone = request.form.get('phone', '').strip()
    availability = request.form.get('availability', 'Available').strip()
    if not all([name, specialization, phone]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('doctors'))
    db = get_connection()
    db.execute(
        "UPDATE Doctor SET Name=?, Specialization=?, Phone=?, Availability=? WHERE Doctor_ID=?",
        (name, specialization, phone, availability, doctor_id)
    )
    db.commit()
    flash(f'Doctor "{name}" updated successfully!', 'success')
    return redirect(url_for('doctors'))


@app.route('/doctors/delete/<int:doctor_id>', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    db = get_connection()
    doctor = db.execute("SELECT Name FROM Doctor WHERE Doctor_ID = ?", (doctor_id,)).fetchone()
    if not doctor:
        flash('Doctor not found.', 'danger')
        return redirect(url_for('doctors'))
    try:
        db.execute("DELETE FROM Doctor WHERE Doctor_ID = ?", (doctor_id,))
        db.commit()
        flash(f'Doctor "{doctor["Name"]}" deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete doctor with existing appointments or records.', 'danger')
    return redirect(url_for('doctors'))


# ── Appointment Management ──────────────────────────────────────────────

@app.route('/appointments')
@login_required
def appointments():
    db = get_connection()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    doctor_filter = request.args.get('doctor_id', '').strip()
    date_filter = request.args.get('date', '').strip()
    query = """
        SELECT a.*, p.Name AS patient_name, d.Name AS doctor_name
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.Name LIKE ? OR d.Name LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if status_filter:
        query += " AND a.Status = ?"
        params.append(status_filter)
    if doctor_filter:
        query += " AND a.Doctor_ID = ?"
        params.append(int(doctor_filter))
    if date_filter:
        query += " AND DATE(a.DateTime) = ?"
        params.append(date_filter)
    query += " ORDER BY a.DateTime DESC"
    appointments_list = db.execute(query, params).fetchall()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    doctors_list = db.execute("SELECT Doctor_ID, Name FROM Doctor ORDER BY Name").fetchall()
    return render_template('appointments.html', appointments=appointments_list,
                           patients=patients_list, doctors=doctors_list,
                           search=search, status_filter=status_filter,
                           doctor_filter=doctor_filter, date_filter=date_filter)


@app.route('/appointments/add', methods=['POST'])
@login_required
def add_appointment():
    patient_id = request.form.get('patient_id', '').strip()
    doctor_id = request.form.get('doctor_id', '').strip()
    appt_date = request.form.get('date', '').strip()
    appt_time = request.form.get('time', '').strip()
    if not all([patient_id, doctor_id, appt_date, appt_time]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('appointments'))
    dt_str = f"{appt_date} {appt_time}"
    try:
        appt_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        if appt_dt < datetime.now():
            flash('Cannot book appointments in the past.', 'danger')
            return redirect(url_for('appointments'))
    except ValueError:
        flash('Invalid date/time format.', 'danger')
        return redirect(url_for('appointments'))
    db = get_connection()
    # Validate patient and doctor exist
    if not db.execute("SELECT 1 FROM Patient WHERE Patient_ID = ?", (patient_id,)).fetchone():
        flash('Selected patient does not exist.', 'danger')
        return redirect(url_for('appointments'))
    if not db.execute("SELECT 1 FROM Doctor WHERE Doctor_ID = ?", (doctor_id,)).fetchone():
        flash('Selected doctor does not exist.', 'danger')
        return redirect(url_for('appointments'))
    try:
        db.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, DateTime, Status) VALUES (?, ?, ?, 'Scheduled')",
            (int(patient_id), int(doctor_id), dt_str)
        )
        db.commit()
        flash('Appointment booked successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('This doctor already has an appointment at that date and time. Please choose another slot.', 'danger')
    return redirect(url_for('appointments'))


@app.route('/appointments/status/<int:appt_id>', methods=['POST'])
@login_required
def update_appointment_status(appt_id):
    status = request.form.get('status', '').strip()
    if status not in ('Scheduled', 'Completed', 'Cancelled'):
        flash('Invalid status.', 'danger')
        return redirect(url_for('appointments'))
    db = get_connection()
    db.execute("UPDATE Appointment SET Status = ? WHERE Appointment_ID = ?", (status, appt_id))
    db.commit()
    flash(f'Appointment #{appt_id} status updated to {status}.', 'success')
    return redirect(url_for('appointments'))


@app.route('/appointments/delete/<int:appt_id>', methods=['POST'])
@login_required
def delete_appointment(appt_id):
    db = get_connection()
    db.execute("DELETE FROM Appointment WHERE Appointment_ID = ?", (appt_id,))
    db.commit()
    flash(f'Appointment #{appt_id} cancelled and removed.', 'success')
    return redirect(url_for('appointments'))


# ── Medical Records ─────────────────────────────────────────────────────

@app.route('/medical-records')
@login_required
def medical_records():
    db = get_connection()
    search = request.args.get('search', '').strip()
    query = """
        SELECT r.*, p.Name AS patient_name, d.Name AS doctor_name
        FROM Medical_Record r
        JOIN Patient p ON r.Patient_ID = p.Patient_ID
        JOIN Doctor d ON r.Doctor_ID = d.Doctor_ID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.Name LIKE ? OR r.Diagnosis LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    query += " ORDER BY r.Record_Date DESC"
    records = db.execute(query, params).fetchall()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    doctors_list = db.execute("SELECT Doctor_ID, Name FROM Doctor ORDER BY Name").fetchall()
    return render_template('medical_records.html', records=records,
                           patients=patients_list, doctors=doctors_list, search=search)


@app.route('/medical-records/add', methods=['POST'])
@login_required
def add_medical_record():
    patient_id = request.form.get('patient_id', '').strip()
    doctor_id = request.form.get('doctor_id', '').strip()
    diagnosis = request.form.get('diagnosis', '').strip()
    treatment = request.form.get('treatment', '').strip()
    record_date = request.form.get('record_date', '').strip()
    if not all([patient_id, doctor_id, diagnosis, treatment, record_date]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('medical_records'))
    db = get_connection()
    db.execute(
        "INSERT INTO Medical_Record (Patient_ID, Doctor_ID, Diagnosis, Treatment, Record_Date) VALUES (?, ?, ?, ?, ?)",
        (int(patient_id), int(doctor_id), diagnosis, treatment, record_date)
    )
    db.commit()
    flash('Medical record added successfully!', 'success')
    return redirect(url_for('medical_records'))


# ── Prescription Management ─────────────────────────────────────────────

@app.route('/prescriptions')
@login_required
def prescriptions():
    db = get_connection()
    search = request.args.get('search', '').strip()
    query = """
        SELECT pr.*, mr.Diagnosis, m.Medicine_Name, p.Name AS patient_name
        FROM Prescription pr
        JOIN Medical_Record mr ON pr.Record_ID = mr.Record_ID
        JOIN Medicine m ON pr.Medicine_ID = m.Medicine_ID
        JOIN Patient p ON mr.Patient_ID = p.Patient_ID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.Name LIKE ? OR m.Medicine_Name LIKE ? OR mr.Diagnosis LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    query += " ORDER BY pr.Prescription_ID DESC"
    prescriptions_list = db.execute(query, params).fetchall()
    records_list = db.execute("""
        SELECT mr.Record_ID, p.Name AS patient_name, mr.Diagnosis
        FROM Medical_Record mr JOIN Patient p ON mr.Patient_ID = p.Patient_ID
        ORDER BY mr.Record_ID DESC
    """).fetchall()
    medicines_list = db.execute("SELECT Medicine_ID, Medicine_Name FROM Medicine ORDER BY Medicine_Name").fetchall()
    return render_template('prescriptions.html', prescriptions=prescriptions_list,
                           records=records_list, medicines=medicines_list, search=search)


@app.route('/prescriptions/add', methods=['POST'])
@login_required
def add_prescription():
    record_id = request.form.get('record_id', '').strip()
    medicine_id = request.form.get('medicine_id', '').strip()
    dosage = request.form.get('dosage', '').strip()
    duration = request.form.get('duration', '').strip()
    if not all([record_id, medicine_id, dosage, duration]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('prescriptions'))
    db = get_connection()
    db.execute(
        "INSERT INTO Prescription (Record_ID, Medicine_ID, Dosage, Duration) VALUES (?, ?, ?, ?)",
        (int(record_id), int(medicine_id), dosage, duration)
    )
    db.commit()
    flash('Prescription added successfully!', 'success')
    return redirect(url_for('prescriptions'))


# ── Medicine Management ─────────────────────────────────────────────────

@app.route('/medicines')
@login_required
def medicines():
    db = get_connection()
    search = request.args.get('search', '').strip()
    query = "SELECT * FROM Medicine WHERE 1=1"
    params = []
    if search:
        query += " AND Medicine_Name LIKE ?"
        params.append(f'%{search}%')
    query += " ORDER BY Medicine_ID DESC"
    medicines_list = db.execute(query, params).fetchall()
    return render_template('medicines.html', medicines=medicines_list, search=search)


@app.route('/medicines/add', methods=['POST'])
@login_required
def add_medicine():
    name = request.form.get('name', '').strip()
    quantity = request.form.get('quantity', '').strip()
    price = request.form.get('price', '').strip()
    expiry = request.form.get('expiry_date', '').strip()
    if not all([name, quantity, price, expiry]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('medicines'))
    try:
        quantity = int(quantity)
        price = float(price)
        if quantity < 0 or price < 0:
            raise ValueError
    except ValueError:
        flash('Quantity and price must be valid non-negative numbers.', 'danger')
        return redirect(url_for('medicines'))
    db = get_connection()
    db.execute(
        "INSERT INTO Medicine (Medicine_Name, Quantity, Price, Expiry_Date) VALUES (?, ?, ?, ?)",
        (name, quantity, price, expiry)
    )
    db.commit()
    flash(f'Medicine "{name}" added successfully!', 'success')
    return redirect(url_for('medicines'))


@app.route('/medicines/edit/<int:medicine_id>', methods=['POST'])
@login_required
def edit_medicine(medicine_id):
    name = request.form.get('name', '').strip()
    quantity = request.form.get('quantity', '').strip()
    price = request.form.get('price', '').strip()
    expiry = request.form.get('expiry_date', '').strip()
    if not all([name, quantity, price, expiry]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('medicines'))
    try:
        quantity = int(quantity)
        price = float(price)
        if quantity < 0 or price < 0:
            raise ValueError
    except ValueError:
        flash('Quantity and price must be valid non-negative numbers.', 'danger')
        return redirect(url_for('medicines'))
    db = get_connection()
    db.execute(
        "UPDATE Medicine SET Medicine_Name=?, Quantity=?, Price=?, Expiry_Date=? WHERE Medicine_ID=?",
        (name, quantity, price, expiry, medicine_id)
    )
    db.commit()
    flash(f'Medicine "{name}" updated successfully!', 'success')
    return redirect(url_for('medicines'))


@app.route('/medicines/delete/<int:medicine_id>', methods=['POST'])
@login_required
def delete_medicine(medicine_id):
    db = get_connection()
    med = db.execute("SELECT Medicine_Name FROM Medicine WHERE Medicine_ID = ?", (medicine_id,)).fetchone()
    if not med:
        flash('Medicine not found.', 'danger')
        return redirect(url_for('medicines'))
    try:
        db.execute("DELETE FROM Medicine WHERE Medicine_ID = ?", (medicine_id,))
        db.commit()
        flash(f'Medicine "{med["Medicine_Name"]}" deleted.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete medicine referenced by prescriptions.', 'danger')
    return redirect(url_for('medicines'))


# ── Billing ─────────────────────────────────────────────────────────────

@app.route('/billing')
@login_required
def billing():
    db = get_connection()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    query = """
        SELECT b.*, p.Name AS patient_name
        FROM Bill b JOIN Patient p ON b.Patient_ID = p.Patient_ID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND p.Name LIKE ?"
        params.append(f'%{search}%')
    if status_filter:
        query += " AND b.Payment_Status = ?"
        params.append(status_filter)
    query += " ORDER BY b.Bill_Date DESC"
    bills = db.execute(query, params).fetchall()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    return render_template('billing.html', bills=bills, patients=patients_list,
                           search=search, status_filter=status_filter)


@app.route('/billing/add', methods=['POST'])
@login_required
def add_bill():
    patient_id = request.form.get('patient_id', '').strip()
    amount = request.form.get('amount', '').strip()
    bill_date = request.form.get('bill_date', '').strip()
    status = request.form.get('payment_status', 'Pending').strip()
    if not all([patient_id, amount, bill_date]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('billing'))
    try:
        amount = float(amount)
        if amount < 0:
            raise ValueError
    except ValueError:
        flash('Amount must be a valid non-negative number.', 'danger')
        return redirect(url_for('billing'))
    db = get_connection()
    db.execute(
        "INSERT INTO Bill (Patient_ID, Amount, Bill_Date, Payment_Status) VALUES (?, ?, ?, ?)",
        (int(patient_id), amount, bill_date, status)
    )
    db.commit()
    flash('Bill created successfully!', 'success')
    return redirect(url_for('billing'))


@app.route('/billing/status/<int:bill_id>', methods=['POST'])
@login_required
def update_bill_status(bill_id):
    status = request.form.get('payment_status', '').strip()
    if status not in ('Pending', 'Paid', 'Overdue'):
        flash('Invalid payment status.', 'danger')
        return redirect(url_for('billing'))
    db = get_connection()
    db.execute("UPDATE Bill SET Payment_Status = ? WHERE Bill_ID = ?", (status, bill_id))
    db.commit()
    flash(f'Bill #{bill_id} status updated to {status}.', 'success')
    return redirect(url_for('billing'))


# ── Insurance ───────────────────────────────────────────────────────────

@app.route('/insurance')
@login_required
def insurance():
    db = get_connection()
    search = request.args.get('search', '').strip()
    query = """
        SELECT i.*, p.Name AS patient_name
        FROM Insurance i JOIN Patient p ON i.Patient_ID = p.Patient_ID
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.Name LIKE ? OR i.Provider LIKE ? OR i.Policy_Number LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    query += " ORDER BY i.Insurance_ID DESC"
    insurance_list = db.execute(query, params).fetchall()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    return render_template('insurance.html', insurance=insurance_list,
                           patients=patients_list, search=search)


@app.route('/insurance/add', methods=['POST'])
@login_required
def add_insurance():
    patient_id = request.form.get('patient_id', '').strip()
    provider = request.form.get('provider', '').strip()
    policy_number = request.form.get('policy_number', '').strip()
    coverage = request.form.get('coverage_amount', '').strip()
    if not all([patient_id, provider, policy_number, coverage]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('insurance'))
    try:
        coverage = float(coverage)
        if coverage < 0:
            raise ValueError
    except ValueError:
        flash('Coverage amount must be a valid non-negative number.', 'danger')
        return redirect(url_for('insurance'))
    db = get_connection()
    try:
        db.execute(
            "INSERT INTO Insurance (Patient_ID, Provider, Policy_Number, Coverage_Amount) VALUES (?, ?, ?, ?)",
            (int(patient_id), provider, policy_number, coverage)
        )
        db.commit()
        flash('Insurance details added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('Policy number already exists.', 'danger')
    return redirect(url_for('insurance'))


# ── DBMS Lab ────────────────────────────────────────────────────────────

@app.route('/dbms-lab')
@login_required
def dbms_lab():
    return render_template('dbms_lab.html')


@app.route('/dbms-lab/run', methods=['POST'])
@login_required
def run_dbms_demo():
    """Run predefined SQL demonstrations safely."""
    demo_id = request.form.get('demo_id', '')
    db = get_connection()
    result = {'success': False, 'message': '', 'rows': [], 'columns': []}

    demos = {
        'ddl_create': {
            'sql': """CREATE TABLE IF NOT EXISTS Demo_Log (
    Log_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Action TEXT NOT NULL,
    Timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);""",
            'type': 'execute'
        },
        'ddl_alter': {
            'sql': "ALTER TABLE Demo_Log ADD COLUMN Details TEXT DEFAULT '';",
            'type': 'execute',
            'ignore_error': True
        },
        'dml_insert': {
            'sql': "INSERT INTO Demo_Log (Action, Details) VALUES ('Demo Insert', 'This row was inserted by the DBMS Lab demo');",
            'type': 'execute'
        },
        'dml_select': {
            'sql': "SELECT * FROM Patient ORDER BY Patient_ID LIMIT 5;",
            'type': 'query'
        },
        'dml_select_join': {
            'sql': """SELECT a.Appointment_ID, p.Name AS Patient, d.Name AS Doctor, a.DateTime, a.Status
FROM Appointment a
JOIN Patient p ON a.Patient_ID = p.Patient_ID
JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
ORDER BY a.DateTime DESC LIMIT 5;""",
            'type': 'query'
        },
        'dml_update': {
            'sql': "UPDATE Demo_Log SET Details = 'Updated by DBMS Lab demo' WHERE Action = 'Demo Insert';",
            'type': 'execute'
        },
        'dml_delete': {
            'sql': "DELETE FROM Demo_Log WHERE Action = 'Demo Insert';",
            'type': 'execute'
        },
        'dml_aggregate': {
            'sql': """SELECT d.Name AS Doctor, COUNT(a.Appointment_ID) AS Total_Appointments
FROM Doctor d LEFT JOIN Appointment a ON d.Doctor_ID = a.Doctor_ID
GROUP BY d.Doctor_ID ORDER BY Total_Appointments DESC;""",
            'type': 'query'
        },
        'dml_subquery': {
            'sql': """SELECT Name, Age, Gender FROM Patient
WHERE Patient_ID IN (
    SELECT Patient_ID FROM Appointment WHERE Status = 'Completed'
);""",
            'type': 'query'
        },
    }

    if demo_id not in demos:
        return jsonify({'success': False, 'message': 'Unknown demo.'})

    demo = demos[demo_id]
    try:
        if demo['type'] == 'query':
            rows = db.execute(demo['sql']).fetchall()
            if rows:
                result['columns'] = list(rows[0].keys())
                result['rows'] = [list(row) for row in rows]
            result['success'] = True
            result['message'] = f'{len(rows)} row(s) returned.'
        else:
            db.execute(demo['sql'])
            db.commit()
            result['success'] = True
            result['message'] = 'Statement executed successfully.'
    except Exception as e:
        if demo.get('ignore_error'):
            result['success'] = True
            result['message'] = f'Statement executed (column may already exist).'
        else:
            result['message'] = str(e)

    return jsonify(result)


# ── Schema Page ─────────────────────────────────────────────────────────

@app.route('/schema')
@login_required
def schema():
    db = get_connection()
    tables = db.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    indexes = db.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name"
    ).fetchall()
    return render_template('schema.html', tables=tables, indexes=indexes)


# ── Transactions Demo ──────────────────────────────────────────────────

@app.route('/transactions')
@login_required
def transactions():
    db = get_connection()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    doctors_list = db.execute("SELECT Doctor_ID, Name FROM Doctor ORDER BY Name").fetchall()
    return render_template('transactions.html', patients=patients_list, doctors=doctors_list)


@app.route('/transactions/demo', methods=['POST'])
@login_required
def transaction_demo():
    """Demonstrate a transaction with commit or rollback."""
    patient_id = request.form.get('patient_id', '').strip()
    doctor_id = request.form.get('doctor_id', '').strip()
    appt_date = request.form.get('date', '').strip()
    appt_time = request.form.get('time', '').strip()
    force_fail = request.form.get('force_fail', '') == '1'

    steps = []
    dt_str = f"{appt_date} {appt_time}" if appt_date and appt_time else ''

    conn = get_db()  # Fresh connection for isolation
    try:
        # Step 1: Begin transaction
        steps.append({'step': 'BEGIN TRANSACTION', 'status': 'success', 'detail': 'Transaction started.'})

        # Step 2: Validate patient
        patient = conn.execute("SELECT * FROM Patient WHERE Patient_ID = ?", (patient_id,)).fetchone()
        if not patient:
            raise ValueError(f"Patient ID {patient_id} does not exist.")
        steps.append({'step': 'Validate Patient ID', 'status': 'success',
                      'detail': f'Patient found: {patient["Name"]}'})

        # Step 3: Validate doctor
        doctor = conn.execute("SELECT * FROM Doctor WHERE Doctor_ID = ?", (doctor_id,)).fetchone()
        if not doctor:
            raise ValueError(f"Doctor ID {doctor_id} does not exist.")
        steps.append({'step': 'Validate Doctor ID', 'status': 'success',
                      'detail': f'Doctor found: {doctor["Name"]}'})

        # Step 4: Check slot
        existing = conn.execute(
            "SELECT * FROM Appointment WHERE Doctor_ID = ? AND DateTime = ?",
            (doctor_id, dt_str)
        ).fetchone()
        if existing:
            raise ValueError(f"Slot conflict: Doctor already booked at {dt_str}.")
        steps.append({'step': 'Check Appointment Slot', 'status': 'success',
                      'detail': f'Slot {dt_str} is available.'})

        # Step 5: Force failure for demo
        if force_fail:
            raise ValueError("Simulated failure triggered for rollback demonstration.")

        # Step 6: Insert
        conn.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, DateTime, Status) VALUES (?, ?, ?, 'Scheduled')",
            (int(patient_id), int(doctor_id), dt_str)
        )
        steps.append({'step': 'INSERT Appointment', 'status': 'success',
                      'detail': f'Appointment row inserted.'})

        # Step 7: Commit
        conn.commit()
        steps.append({'step': 'COMMIT', 'status': 'success',
                      'detail': 'Transaction committed successfully. All changes are permanent.'})
        outcome = 'committed'

    except (ValueError, sqlite3.IntegrityError) as e:
        conn.rollback()
        steps.append({'step': 'Error Detected', 'status': 'error', 'detail': str(e)})
        steps.append({'step': 'ROLLBACK', 'status': 'rollback',
                      'detail': 'Transaction rolled back. No changes were saved to the database.'})
        outcome = 'rolled_back'
    except Exception as e:
        conn.rollback()
        steps.append({'step': 'Unexpected Error', 'status': 'error', 'detail': str(e)})
        steps.append({'step': 'ROLLBACK', 'status': 'rollback', 'detail': 'Transaction rolled back.'})
        outcome = 'rolled_back'
    finally:
        conn.close()

    return jsonify({'steps': steps, 'outcome': outcome})


# ── Concurrency Control Demo ───────────────────────────────────────────

@app.route('/concurrency')
@login_required
def concurrency():
    db = get_connection()
    patients_list = db.execute("SELECT Patient_ID, Name FROM Patient ORDER BY Name").fetchall()
    doctors_list = db.execute("SELECT Doctor_ID, Name FROM Doctor ORDER BY Name").fetchall()
    return render_template('concurrency.html', patients=patients_list, doctors=doctors_list)


@app.route('/concurrency/demo', methods=['POST'])
@login_required
def concurrency_demo():
    """Simulate two concurrent booking requests for the same slot."""
    doctor_id = request.form.get('doctor_id', '').strip()
    appt_date = request.form.get('date', '').strip()
    appt_time = request.form.get('time', '').strip()
    patient_a = request.form.get('patient_a', '').strip()
    patient_b = request.form.get('patient_b', '').strip()

    dt_str = f"{appt_date} {appt_time}"
    results = []

    # First, clean up any existing appointment at this slot for a clean demo
    cleanup_conn = get_db()
    cleanup_conn.execute(
        "DELETE FROM Appointment WHERE Doctor_ID = ? AND DateTime = ?",
        (int(doctor_id), dt_str)
    )
    cleanup_conn.commit()
    cleanup_conn.close()

    # Request A
    conn_a = get_db()
    try:
        slot = conn_a.execute(
            "SELECT * FROM Appointment WHERE Doctor_ID = ? AND DateTime = ?",
            (int(doctor_id), dt_str)
        ).fetchone()
        results.append({
            'request': 'A', 'patient_id': patient_a,
            'step': 'Check Slot', 'detail': 'Slot is available.' if not slot else 'Slot taken.',
            'status': 'success'
        })
        conn_a.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, DateTime, Status) VALUES (?, ?, ?, 'Scheduled')",
            (int(patient_a), int(doctor_id), dt_str)
        )
        conn_a.commit()
        results.append({
            'request': 'A', 'patient_id': patient_a,
            'step': 'Book Slot', 'detail': 'Booking SUCCEEDED — appointment created.',
            'status': 'success'
        })
    except sqlite3.IntegrityError:
        conn_a.rollback()
        results.append({
            'request': 'A', 'patient_id': patient_a,
            'step': 'Book Slot', 'detail': 'Booking FAILED — slot already taken (UNIQUE constraint).',
            'status': 'error'
        })
    finally:
        conn_a.close()

    # Request B (same slot)
    conn_b = get_db()
    try:
        slot = conn_b.execute(
            "SELECT * FROM Appointment WHERE Doctor_ID = ? AND DateTime = ?",
            (int(doctor_id), dt_str)
        ).fetchone()
        results.append({
            'request': 'B', 'patient_id': patient_b,
            'step': 'Check Slot', 'detail': 'Slot is available.' if not slot else 'Slot is now TAKEN by Request A.',
            'status': 'warning' if slot else 'success'
        })
        conn_b.execute(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, DateTime, Status) VALUES (?, ?, ?, 'Scheduled')",
            (int(patient_b), int(doctor_id), dt_str)
        )
        conn_b.commit()
        results.append({
            'request': 'B', 'patient_id': patient_b,
            'step': 'Book Slot', 'detail': 'Booking SUCCEEDED.',
            'status': 'success'
        })
    except sqlite3.IntegrityError:
        conn_b.rollback()
        results.append({
            'request': 'B', 'patient_id': patient_b,
            'step': 'Book Slot',
            'detail': 'Booking FAILED — UNIQUE constraint on (Doctor_ID, DateTime) prevented double-booking.',
            'status': 'error'
        })
    finally:
        conn_b.close()

    # Final state
    final_conn = get_db()
    final_appts = final_conn.execute("""
        SELECT a.Appointment_ID, p.Name AS patient_name, d.Name AS doctor_name, a.DateTime, a.Status
        FROM Appointment a
        JOIN Patient p ON a.Patient_ID = p.Patient_ID
        JOIN Doctor d ON a.Doctor_ID = d.Doctor_ID
        WHERE a.Doctor_ID = ? AND a.DateTime = ?
    """, (int(doctor_id), dt_str)).fetchall()
    final_records = [dict(r) for r in final_appts]
    final_conn.close()

    return jsonify({'results': results, 'final_records': final_records})


# ── RAID Storage Demo ──────────────────────────────────────────────────

@app.route('/raid')
@login_required
def raid():
    return render_template('raid.html')


# ── Query Optimisation Demo ────────────────────────────────────────────

@app.route('/optimisation')
@login_required
def optimisation():
    return render_template('optimisation.html')


@app.route('/optimisation/demo', methods=['POST'])
@login_required
def optimisation_demo():
    """Run EXPLAIN QUERY PLAN before and after index."""
    demo_type = request.form.get('type', '')
    db = get_connection()

    if demo_type == 'before_select_star':
        plan = db.execute("EXPLAIN QUERY PLAN SELECT * FROM Appointment WHERE Patient_ID = 1").fetchall()
        return jsonify({
            'sql': 'SELECT * FROM Appointment WHERE Patient_ID = 1;',
            'plan': [list(r) for r in plan],
            'columns': ['selectid', 'order', 'from', 'detail']
        })

    elif demo_type == 'after_select_cols':
        plan = db.execute(
            "EXPLAIN QUERY PLAN SELECT Appointment_ID, Doctor_ID, DateTime FROM Appointment WHERE Patient_ID = 1"
        ).fetchall()
        return jsonify({
            'sql': 'SELECT Appointment_ID, Doctor_ID, DateTime FROM Appointment WHERE Patient_ID = 1;',
            'plan': [list(r) for r in plan],
            'columns': ['selectid', 'order', 'from', 'detail']
        })

    elif demo_type == 'show_index':
        indexes = db.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND tbl_name='Appointment'"
        ).fetchall()
        return jsonify({
            'indexes': [{'name': r[0], 'table': r[1], 'sql': r[2]} for r in indexes]
        })

    elif demo_type == 'timing':
        import time
        # Run query multiple times for measurable timing
        t1 = time.perf_counter()
        for _ in range(1000):
            db.execute("SELECT * FROM Appointment WHERE Patient_ID = 1").fetchall()
        time_star = time.perf_counter() - t1

        t2 = time.perf_counter()
        for _ in range(1000):
            db.execute(
                "SELECT Appointment_ID, Doctor_ID, DateTime FROM Appointment WHERE Patient_ID = 1"
            ).fetchall()
        time_cols = time.perf_counter() - t2

        return jsonify({
            'time_select_star': round(time_star * 1000, 2),
            'time_select_cols': round(time_cols * 1000, 2),
            'iterations': 1000,
            'note': 'Times are in milliseconds for 1000 iterations. With small datasets, differences may be minimal.'
        })

    return jsonify({'error': 'Unknown demo type.'})


# ── Application Entry Point ────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
