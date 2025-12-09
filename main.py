from flask import Flask, request, make_response, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
from hashlib import sha256
import uuid
import json
import random
import string
from datetime import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")


@app.route("/")
@app.route("/home")
def index():
    return {"message": "Hello World!"}


@app.route("/healthcheck", methods=["GET"])
def healthcheck():
    return "event-scheduling-api is up!", 200


def generate_short_id(length=6):
    """Generate a short, readable event ID"""
    characters = string.ascii_uppercase + string.digits
    # Exclude similar looking characters: 0/O, 1/I/L
    characters = characters.replace('0', '').replace('O', '').replace('1', '').replace('I', '').replace('L', '')
    return ''.join(random.choice(characters) for _ in range(length))

def get_unique_event_id():
    """Generate a unique short event ID"""
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        while True:
            event_id = generate_short_id(6)
            cursor.execute("SELECT eventId FROM EVENTS WHERE eventId = ?", (event_id,))
            if not cursor.fetchone():
                return event_id


"""connect = sqlite3.connect("database.db")
connect.execute("DROP TABLE USERS")"""
connect = sqlite3.connect("database.db")
connect.execute("CREATE TABLE IF NOT EXISTS USERS (userId TEXT, name TEXT, surname TEXT, email TEXT, password TEXT)")
connect.execute("""CREATE TABLE IF NOT EXISTS EVENTS (
    eventId TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    selectedDates TEXT,
    selectedDays TEXT,
    startTime TEXT,
    endTime TEXT,
    timezone TEXT,
    organizerName TEXT,
    isFinalized INTEGER DEFAULT 0,
    finalizedTime TEXT,
    createdAt TEXT
)""")
connect.execute("""CREATE TABLE IF NOT EXISTS PARTICIPANTS (
    participantId TEXT PRIMARY KEY,
    eventId TEXT,
    name TEXT,
    joinedAt TEXT,
    FOREIGN KEY (eventId) REFERENCES EVENTS(eventId)
)""")
connect.execute("""CREATE TABLE IF NOT EXISTS VOTES (
    voteId TEXT PRIMARY KEY,
    eventId TEXT,
    participantId TEXT,
    timeSlot TEXT,
    FOREIGN KEY (eventId) REFERENCES EVENTS(eventId),
    FOREIGN KEY (participantId) REFERENCES PARTICIPANTS(participantId)
)""")


@app.route("/createUser", methods=["POST"])
def create_user():
    if request.is_json:
        payload = dict(request.get_json())
        user_id = str(uuid.uuid4())
        name = payload.get("name")
        surname = payload.get("surname")
        email = payload.get("email")
        password = sha256(str(payload.get("password")).encode("utf-8")).hexdigest()
        with sqlite3.connect("database.db") as users:
            cursor = users.cursor()
            cursor.execute(
                "INSERT INTO USERS (userId, name, surname, email, password) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, surname, email, password)
            )
            users.commit()
        return "OK", 200
    else:
        return "Request body must be json!", 500


@app.route("/users", methods=["GET"])
def get_users():
    connect = sqlite3.connect("database.db")
    cursor = connect.cursor()
    cursor.execute("SELECT name, surname, email FROM USERS")

    data = cursor.fetchall()
    return str(data), 200


@app.route("/login", methods=["POST"])
def login():
    if request.is_json:
        payload = dict(request.get_json())
        email = payload.get("email")
        password_from_user = sha256(str(payload.get("password")).encode("utf-8")).hexdigest()

        connect = sqlite3.connect("database.db")
        cursor = connect.cursor()
        cursor.execute("SELECT userId, password FROM USERS WHERE email = ?", (email,))
        data = cursor.fetchall()
        password_from_db = data[0][1]
        user_id = data[0][0]

        if password_from_user == password_from_db:
            resp = make_response()
            resp.set_cookie("session_id", user_id)
            return resp, 200
        else:
            return "Unauthorized", 401
    else:
        return "Request body must be json!", 500


@app.route("/events", methods=["POST"])
def create_event():
    if request.is_json:
        payload = dict(request.get_json())
        event_id = get_unique_event_id()
        title = payload.get("title", "Untitled Event")
        event_type = payload.get("type", "dates")
        selected_dates = json.dumps(payload.get("selectedDates", []))
        selected_days = json.dumps(payload.get("selectedDays", []))
        start_time = payload.get("startTime", "09:00")
        end_time = payload.get("endTime", "17:00")
        timezone = payload.get("timezone", "UTC")
        organizer_name = payload.get("organizerName", "Anonymous")
        created_at = datetime.utcnow().isoformat()

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO EVENTS (eventId, title, type, selectedDates, selectedDays, startTime, endTime, timezone, organizerName, isFinalized, finalizedTime, createdAt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)""",
                (event_id, title, event_type, selected_dates, selected_days, start_time, end_time, timezone, organizer_name, created_at)
            )
            conn.commit()

        return jsonify({"eventId": event_id, "message": "Event created successfully"}), 201
    else:
        return jsonify({"error": "Request body must be json"}), 400


@app.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT eventId, title, type, selectedDates, selectedDays, startTime, endTime, timezone,
                   organizerName, isFinalized, finalizedTime, createdAt
            FROM EVENTS WHERE eventId = ?
        """, (event_id,))
        row = cursor.fetchone()

        if row:
            event = {
                "eventId": row[0],
                "title": row[1],
                "type": row[2],
                "selectedDates": json.loads(row[3]) if row[3] else [],
                "selectedDays": json.loads(row[4]) if row[4] else [],
                "startTime": row[5],
                "endTime": row[6],
                "timezone": row[7],
                "organizerName": row[8],
                "isFinalized": bool(row[9]),
                "finalizedTime": row[10],
                "createdAt": row[11]
            }
            return jsonify(event), 200
        else:
            return jsonify({"error": "Event not found"}), 404


@app.route("/events/<event_id>/participants", methods=["GET"])
def get_participants(event_id):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT participantId, name, joinedAt FROM PARTICIPANTS WHERE eventId = ?", (event_id,))
        rows = cursor.fetchall()

        participants = [{"participantId": row[0], "name": row[1], "joinedAt": row[2]} for row in rows]
        return jsonify(participants), 200


@app.route("/events/<event_id>/participants", methods=["POST"])
def add_participant(event_id):
    if request.is_json:
        payload = dict(request.get_json())
        participant_id = str(uuid.uuid4())
        name = payload.get("name")
        joined_at = datetime.utcnow().isoformat()

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO PARTICIPANTS (participantId, eventId, name, joinedAt) VALUES (?, ?, ?, ?)",
                (participant_id, event_id, name, joined_at)
            )
            conn.commit()

        # Emit WebSocket event to all clients in this event room
        socketio.emit('participant_joined', {
            'participantId': participant_id,
            'name': name,
            'joinedAt': joined_at
        }, room=event_id)

        return jsonify({"participantId": participant_id, "message": "Participant added successfully"}), 201
    else:
        return jsonify({"error": "Request body must be json"}), 400


@app.route("/events/<event_id>/votes", methods=["GET"])
def get_votes(event_id):
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT voteId, participantId, timeSlot FROM VOTES WHERE eventId = ?", (event_id,))
        rows = cursor.fetchall()

        votes = [{"voteId": row[0], "participantId": row[1], "timeSlot": row[2]} for row in rows]
        return jsonify(votes), 200


@app.route("/events/<event_id>/votes", methods=["POST"])
def add_vote(event_id):
    if request.is_json:
        payload = dict(request.get_json())
        participant_id = payload.get("participantId")
        time_slots = payload.get("timeSlots", [])

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            # Delete existing votes for this participant
            cursor.execute("DELETE FROM VOTES WHERE eventId = ? AND participantId = ?", (event_id, participant_id))

            # Insert new votes
            for time_slot in time_slots:
                vote_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO VOTES (voteId, eventId, participantId, timeSlot) VALUES (?, ?, ?, ?)",
                    (vote_id, event_id, participant_id, time_slot)
                )
            conn.commit()

            # Get updated vote counts
            cursor.execute("SELECT voteId, participantId, timeSlot FROM VOTES WHERE eventId = ?", (event_id,))
            rows = cursor.fetchall()
            votes = [{"voteId": row[0], "participantId": row[1], "timeSlot": row[2]} for row in rows]

        # Emit WebSocket event to all clients in this event room
        socketio.emit('votes_updated', {
            'votes': votes
        }, room=event_id)

        return jsonify({"message": "Votes recorded successfully"}), 201
    else:
        return jsonify({"error": "Request body must be json"}), 400


@app.route("/events/<event_id>/finalize", methods=["POST"])
def finalize_event(event_id):
    if request.is_json:
        payload = dict(request.get_json())
        finalized_time = payload.get("finalizedTime")

        if not finalized_time:
            return jsonify({"error": "finalizedTime is required"}), 400

        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE EVENTS SET isFinalized = 1, finalizedTime = ? WHERE eventId = ?",
                (finalized_time, event_id)
            )
            conn.commit()

        # Emit WebSocket event to all clients in this event room
        socketio.emit('event_finalized', {
            'finalizedTime': finalized_time
        }, room=event_id)

        return jsonify({"message": "Event finalized successfully", "finalizedTime": finalized_time}), 200
    else:
        return jsonify({"error": "Request body must be json"}), 400


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_event')
def handle_join_event(data):
    event_id = data.get('eventId')
    if event_id:
        join_room(event_id)
        print(f'Client joined event room: {event_id}')

@socketio.on('leave_event')
def handle_leave_event(data):
    event_id = data.get('eventId')
    if event_id:
        leave_room(event_id)
        print(f'Client left event room: {event_id}')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
