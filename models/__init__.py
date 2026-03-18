from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import pickle

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Student, Lecturer, Security Officer, Head of Security
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    incidents_reported = db.relationship('Incident', backref='reporter', lazy=True)

    # Fixed relationship: alerts_received points to Alert.recipient_id
    alerts_received = db.relationship(
        'Alert',
        backref='recipient',      # Alert.recipient gives the User
        lazy=True,
        foreign_keys='Alert.recipient_id'
    )

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)


class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    location = db.Column(db.String(100))
    category = db.Column(db.String(100))
    incident_date = db.Column(db.String(50))
    reported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    severity = db.Column(db.String(50))
    status = db.Column(db.String(50), default="Pending")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('security_personnel.id'), nullable=True)
    assigned_officer = db.relationship('SecurityPersonnel', backref='incidents', lazy=True)

    # Track which users have dismissed this incident
    dismissed_by = db.Column(db.PickleType, default=list)

    # Investigation and Resolution notes
    investigation_notes = db.Column(db.Text, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    @property
    def reported_by_username(self):
        return self.reporter.username if self.reporter else "Anonymous"

    @property
    def reported_by_role(self):
        return self.reporter.role if self.reporter else "Unknown"


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='Normal')  # 'Normal' or 'Critical'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationship to access incident details from an alert
    incident = db.relationship('Incident', backref='alerts', lazy=True)

    # Recipient relationship is now fixed using foreign_keys in User model
    # Access recipient via Alert.recipient (backref)
    # User.alerts_received gives all alerts received by the user


class SecurityPersonnel(db.Model):
    __tablename__ = 'security_personnel'

    id = db.Column(db.Integer, primary_key=True)
    personnel_id = db.Column(db.String(20), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    hire_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='Off Duty')
    employment_status = db.Column(db.String(50), default="Active")

    attendance_records = db.relationship('Attendance', backref='personnel', lazy=True)


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    personnel_id = db.Column(db.Integer, db.ForeignKey('security_personnel.id'), nullable=False)
    campus = db.Column(db.String(50), nullable=True)
    sign_in_time = db.Column(db.DateTime, nullable=True)
    sign_out_time = db.Column(db.DateTime, nullable=True)
    date = db.Column(db.Date, default=date.today)


