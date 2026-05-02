# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

tickets = []

@app.route("/api/tickets", methods=["GET"])
def get_tickets():
    return jsonify(tickets)

@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    data = request.json
    ticket = {
        "id": len(tickets) + 1,
        "title": data["title"],
        "status": "OPEN"
    }
    tickets.append(ticket)
    return jsonify(ticket)

if __name__ == "__main__":
    app.run(debug=True)