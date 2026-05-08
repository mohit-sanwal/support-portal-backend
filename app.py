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
from sqlalchemy import or_

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

def is_admin_or_superAdmin(user):
    return user.role in ["admin", "super_admin"]

def is_super_admin(user):
    return user.role == "super_admin"

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

def can_comment(user, ticket):

    assignment = TicketAssignment.query.filter_by(
        ticket_id=ticket.id
    ).order_by(TicketAssignment.id.desc()).first()

    # assigned user
    if assignment and assignment.assigned_to == user.id:
        return True

    # admin/super admin
    if user.role in ["admin", "super_admin"]:
        return True

    # ticket creator
    if ticket.user_id == user.id:
        return True

    return False

def build_comment_tree(comments):
    comment_map = {}
    root = []

    for c in comments:
        user = User.query.get(c.user_id)   # 👈 fetch user

        node = {
            "id": c.id,
            "content": c.content,
            "user_id": c.user_id,
            "username": user.username if user else "Unknown",
            "parent_id": c.parent_id,
            "created_at": c.created_at.isoformat(),  # 👈 stringify
            "replies": []
        }
        comment_map[c.id] = node

    for c in comments:
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id]["replies"].append(comment_map[c.id])
        else:
            root.append(comment_map[c.id])

    return root


def can_manage_comment(current_user, comment):

    # super admin can manage all
    if current_user.role == "super_admin":
        return True

    # everyone else only own comment
    return comment.user_id == current_user.id

def can_delete_ticket(current_user, ticket):

    # own ticket
    if ticket.user_id == current_user.id:
        return True

    ticket_owner = User.query.get(ticket.user_id)

    if not ticket_owner:
        return False

    # super admin → all access
    if current_user.role == "super_admin":
        return True

    # admin → only normal users tickets
    if (
        current_user.role == "admin" and
        ticket_owner.role == "user"
    ):
        return True

    return False

# ---------------- MODEL ----------------
#ticket
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    priority = db.Column(db.String(50), default="LOW")
    status = db.Column(db.String(50), default="OPEN")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    comments = db.relationship(
        "Comment",
        backref="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    assignments = db.relationship(
        "TicketAssignment",
        backref="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String, default="user")
    can_assign = db.Column(db.Boolean, default=False)

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("ticket.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class TicketAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("ticket.id", ondelete="CASCADE"),
        nullable=False
    )
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ---------------- HELPERS ----------------
def ticket_to_dict(ticket):

    creator = User.query.get(ticket.user_id)

    latest_assignment = TicketAssignment.query.filter_by(
        ticket_id=ticket.id
    ).order_by(TicketAssignment.id.desc()).first()

    assigned_user = None
    assigned_by_user = None

    if latest_assignment:
        assigned_user = User.query.get(latest_assignment.assigned_to)
        assigned_by_user = User.query.get(latest_assignment.assigned_by)

    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status,

        # creator
        "created_by": ticket.user_id,
        "created_by_name": creator.username if creator else "Unknown",
        "created_by_role": creator.role if creator else None,
        "created_at": (
            ticket.created_at.isoformat()
            if ticket.created_at
            else None
        ),

        # assignment
        "assigned_to": (
            latest_assignment.assigned_to
            if latest_assignment
            else None
        ),

        "assigned_to_name": (
            assigned_user.username
            if assigned_user
            else None
        ),

        "assigned_by": (
            latest_assignment.assigned_by
            if latest_assignment
            else None
        ),

        "assigned_by_name": (
            assigned_by_user.username
            if assigned_by_user
            else None
        )
    }

def can_user_assign(current_user):
    if current_user.role in ["admin", "super_admin"]:
        return True
    return current_user.can_assign

# ---------------- VALIDATION ----------------
ALLOWED_STATUSES = [
    "OPEN",
    "IN_PROGRESS",
    "IN_REVIEW",
    "IN_QE",
    "DONE"
]
ALLOWED_PRIORITIES = ["LOW", "MEDIUM", "HIGH"]

def validate_ticket(data):
    if not data.get("title"):
        return "Title is required"

    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        return "Invalid status"

    if "priority" in data and data["priority"] not in ALLOWED_PRIORITIES:
        return "Invalid priority"

    return None


@app.route("/api/auth/current-user", methods=["GET"])
@token_required
def current_user():
    user = User.query.get(request.user_id)
    return jsonify({
        "id": user.id,
        "username": user.username,
        "role": user.role
    })

# get users
@app.route("/api/users", methods=["GET"])
@token_required
def get_users():
    current_user = User.query.get(request.user_id)

    if not is_admin_or_superAdmin(current_user):
        return jsonify({"error": "Access denied"}), 403

    users = User.query.order_by(
        User.id.desc()
    ).all()

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

    # only admin or super admin
    if not is_admin_or_superAdmin(current_user):
        return jsonify({"error": "Access denied"}), 403

    # cannot modify super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot modify super admin"}), 403

    user.role = "admin"
    db.session.commit()

    return jsonify({"message": "User promoted"})

# CREATE
@app.route("/api/create-ticket", methods=["POST"])
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

# READ ALL TICKETS
@app.route("/api/tickets", methods=["GET"])
@token_required
def get_tickets():
    current_user = User.query.get(request.user_id)
    # admin/super admin → all tickets
    if is_admin_or_superAdmin(current_user):
        tickets = Ticket.query.order_by(Ticket.created_at.desc(), Ticket.id.desc()).all()
    else:
        # tickets assigned to current user
        assigned_ticket_ids = db.session.query(
            TicketAssignment.ticket_id
        ).filter(
            TicketAssignment.assigned_to == current_user.id
        ).distinct()

        tickets = Ticket.query.filter(
            or_(
                # own unassigned tickets
                (
                    (Ticket.user_id == current_user.id)
                ),

                # assigned tickets
                Ticket.id.in_(assigned_ticket_ids)
            )
        ).order_by(
            Ticket.created_at.desc(), Ticket.id.desc()
        ).all()

        # remove tickets reassigned to others
        filtered = []

        for t in tickets:

            latest_assignment = TicketAssignment.query.filter_by(
                ticket_id=t.id
            ).order_by(TicketAssignment.id.desc()).first()

            # no assignment → creator can see
            if not latest_assignment:
                filtered.append(t)

            # assigned to current user
            elif latest_assignment.assigned_to == current_user.id:
                filtered.append(t)

        tickets = filtered

    return jsonify([ticket_to_dict(t) for t in tickets])

#DELETE TICKET
@app.route("/api/tickets/<int:id>", methods=["DELETE"])
@token_required
def delete_ticket(id):
    current_user = User.query.get(request.user_id)
    ticket = Ticket.query.get(id)

    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    if not can_delete_ticket(current_user, ticket):
        return jsonify({"error": "Access denied"}), 403

    db.session.delete(ticket)
    db.session.commit()

    return jsonify({"message": "Ticket deleted successfully"})


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

# DELETE USER
@app.route("/api/users/<int:id>", methods=["DELETE"])
@token_required
def delete_user(id):
    current_user = User.query.get(request.user_id)
    user = User.query.get(id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # only super admin allowed
    if not is_super_admin(current_user):
        return jsonify({"error": "Only super admin allowed"}), 403

    # cannot delete super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot delete super admin"}), 403

    # prevent self delete
    if user.id == current_user.id:
        return jsonify({"error": "Cannot delete yourself"}), 400

    # prevent last admin removal
    admin_count = User.query.filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    if user.role in ["admin"] and admin_count <= 1:
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

@app.route("/api/users/<int:id>/make-user", methods=["PATCH"])
@token_required
def make_user(id):
    current_user = User.query.get(request.user_id)
    user = User.query.get(id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # only super admin allowed
    if not is_super_admin(current_user):
        return jsonify({"error": "Only super admin allowed"}), 403

    # cannot modify super admin
    if user.role == "super_admin":
        return jsonify({"error": "Cannot modify super admin"}), 403

    # prevent last admin removal
    admin_count = User.query.filter(
        User.role.in_(["admin", "super_admin"])
    ).count()

    if user.role in ["admin"] and admin_count <= 1:
        return jsonify({"error": "At least one admin required"}), 400

    user.role = "user"
    db.session.commit()

    return jsonify({"message": "Role converted to user"})

@app.route("/api/tickets/<int:id>/assign", methods=["POST"])
@token_required
def assign_ticket(id):

    current_user = User.query.get(request.user_id)

    data = request.json or {}

    if current_user.role not in ["admin", "super_admin"]:
        return jsonify({"error": "Access denied"}), 403

    ticket = Ticket.query.get(id)

    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    assigned_to = data.get("assigned_to")

    if not assigned_to:
        return jsonify({"error": "assigned_to is required"}), 400

    user = User.query.get(assigned_to)

    if not user:
        return jsonify({"error": "Assigned user not found"}), 404

    assignment = TicketAssignment(
        ticket_id=id,
        assigned_to=assigned_to,
        assigned_by=current_user.id
    )

    db.session.add(assignment)
    db.session.commit()

    return jsonify({"message": "Ticket assigned"})


@app.route("/api/tickets/<int:id>/assignment", methods=["GET"])
@token_required
def get_assignment(id):
    assignment = TicketAssignment.query.filter_by(ticket_id=id).order_by(TicketAssignment.id.desc()).first()

    if not assignment:
        return jsonify({"assigned_to": None})

    user = User.query.get(assignment.assigned_to)

    return jsonify({
        "assigned_to": assignment.assigned_to,
        "assigned_to_name": user.username if user else "Unknown"
    })

@app.route("/api/users/assignable", methods=["GET"])
@token_required
def get_assignable_users():
    current_user = User.query.get(request.user_id)

    # no permission → empty list
    if not can_user_assign(current_user):
        return jsonify([])

    if current_user.role == "super_admin":
        users = User.query.all()

    elif current_user.role == "admin":
        users = User.query.filter(User.role != "super_admin").all()

    else:
        # user → only self
        users = [current_user]

    return jsonify([
        {
            "id": u.id,
            "username": u.username,
            "role": u.role
        } for u in users
    ])

@app.route("/api/tickets/<int:ticket_id>/comments", methods=["POST"])
@token_required
def add_comment(ticket_id):
    data = request.json or {}
    user = User.query.get(request.user_id)

    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    if not can_comment(user, ticket):
        return jsonify({"error": "Access denied"}), 403

    comment = Comment(
        content=data.get("content"),
        ticket_id=ticket_id,
        user_id=user.id,
        parent_id=data.get("parent_id")  # for reply
    )

    db.session.add(comment)
    db.session.commit()

    return jsonify({"message": "Comment added"})

@app.route("/api/tickets/<int:ticket_id>/comments", methods=["GET"])
@token_required
def get_comments(ticket_id):
    comments = Comment.query.filter_by(ticket_id=ticket_id).order_by(Comment.created_at.asc()).all()

    tree = build_comment_tree(comments)

    return jsonify(tree)

@app.route("/api/comments/<int:id>", methods=["DELETE"])
@token_required
def delete_comment(id):
    user = User.query.get(request.user_id)
    comment = Comment.query.get(id)

    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    # permission check
    if user.role not in ["admin", "super_admin"] and comment.user_id != user.id:
        return jsonify({"error": "Access denied"}), 403

    # NEW RULE: check replies exist
    has_replies = Comment.query.filter_by(parent_id=comment.id).first()

    if has_replies:
        comment.content = "[deleted]"
        db.session.commit()
        return jsonify({"message": "Comment marked as deleted"})

    db.session.delete(comment)
    db.session.commit()

    return jsonify({"message": "Comment deleted"})

@app.route("/api/comments/<int:id>", methods=["PATCH"])
@token_required
def update_comment(id):
    user = User.query.get(request.user_id)
    comment = Comment.query.get(id)

    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    # permission
    if not can_manage_comment(user, comment):
        return jsonify({"error": "Access denied"}), 403
    data = request.json or {}

    if not data.get("content"):
        return jsonify({"error": "Content required"}), 400

    comment.content = data["content"]
    db.session.commit()

    return jsonify({"message": "Comment updated"})

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=port)