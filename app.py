# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from dotenv import load_dotenv
import os
from flask_migrate import Migrate

load_dotenv()
port = int(os.environ.get("PORT", 5000))

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = '#$%@#$%^90808792##'

# db config

uri = os.getenv("DATABASE_URL")
if not uri:
    raise Exception("DB URL missing")

if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri

print(os.getenv("DATABASE_URL"))
print(os.getenv("DATABASE_PUBLIC_URL"))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

def is_admin(user):
    return user.role in ["admin", "super_admin"]

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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String, default="user")

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

# get users
@app.route("/api/users", methods=["GET"])
@token_required
def get_users():
    current_user = User.query.get(request.user_id)

   
    if not is_admin(current_user):
        return jsonify({"error": "Access denied"}), 403

    users = User.query.all()

    result = []
    for u in users:
        result.append({
            "id": u.id,
            "username": u.username,
            "role": u.role
        })

    return jsonify(result)

#promote 
@app.route("/api/users/<int:id>/make-admin", methods=["PATCH"])
@token_required
def make_admin(id):
    current_user = User.query.get(request.user_id)
    user = User.query.get(id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # ❌ only admin or super admin
    if not is_admin(current_user):
        return jsonify({"error": "Access denied"}), 403

    # ❌ cannot modify super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot modify super admin"}), 403

    user.role = "admin"
    db.session.commit()

    return jsonify({"message": "User promoted"})

# CREATE
@app.route("/api/tickets", methods=["POST"])
@token_required
def create_ticket():
    data = request.json or {}

    error = validate_ticket(data)
    if error:
        return jsonify({"error": error}), 400

    ticket = Ticket(
        title=data.get("title"),
        description=data.get("description"),
        priority=data.get("priority", "LOW"),
        status=data.get("status", "OPEN"),
        user_id=request.user_id
    )

    db.session.add(ticket)
    db.session.commit()

    return jsonify(ticket_to_dict(ticket)), 201

# READ ALL
@app.route("/api/tickets", methods=["GET"])
@token_required
def get_tickets():
    user = User.query.get(request.user_id)

    if user.role == "admin":
        tickets = Tickets.query.all()
    else:
        tickets = Ticket.query.filter_by(user_id=request.user_id).all()

    return jsonify([ticket_to_dict(t) for t in tickets])


# UPDATE (status / fields)
@app.route("/api/tickets/<int:id>", methods=["PATCH"])
@token_required
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
@app.route("/api/users/<int:id>", methods=["DELETE"])
@token_required
def delete_user(id):
    current_user = User.query.get(request.user_id)
    user = User.query.get(id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # ❌ only admin or super admin
    if not is_admin(current_user):
        return jsonify({"error": "Access denied"}), 403

    # ❌ cannot delete super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot delete super admin"}), 403

    # ❌ prevent self delete
    if user.id == current_user.id:
        return jsonify({"error": "Cannot delete yourself"}), 400

    # ❌ prevent last admin removal
    admin_count = User.query.filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    if user.role in ["admin", "super_admin"] and admin_count <= 1:
        return jsonify({"error": "At least one admin required"}), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "User deleted"})

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}

    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username & password required"}), 400

    existing = User.query.filter_by(username=data["username"]).first()
    if existing:
        return jsonify({"error": "User already exists"}), 409

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

    return jsonify({"token": token, "role": user.role})

@app.route("/api/users/<int:id>/demote", methods=["PATCH"])
@token_required
def demote_user(id):
    current_user = User.query.get(request.user_id)
    user = User.query.get(id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # ❌ only admin or super admin
    if not is_admin(current_user):
        return jsonify({"error": "Access denied"}), 403

    # ❌ cannot modify super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot modify super admin"}), 403

    # ❌ prevent last admin removal
    admin_count = User.query.filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    if admin_count <= 1:
        return jsonify({"error": "At least one admin required"}), 400

    user.role = "user"
    db.session.commit()

    return jsonify({"message": "User demoted"})

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=port)