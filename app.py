from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, User, Incident, Alert, SecurityPersonnel, Attendance
from datetime import datetime, date
import random
import string

# For password hashing
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- Helper Functions ----------------
def generate_personnel_id():
    prefix = "SEC"
    numbers = ''.join(random.choices(string.digits, k=4))
    return prefix + numbers

def get_user_id():
    user = User.query.filter_by(username=session.get('username')).first()
    return user.id if user else None

# ---------------- App Initialization ----------------
app = Flask(__name__)
app.secret_key = "your_secret_key"
import os
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///safealert.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# ---------------- Home ----------------
@app.route('/')
def home():
    return render_template('home.html')

# ---------------- Registration Route ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        # Block Security Officer self-registration
        if role == "Security Officer":
            flash("Security officers cannot register themselves. Contact Head of Security.")
            return redirect(url_for('register'))

        # Check if username or email already exists
        existing_user = User.query.filter((User.username==username) | (User.email==email)).first()
        if existing_user:
            flash("Username or email already exists.")
            return redirect(url_for('register'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Create user
        new_user = User(username=username, email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now login.")
        return redirect(url_for('login', role=role))

    return render_template('register.html')

@app.route('/select_role')
def select_role():
    return render_template('select_role.html')

# ---------------- Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    role = request.args.get('role')
    if not role:
        flash("Please select your role first.")
        return redirect(url_for('select_role'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Head of Security login
        if role == "Head of Security":
            if username == "admin" and password == "admin123":
                session['username'] = "Head of Security"
                session['role'] = role
                return redirect(url_for('head_dashboard'))
            else:
                flash("Invalid Head of Security credentials")
                return redirect(url_for('login', role=role))

        # Other roles
        user = User.query.filter_by(username=username, role=role).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password")
            return redirect(url_for('login', role=role))

        session['username'] = user.username
        session['role'] = user.role
        session['user_id'] = user.id # Store user ID for later use  

        # Ensure SecurityPersonnel record exists for Security Officer
        if role == "Security Officer":
            personnel = SecurityPersonnel.query.filter_by(username=username).first()
            if not personnel:
                personnel = SecurityPersonnel(
                    personnel_id=generate_personnel_id(),
                    username=username,
                    name=username,  # HOS can edit name later
                    status="Off Duty"
                )
                db.session.add(personnel)
                db.session.commit()

        # Redirect to correct dashboard
        if role == "Student":
            return redirect(url_for('student_dashboard'))
        elif role == "Lecturer":
            return redirect(url_for('lecturer_dashboard'))
        elif role == "Security Officer":
            return redirect(url_for('officer_dashboard'))
        elif role == "Head of Security":
            return redirect(url_for('head_dashboard'))

    return render_template('login.html', role=role)

# ---------------- Dashboards ----------------
@app.route('/student_dashboard')
def student_dashboard():
    user_id = session.get('user_id')  # assuming you store the logged-in user's id in session

    # Fetch all alerts for this student:
    # - Alerts specifically for them (recipient_id = user_id)
    # - All HOS critical alerts (priority='Critical')
    alerts = Alert.query.filter(
        (Alert.recipient_id == user_id) | (Alert.priority == 'Critical')
    ).order_by(Alert.timestamp.desc()).all()

    # Optional: Count critical alerts separately
    critical_alert_count = sum(1 for alert in alerts if alert.priority == 'Critical')

    return render_template(
        'student_dashboard.html',
        alerts=alerts,
        critical_alert_count=critical_alert_count
    )

@app.route('/lecturer_dashboard')
def lecturer_dashboard():
    user_id = session.get('user_id')  # assuming you store the logged-in lecturer's id

    # Fetch all alerts for this lecturer
    alerts = Alert.query.filter(
        (Alert.recipient_id == user_id) | (Alert.priority == 'Critical')
    ).order_by(Alert.timestamp.desc()).all()

    # Optional: Count critical alerts separately
    critical_alert_count = sum(1 for alert in alerts if alert.priority == 'Critical')

    return render_template(
        'lecturer_dashboard.html',
        alerts=alerts,
        critical_alert_count=critical_alert_count
    )

@app.route('/officer_dashboard')
def officer_dashboard():
    return render_template('officer_dashboard.html')

@app.route('/head_dashboard')
def head_dashboard():
    incidents = Incident.query.order_by(Incident.timestamp.desc()).all()
    return render_template('head_dashboard.html', incidents=incidents)

# ---------------- View Incidents for Security Officer ----------------
@app.route('/officer/incidents')
def officer_view_incidents():
    if 'username' not in session:
        return redirect(url_for('login'))

    officer = SecurityPersonnel.query.filter_by(username=session['username']).first()
    if not officer:
        flash("Security personnel record not found.")
        return redirect(url_for('officer_dashboard'))

    incidents = Incident.query.filter_by(assigned_officer_id=officer.id).all()
    return render_template('officer_view_incidents.html', incidents=incidents)

# ---------------- Update Severity ----------------
@app.route('/officer_dashboard/set_severity/<int:incident_id>', methods=['POST'])
def set_severity(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    severity = request.form['severity']
    incident.severity = severity

    if severity == "Critical":
        alert_message = f"CRITICAL INCIDENT: {incident.title} reported at {incident.location}. Please avoid the area."
        new_alert = Alert(
            message=alert_message,
            incident_id=incident.id,
            timestamp=datetime.now()
        )
        db.session.add(new_alert)

    db.session.commit()
    flash(f"Severity for incident '{incident.title}' updated.")
    return redirect(url_for('officer_view_incidents'))

# ---------------- Report Incident ----------------
@app.route('/report_incident', methods=['GET','POST'])
def report_incident():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        category = request.form.get('category')
        incident_date = request.form.get('incident_date')
        anonymous = request.form.get('anonymous')
        reported_by = None if anonymous else get_user_id()

        new_incident = Incident(
            title=title,
            description=description,
            location=location,
            category=category,
            incident_date=incident_date,
            reported_by=reported_by
        )
        db.session.add(new_incident)
        db.session.commit()
        flash("Incident reported successfully. Security has been notified.")
        return redirect(url_for('student_dashboard'))

    return render_template('report_incident.html')

@app.route('/lecturer_report_incident', methods=['GET', 'POST'])
def lecturer_report_incident():
    if request.method == 'POST':
        title = request.form['title']
        location = request.form['location']
        incident_date = request.form['incident_date']
        category = request.form['category']
        description = request.form['description']
        reported_by = get_user_id()

        new_incident = Incident(
            title=title,
            location=location,
            incident_date=incident_date,
            category=category,
            description=description,
            reported_by=reported_by,
            status="Pending"
        )
        db.session.add(new_incident)
        db.session.commit()
        flash("Incident reported successfully. Security has been notified")
        return redirect(url_for('lecturer_dashboard'))

    return render_template('lecturer_report_incident.html')

# ---------------- Attendance / Sign In & Sign Out ----------------
@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    username = session.get('username')
    role = session.get('role')

    if not username or role != 'Security Officer':
        flash("Please log in as Security Officer first")
        return redirect(url_for('login', role='Security Officer'))

    personnel = SecurityPersonnel.query.filter_by(username=username).first()
    if not personnel:
        flash("Personnel record not found. Contact admin.")
        return redirect(url_for('login', role='Security Officer'))

    if request.method == 'POST':
        campus = request.form.get('campus')
        action = request.form.get('action')

        today_record = Attendance.query.filter_by(personnel_id=personnel.id, date=date.today()).first()
        if not today_record:
            today_record = Attendance(personnel_id=personnel.id, date=date.today())
            db.session.add(today_record)

        if action == 'sign_in':
            today_record.sign_in_time = datetime.now()
            today_record.campus = campus
            personnel.status = 'On Duty'
            flash(f"Signed in at {today_record.sign_in_time.strftime('%H:%M:%S')} on {campus}")
        elif action == 'sign_out':
            today_record.sign_out_time = datetime.now()
            personnel.status = 'Off Duty'
            flash(f"Signed out at {today_record.sign_out_time.strftime('%H:%M:%S')}")

        db.session.commit()
        return redirect(url_for('attendance'))

    last_attendance = Attendance.query.filter_by(personnel_id=personnel.id).order_by(Attendance.date.desc()).first()
    return render_template('attendance.html', personnel=personnel, last_attendance=last_attendance)

# ---------------- Manage Security Officers ----------------
@app.route('/manage_officers', methods=['GET', 'POST'])
def manage_officers():
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    if request.method == 'POST':
        # Add new officer
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hire_date_str = request.form.get('hire_date')
        hire_date = datetime.strptime(hire_date_str, "%Y-%m-%d").date() if hire_date_str else None
        personnel_id = generate_personnel_id()

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create User account
        new_user = User(username=username, email=email, password=hashed_password, role="Security Officer")
        db.session.add(new_user)

        # Create SecurityPersonnel record
        new_officer = SecurityPersonnel(
            name=name,
            username=username,
            personnel_id=personnel_id,
            hire_date=hire_date,
            status="Off Duty"
        )
        db.session.add(new_officer)
        db.session.commit()

        flash(f"Security officer added successfully. Username: {username}, ID: {personnel_id}")
        return redirect(url_for('manage_officers'))

    # GET → display all officers
    officers_query = SecurityPersonnel.query.all()
    officers = []
    for officer in officers_query:
        # Latest attendance
        latest_attendance = Attendance.query.filter_by(personnel_id=officer.id)\
                            .order_by(Attendance.date.desc()).first()
        campus = latest_attendance.campus if latest_attendance and latest_attendance.sign_in_time and not latest_attendance.sign_out_time else None

        # Get email
        user_account = User.query.filter_by(username=officer.username).first()
        email = user_account.email if user_account else "N/A"

        officers.append({
            "officer": officer,
            "campus": campus,
            "email": email
        })

    # **This must be at the very end**
    return render_template('manage_officers.html', officers=officers)

# ---------------- Remove Officer ----------------
@app.route('/remove_officer/<int:officer_id>', methods=['POST'])
def remove_officer(officer_id):
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login'))

    officer = SecurityPersonnel.query.get_or_404(officer_id)
    user_account = User.query.filter_by(username=officer.username).first()

    # Delete both personnel record and login
    db.session.delete(officer)
    if user_account:
        db.session.delete(user_account)

    db.session.commit()
    flash(f"Officer {officer.name} removed successfully.")
    return redirect(url_for('manage_officers'))

# ---------------- Update Incident Status ----------------
@app.route('/update_status/<int:incident_id>', methods=['POST'])
def update_status(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    new_status = request.form['status']
    incident.status = new_status

    if new_status == "Resolved":
        Alert.query.filter_by(incident_id=incident.id).delete()

    db.session.commit()
    flash("Incident status updated successfully.")
    return redirect(url_for('officer_view_incidents'))

# ---------------- View Incident Status (Students/Lecturers) ----------------
@app.route('/view_incident_status', methods=['GET'])
def view_incident_status():
    username = session.get('username')
    if not username:
        flash("Please login first")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found")
        return redirect(url_for('login'))

    # Only their own incidents
    query = Incident.query.filter_by(reported_by=user.id)

    # Filters
    status_filter = request.args.get('status')
    severity_filter = request.args.get('severity')
    category_filter = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if status_filter and status_filter != "All":
        query = query.filter_by(status=status_filter)
    if severity_filter and severity_filter != "All":
        query = query.filter_by(severity=severity_filter)
    if category_filter and category_filter != "All":
        query = query.filter_by(category=category_filter)
    if start_date:
        query = query.filter(Incident.incident_date >= start_date)
    if end_date:
        query = query.filter(Incident.incident_date <= end_date)

    incidents = query.order_by(Incident.incident_date.desc()).all()

    statuses = ["Pending", "In Progress", "Resolved"]
    severities = ["Minor", "Moderate", "Severe", "Critical"]
    categories = list({i.category for i in Incident.query.all()})

    return render_template(
        'view_incident_status.html',
        incidents=incidents,
        statuses=statuses,
        severities=severities,
        categories=categories,
        selected_status=status_filter or "All",
        selected_severity=severity_filter or "All",
        selected_category=category_filter or "All",
        start_date=start_date or "",
        end_date=end_date or ""
    )

# ---------------- Investigate Incident ----------------
@app.route('/investigate/<int:incident_id>', methods=['GET', 'POST'])
def investigate_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)

    if request.method == 'POST':
        # If incident was Pending and officer is submitting investigation, move to In Progress
        if incident.status == "Pending":
            incident.status = "In Progress"

        # Update investigation/resolution notes
        incident.investigation_notes = request.form.get('investigation_notes', incident.investigation_notes)
        incident.resolution_notes = request.form.get('resolution_notes', incident.resolution_notes)

        # Update status if officer selected Resolved (or keep In Progress)
        form_status = request.form.get('status')
        if form_status:
            incident.status = form_status

        db.session.commit()
        flash("Incident updated successfully.")
        return redirect(url_for('officer_view_incidents'))

    # GET request: just render page; do NOT auto-change status
    return render_template('investigate_incident.html', incident=incident)

# ---------------- Manage Incidents Page for Head of Security ----------------
@app.route('/manage_incidents')
def manage_incidents():
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    # Get all officers for assignment dropdown
    officers_query = SecurityPersonnel.query.all()
    officers = []
    for officer in officers_query:
        latest_attendance = Attendance.query.filter_by(personnel_id=officer.id).order_by(Attendance.date.desc()).first()
        campus = latest_attendance.campus if latest_attendance and latest_attendance.sign_in_time and not latest_attendance.sign_out_time else None
        officers.append({"officer": officer, "campus": campus})

    # Get all incidents
    incidents = Incident.query.order_by(Incident.timestamp.desc()).all()
    for incident in incidents:
        incident.reported_by_user = User.query.get(incident.reported_by) if incident.reported_by else None

    return render_template('incident_management.html', officers=officers, incidents=incidents)

# Assign Officer
@app.route('/assign_officer/<int:incident_id>', methods=['POST'])
def assign_officer(incident_id):
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    officer_id = request.form.get('officer_id')
    officer = SecurityPersonnel.query.get(officer_id)
    incident = Incident.query.get_or_404(incident_id)

    if officer:
        incident.assigned_officer_id = officer.id
        # Always reset status to Pending when newly assigned
        incident.status = "Pending"
        db.session.commit()
        flash(f"{officer.name} assigned to incident '{incident.title}' and status set to Pending")
    else:
        flash("Officer not found")

    return redirect(url_for('manage_incidents'))

# Update severity
@app.route('/update_incident_severity/<int:incident_id>', methods=['POST'])
def update_incident_severity(incident_id):
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    incident = Incident.query.get_or_404(incident_id)
    severity = request.form.get('severity')
    incident.severity = severity

    # Add alert if critical
    if severity == "Critical":
        alert_message = f"CRITICAL INCIDENT: {incident.title} at {incident.location}"
        new_alert = Alert(message=alert_message, incident_id=incident.id, timestamp=datetime.now())
        db.session.add(new_alert)

    db.session.commit()
    flash(f"Severity for incident '{incident.title}' updated.")
    return redirect(url_for('manage_incidents'))

# ---------------- View Critical Alerts (Student/Lecturer) ----------------
@app.route('/view_critical_alerts')
def view_critical_alerts():
    if 'username' not in session:
        flash("Please login first")
        return redirect(url_for('select_role'))

    role = session.get('role')
    if role not in ['Student', 'Lecturer', 'Security Officer']:
        flash("Access denied")
        return redirect(url_for('login'))

    # Get filter from query params
    status_filter = request.args.get('status', 'all')

    alerts_query = Alert.query.order_by(Alert.timestamp.desc())

    if status_filter == 'ongoing':
        alerts_query = alerts_query.join(Incident).filter(Incident.status != 'Resolved')
    elif status_filter == 'resolved':
        alerts_query = alerts_query.join(Incident).filter(Incident.status == 'Resolved')

    alerts = alerts_query.all()

    return render_template('view_critical_alerts.html', alerts=alerts, selected_status=status_filter)

# ---------------- Head of Security: Create Critical Alert ----------------
@app.route('/create_critical_alert', methods=['GET', 'POST'])
def create_critical_alert():
    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    # Fetch incidents for the dropdown
    incidents = Incident.query.order_by(Incident.timestamp.desc()).all()

    # Fetch previously created alerts
    previous_alerts = Alert.query.order_by(Alert.timestamp.desc()).all()

    if request.method == 'POST':
        message = request.form.get('message')
        if not message:
            flash("Alert message cannot be empty")
            return redirect(url_for('create_critical_alert'))

        # Get linked incident (optional)
        incident_id = request.form.get('incident_id') or None

        # Create the alert WITHOUT incident_title or incident_location
        new_alert = Alert(
            message=message,
            priority='Critical',
            incident_id=incident_id,
            timestamp=datetime.now(),
            recipient_id=None
        )

        db.session.add(new_alert)
        db.session.commit()

        flash("Critical alert created successfully.")
        return redirect(url_for('create_critical_alert'))

    return render_template(
        'create_critical_alert.html',
        incidents=incidents,
        previous_alerts=previous_alerts
    )

@app.route('/generate_report')
def generate_report():

    if session.get('role') != "Head of Security":
        flash("Access denied")
        return redirect(url_for('login', role='Head of Security'))

    incidents = Incident.query.all()

    # -------- Campus Counts --------
    campus_counts = {}
    for inc in incidents:
        campus = inc.location if inc.location else "Unknown"
        campus_counts[campus] = campus_counts.get(campus, 0) + 1

    # -------- Category Counts --------
    category_counts = {}
    for inc in incidents:
        category = inc.category if inc.category else "Uncategorized"
        category_counts[category] = category_counts.get(category, 0) + 1

    # -------- Severity Counts --------
    severity_counts = {}
    for inc in incidents:
        severity = inc.severity if inc.severity else "Not Set"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    # -------- Status Counts (NEW CHART) --------
    status_counts = {
        "Pending": 0,
        "In Progress": 0,
        "Resolved": 0
    }

    for inc in incidents:
        if inc.status in status_counts:
            status_counts[inc.status] += 1

    return render_template(
        "generate_reports.html",
        campus_counts=campus_counts,
        category_counts=category_counts,
        severity_counts=severity_counts,
        status_counts=status_counts
    )



# ---------------- Run App ----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


