"""
database.py — Database initialization, schema creation, seed data, and helpers.
Hospital Management System — Team 15 DBMS Capstone Project.
"""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'hospital.db')


def get_db():
    """Return a new database connection with foreign keys enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Create all tables, indexes, and seed data if not already present."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # ── DDL: Create Tables ──────────────────────────────────────────────

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS User (
        User_ID     INTEGER PRIMARY KEY AUTOINCREMENT,
        Username    TEXT NOT NULL UNIQUE,
        Password    TEXT NOT NULL,
        Role        TEXT NOT NULL DEFAULT 'admin'
    );

    CREATE TABLE IF NOT EXISTS Patient (
        Patient_ID  INTEGER PRIMARY KEY AUTOINCREMENT,
        Name        TEXT NOT NULL,
        Age         INTEGER NOT NULL CHECK(Age > 0 AND Age < 150),
        Gender      TEXT NOT NULL CHECK(Gender IN ('Male', 'Female', 'Other')),
        Phone       TEXT NOT NULL,
        Address     TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS Doctor (
        Doctor_ID       INTEGER PRIMARY KEY AUTOINCREMENT,
        Name            TEXT NOT NULL,
        Specialization  TEXT NOT NULL,
        Phone           TEXT NOT NULL,
        Availability    TEXT NOT NULL DEFAULT 'Available'
    );

    CREATE TABLE IF NOT EXISTS Appointment (
        Appointment_ID  INTEGER PRIMARY KEY AUTOINCREMENT,
        Patient_ID      INTEGER NOT NULL,
        Doctor_ID       INTEGER NOT NULL,
        DateTime        TEXT NOT NULL,
        Status          TEXT NOT NULL DEFAULT 'Scheduled'
                        CHECK(Status IN ('Scheduled', 'Completed', 'Cancelled')),
        FOREIGN KEY (Patient_ID) REFERENCES Patient(Patient_ID),
        FOREIGN KEY (Doctor_ID)  REFERENCES Doctor(Doctor_ID),
        UNIQUE(Doctor_ID, DateTime)
    );

    CREATE TABLE IF NOT EXISTS Medical_Record (
        Record_ID   INTEGER PRIMARY KEY AUTOINCREMENT,
        Patient_ID  INTEGER NOT NULL,
        Doctor_ID   INTEGER NOT NULL,
        Diagnosis   TEXT NOT NULL,
        Treatment   TEXT NOT NULL,
        Record_Date TEXT NOT NULL,
        FOREIGN KEY (Patient_ID) REFERENCES Patient(Patient_ID),
        FOREIGN KEY (Doctor_ID)  REFERENCES Doctor(Doctor_ID)
    );

    CREATE TABLE IF NOT EXISTS Medicine (
        Medicine_ID   INTEGER PRIMARY KEY AUTOINCREMENT,
        Medicine_Name TEXT NOT NULL,
        Quantity      INTEGER NOT NULL CHECK(Quantity >= 0),
        Price         REAL NOT NULL CHECK(Price >= 0),
        Expiry_Date   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS Prescription (
        Prescription_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Record_ID       INTEGER NOT NULL,
        Medicine_ID     INTEGER NOT NULL,
        Dosage          TEXT NOT NULL,
        Duration        TEXT NOT NULL,
        FOREIGN KEY (Record_ID)   REFERENCES Medical_Record(Record_ID),
        FOREIGN KEY (Medicine_ID) REFERENCES Medicine(Medicine_ID)
    );

    CREATE TABLE IF NOT EXISTS Bill (
        Bill_ID         INTEGER PRIMARY KEY AUTOINCREMENT,
        Patient_ID      INTEGER NOT NULL,
        Amount          REAL NOT NULL CHECK(Amount >= 0),
        Bill_Date       TEXT NOT NULL,
        Payment_Status  TEXT NOT NULL DEFAULT 'Pending'
                        CHECK(Payment_Status IN ('Pending', 'Paid', 'Overdue')),
        FOREIGN KEY (Patient_ID) REFERENCES Patient(Patient_ID)
    );

    CREATE TABLE IF NOT EXISTS Insurance (
        Insurance_ID    INTEGER PRIMARY KEY AUTOINCREMENT,
        Patient_ID      INTEGER NOT NULL,
        Provider        TEXT NOT NULL,
        Policy_Number   TEXT NOT NULL UNIQUE,
        Coverage_Amount REAL NOT NULL CHECK(Coverage_Amount >= 0),
        FOREIGN KEY (Patient_ID) REFERENCES Patient(Patient_ID)
    );

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_appt_patient   ON Appointment(Patient_ID);
    CREATE INDEX IF NOT EXISTS idx_appt_doctor    ON Appointment(Doctor_ID);
    CREATE INDEX IF NOT EXISTS idx_appt_datetime  ON Appointment(DateTime);
    CREATE INDEX IF NOT EXISTS idx_record_patient  ON Medical_Record(Patient_ID);
    CREATE INDEX IF NOT EXISTS idx_bill_patient    ON Bill(Patient_ID);
    CREATE INDEX IF NOT EXISTS idx_insurance_patient ON Insurance(Patient_ID);
    """)

    # ── Seed Data (only if tables are empty) ────────────────────────────

    if cursor.execute("SELECT COUNT(*) FROM User").fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        cursor.execute(
            "INSERT INTO User (Username, Password, Role) VALUES (?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 'admin')
        )

    if cursor.execute("SELECT COUNT(*) FROM Patient").fetchone()[0] == 0:
        patients = [
            ('Aarav Sharma', 28, 'Male', '9876543210', '12 MG Road, Chennai'),
            ('Priya Nair', 34, 'Female', '9876543211', '45 Anna Nagar, Chennai'),
            ('Vikram Patel', 45, 'Male', '9876543212', '78 T Nagar, Chennai'),
            ('Divya Krishnan', 22, 'Female', '9876543213', '23 Adyar, Chennai'),
            ('Rahul Menon', 55, 'Male', '9876543214', '90 Velachery, Chennai'),
            ('Sneha Iyer', 30, 'Female', '9876543215', '34 Mylapore, Chennai'),
            ('Karthik Rajan', 40, 'Male', '9876543216', '67 Guindy, Chennai'),
            ('Ananya Das', 26, 'Female', '9876543217', '11 Porur, Chennai'),
        ]
        cursor.executemany(
            "INSERT INTO Patient (Name, Age, Gender, Phone, Address) VALUES (?, ?, ?, ?, ?)",
            patients
        )

    if cursor.execute("SELECT COUNT(*) FROM Doctor").fetchone()[0] == 0:
        doctors = [
            ('Dr. Lakshmi Subramaniam', 'Cardiology', '9000000001', 'Available'),
            ('Dr. Rajesh Kumar', 'Neurology', '9000000002', 'Available'),
            ('Dr. Meena Venkatesh', 'Orthopedics', '9000000003', 'Available'),
            ('Dr. Arjun Reddy', 'Pediatrics', '9000000004', 'Available'),
            ('Dr. Kavitha Sundaram', 'Dermatology', '9000000005', 'On Leave'),
            ('Dr. Suresh Babu', 'General Medicine', '9000000006', 'Available'),
        ]
        cursor.executemany(
            "INSERT INTO Doctor (Name, Specialization, Phone, Availability) VALUES (?, ?, ?, ?)",
            doctors
        )

    if cursor.execute("SELECT COUNT(*) FROM Appointment").fetchone()[0] == 0:
        appointments = [
            (1, 1, '2026-10-25 09:00', 'Completed'),
            (2, 2, '2026-10-25 10:00', 'Completed'),
            (3, 3, '2026-10-25 11:00', 'Scheduled'),
            (4, 4, '2026-10-26 09:00', 'Scheduled'),
            (5, 1, '2026-10-26 10:00', 'Scheduled'),
            (6, 6, '2026-10-27 14:00', 'Scheduled'),
        ]
        cursor.executemany(
            "INSERT INTO Appointment (Patient_ID, Doctor_ID, DateTime, Status) VALUES (?, ?, ?, ?)",
            appointments
        )

    if cursor.execute("SELECT COUNT(*) FROM Medical_Record").fetchone()[0] == 0:
        records = [
            (1, 1, 'Mild Hypertension', 'Lifestyle changes and Amlodipine 5mg', '2026-10-25'),
            (2, 2, 'Migraine', 'Sumatriptan 50mg as needed', '2026-10-25'),
            (3, 3, 'Knee Osteoarthritis', 'Physiotherapy and Diclofenac gel', '2026-10-25'),
        ]
        cursor.executemany(
            "INSERT INTO Medical_Record (Patient_ID, Doctor_ID, Diagnosis, Treatment, Record_Date) VALUES (?, ?, ?, ?, ?)",
            records
        )

    if cursor.execute("SELECT COUNT(*) FROM Medicine").fetchone()[0] == 0:
        medicines = [
            ('Amlodipine 5mg', 200, 12.50, '2027-06-30'),
            ('Sumatriptan 50mg', 150, 45.00, '2027-03-15'),
            ('Diclofenac Gel 1%', 80, 85.00, '2027-09-01'),
            ('Paracetamol 500mg', 500, 5.00, '2028-01-20'),
            ('Amoxicillin 500mg', 300, 18.00, '2027-07-10'),
            ('Metformin 500mg', 400, 8.50, '2027-12-31'),
            ('Cetirizine 10mg', 15, 6.00, '2027-04-15'),
            ('Ibuprofen 400mg', 8, 10.00, '2027-08-20'),
        ]
        cursor.executemany(
            "INSERT INTO Medicine (Medicine_Name, Quantity, Price, Expiry_Date) VALUES (?, ?, ?, ?)",
            medicines
        )

    if cursor.execute("SELECT COUNT(*) FROM Prescription").fetchone()[0] == 0:
        prescriptions = [
            (1, 1, '5mg once daily', '30 days'),
            (2, 2, '50mg as needed, max 2/day', '14 days'),
            (3, 3, 'Apply twice daily', '21 days'),
        ]
        cursor.executemany(
            "INSERT INTO Prescription (Record_ID, Medicine_ID, Dosage, Duration) VALUES (?, ?, ?, ?)",
            prescriptions
        )

    if cursor.execute("SELECT COUNT(*) FROM Bill").fetchone()[0] == 0:
        bills = [
            (1, 1500.00, '2026-10-25', 'Paid'),
            (2, 2200.00, '2026-10-25', 'Pending'),
            (3, 3500.00, '2026-10-25', 'Pending'),
        ]
        cursor.executemany(
            "INSERT INTO Bill (Patient_ID, Amount, Bill_Date, Payment_Status) VALUES (?, ?, ?, ?)",
            bills
        )

    if cursor.execute("SELECT COUNT(*) FROM Insurance").fetchone()[0] == 0:
        insurance = [
            (1, 'Star Health Insurance', 'SH-2026-001', 500000.00),
            (2, 'ICICI Lombard', 'IL-2026-045', 300000.00),
            (5, 'New India Assurance', 'NIA-2026-112', 200000.00),
        ]
        cursor.executemany(
            "INSERT INTO Insurance (Patient_ID, Provider, Policy_Number, Coverage_Amount) VALUES (?, ?, ?, ?)",
            insurance
        )

    conn.commit()
    conn.close()
