# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = '#$%@#$%^90808792##'

# db config

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tickets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Token missing"}), 401

        try:
            token = token.split(" ")[1]  # Bearer <token>

            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user_id = data["user_id"]

        except Exception:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated

# ---------------- MODEL ----------------
#ticket
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    priority = db.Column(db.String(50), default="LOW")
    status = db.Column(db.String(50), default="OPEN")
#user
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# ---------------- HELPERS ----------------
def ticket_to_dict(ticket):
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status
    }

# ---------------- VALIDATION ----------------
ALLOWED_STATUSES = ["OPEN", "IN_PROGRESS", "DONE"]
ALLOWED_PRIORITIES = ["LOW", "MEDIUM", "HIGH"]

def validate_ticket(data):
    if not data.get("title"):
        return "Title is required"

    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        return "Invalid status"

    if "priority" in data and data["priority"] not in ALLOWED_PRIORITIES:
        return "Invalid priority"

    return None


tickets = []

# CREATE
@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    data = request.json or {}

    error = validate_ticket(data)
    if error:
        return jsonify({"error": error}), 400

    ticket = Ticket(
        title=data.get("title"),
        description=data.get("description"),
        priority=data.get("priority", "LOW"),
        status=data.get("status", "OPEN")
    )

    db.session.add(ticket)
    db.session.commit()

    return jsonify(ticket_to_dict(ticket)), 201

# READ ALL
@app.route("/api/tickets", methods=["GET"])
@token_required
def get_tickets():
    tickets = Ticket.query.all()
    return jsonify([ticket_to_dict(t) for t in tickets])


# UPDATE (status / fields)
@app.route("/api/tickets/<int:id>", methods=["PATCH"])
def update_ticket(id):
    data = request.json or {}

    ticket = Ticket.query.get(id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    # validate incoming fields
    error = validate_ticket({**ticket_to_dict(ticket), **data})
    if error:
        return jsonify({"error": error}), 400

    # update allowed fields only
    if "title" in data:
        ticket.title = data["title"]

    if "description" in data:
        ticket.description = data["description"]

    if "priority" in data:
        ticket.priority = data["priority"]

    if "status" in data:
        ticket.status = data["status"]

    db.session.commit()

    return jsonify(ticket_to_dict(ticket))

# DELETE
@app.route("/api/tickets/<int:id>", methods=["DELETE"])
def delete_ticket(id):
    ticket = Ticket.query.get(id)

    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    db.session.delete(ticket)
    db.session.commit()

    return jsonify({"message": "Ticket deleted successfully"})

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}

    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username & password required"}), 400

    existing = User.query.filter_by(username=data["username"]).first()
    if existing:
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(data["password"])

    user = User(
        username=data["username"],
        password=hashed_password
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json or {}

    user = User.query.filter_by(username=data.get("username")).first()

    if not user or not check_password_hash(user.password, data.get("password")):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({"token": token})

if __name__ == "__main__":
    app.run(debug=True)