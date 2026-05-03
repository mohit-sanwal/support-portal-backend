# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
CORS(app)

# db config

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tickets.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- MODEL ----------------
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    priority = db.Column(db.String(50), default="LOW")
    status = db.Column(db.String(50), default="OPEN")

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



if __name__ == "__main__":
    app.run(debug=True)