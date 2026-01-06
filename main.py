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

# Configure database path (can be overridden via environment variable)
DB_PATH = os.environ.get("DB_PATH", "database.db")

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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        while True:
            event_id = generate_short_id(6)
            cursor.execute("SELECT eventId FROM EVENTS WHERE eventId = ?", (event_id,))
            if not cursor.fetchone():
                return event_id

def get_client_ip():
    """Get the client's IP address from the request"""
    # Try to get the real IP from headers (in case behind proxy)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


"""connect = sqlite3.connect("database.db")
connect.execute("DROP TABLE USERS")"""

# Database initialization and migration
def init_database():
    """Initialize database tables and run migrations"""
    connect = sqlite3.connect(DB_PATH)
    cursor = connect.cursor()

    # Create base tables
    cursor.execute("CREATE TABLE IF NOT EXISTS USERS (userId TEXT, name TEXT, surname TEXT, email TEXT, password TEXT)")

    cursor.execute("""CREATE TABLE IF NOT EXISTS EVENTS (
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
        createdAt TEXT,
        votingDeadline TEXT,
        deadlineTimezone TEXT
    )""")

    # Create PARTICIPANTS table (without ipAddress initially for migration)
    cursor.execute("""CREATE TABLE IF NOT EXISTS PARTICIPANTS (
        participantId TEXT PRIMARY KEY,
        eventId TEXT,
        name TEXT,
        joinedAt TEXT,
        FOREIGN KEY (eventId) REFERENCES EVENTS(eventId)
    )""")

    # Check if ipAddress column exists in PARTICIPANTS
    cursor.execute("PRAGMA table_info(PARTICIPANTS)")
    participant_columns = [row[1] for row in cursor.fetchall()]
    if 'ipAddress' not in participant_columns:
        print("Running migration: Adding ipAddress column to PARTICIPANTS...")
        cursor.execute("ALTER TABLE PARTICIPANTS ADD COLUMN ipAddress TEXT DEFAULT '0.0.0.0'")
        print("✓ Migration completed")

    cursor.execute("""CREATE TABLE IF NOT EXISTS VOTES (
        voteId TEXT PRIMARY KEY,
        eventId TEXT,
        participantId TEXT,
        timeSlot TEXT,
        FOREIGN KEY (eventId) REFERENCES EVENTS(eventId),
        FOREIGN KEY (participantId) REFERENCES PARTICIPANTS(participantId)
    )""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS BLOCKED_USERS (
        blockId TEXT PRIMARY KEY,
        eventId TEXT,
        ipAddress TEXT,
        participantName TEXT,
        blockedAt TEXT,
        FOREIGN KEY (eventId) REFERENCES EVENTS(eventId)
    )""")

    connect.commit()
    connect.close()

# Run database initialization
init_database()


@app.route("/createUser", methods=["POST"])
def create_user():
    if request.is_json:
        payload = dict(request.get_json())
        user_id = str(uuid.uuid4())
        name = payload.get("name")
        surname = payload.get("surname")
        email = payload.get("email")
        password = sha256(str(payload.get("password")).encode("utf-8")).hexdigest()
        with sqlite3.connect(DB_PATH) as users:
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
    connect = sqlite3.connect(DB_PATH)
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

        connect = sqlite3.connect(DB_PATH)
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
        voting_deadline = payload.get("votingDeadline")  # Optional ISO timestamp in UTC
        deadline_timezone = payload.get("deadlineTimezone")  # Optional organizer's timezone

        print(f"[DEBUG] Creating event with deadline: {voting_deadline}, timezone: {deadline_timezone}")
        print(f"[DEBUG] Full payload: {payload}")

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO EVENTS (eventId, title, type, selectedDates, selectedDays, startTime, endTime, timezone, organizerName, isFinalized, finalizedTime, createdAt, votingDeadline, deadlineTimezone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)""",
                (event_id, title, event_type, selected_dates, selected_days, start_time, end_time, timezone, organizer_name, created_at, voting_deadline, deadline_timezone)
            )
            conn.commit()

        return jsonify({"eventId": event_id, "message": "Event created successfully"}), 201
    else:
        return jsonify({"error": "Request body must be json"}), 400


@app.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT eventId, title, type, selectedDates, selectedDays, startTime, endTime, timezone,
                   organizerName, isFinalized, finalizedTime, createdAt, votingDeadline, deadlineTimezone
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
                "createdAt": row[11],
                "votingDeadline": row[12],
                "deadlineTimezone": row[13]
            }
            return jsonify(event), 200
        else:
            return jsonify({"error": "Event not found"}), 404


@app.route("/events/<event_id>/participants", methods=["GET"])
def get_participants(event_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT participantId, name, ipAddress, joinedAt FROM PARTICIPANTS WHERE eventId = ?", (event_id,))
        rows = cursor.fetchall()

        participants = [{"participantId": row[0], "name": row[1], "ipAddress": row[2], "joinedAt": row[3]} for row in rows]
        return jsonify(participants), 200


@app.route("/events/<event_id>/participants", methods=["POST"])
def add_participant(event_id):
    if request.is_json:
        payload = dict(request.get_json())
        name = payload.get("name")
        ip_address = get_client_ip()
        joined_at = datetime.utcnow().isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if this IP is blocked for this event
            cursor.execute(
                "SELECT blockId FROM BLOCKED_USERS WHERE eventId = ? AND ipAddress = ?",
                (event_id, ip_address)
            )
            if cursor.fetchone():
                return jsonify({"error": "You have been blocked from this event"}), 403

            participant_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO PARTICIPANTS (participantId, eventId, name, ipAddress, joinedAt) VALUES (?, ?, ?, ?, ?)",
                (participant_id, event_id, name, ip_address, joined_at)
            )
            conn.commit()

        # Emit WebSocket event to all clients in this event room
        socketio.emit('participant_joined', {
            'participantId': participant_id,
            'name': name,
            'ipAddress': ip_address,
            'joinedAt': joined_at
        }, room=event_id)

        return jsonify({"participantId": participant_id, "message": "Participant added successfully"}), 201
    else:
        return jsonify({"error": "Request body must be json"}), 400


@app.route("/events/<event_id>/votes", methods=["GET"])
def get_votes(event_id):
    with sqlite3.connect(DB_PATH) as conn:
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

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check event status and deadline
            cursor.execute(
                "SELECT votingDeadline, isFinalized FROM EVENTS WHERE eventId = ?",
                (event_id,)
            )
            event_data = cursor.fetchone()

            if not event_data:
                return jsonify({"error": "Event not found"}), 404

            voting_deadline, is_finalized = event_data

            # Check if event is finalized
            if is_finalized:
                return jsonify({"error": "Voting is closed - event has been finalized"}), 403

            # Check if voting deadline has passed
            if voting_deadline:
                try:
                    deadline_dt = datetime.fromisoformat(voting_deadline.replace('Z', '+00:00'))
                    now_utc = datetime.utcnow()

                    if now_utc > deadline_dt:
                        return jsonify({"error": "Voting deadline has passed"}), 403
                except Exception as e:
                    print(f"Error parsing deadline: {e}")

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

        with sqlite3.connect(DB_PATH) as conn:
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


@app.route("/events/<event_id>/participants/<participant_id>/votes", methods=["GET"])
def get_participant_votes(event_id, participant_id):
    """Get votes for a specific participant"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timeSlot FROM VOTES WHERE eventId = ? AND participantId = ?",
            (event_id, participant_id)
        )
        rows = cursor.fetchall()

        time_slots = [row[0] for row in rows]
        return jsonify({"timeSlots": time_slots}), 200


@app.route("/events/<event_id>/block", methods=["POST"])
def block_user(event_id):
    """Block a user from an event by their IP address"""
    if request.is_json:
        payload = dict(request.get_json())
        participant_id = payload.get("participantId")

        if not participant_id:
            return jsonify({"error": "participantId is required"}), 400

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get participant's IP address and name
            cursor.execute(
                "SELECT ipAddress, name FROM PARTICIPANTS WHERE participantId = ? AND eventId = ?",
                (participant_id, event_id)
            )
            participant = cursor.fetchone()

            if not participant:
                return jsonify({"error": "Participant not found"}), 404

            ip_address = participant[0]
            participant_name = participant[1]

            # Check if already blocked
            cursor.execute(
                "SELECT blockId FROM BLOCKED_USERS WHERE eventId = ? AND ipAddress = ?",
                (event_id, ip_address)
            )
            if cursor.fetchone():
                return jsonify({"error": "User is already blocked"}), 400

            # Add to blocked users
            block_id = str(uuid.uuid4())
            blocked_at = datetime.utcnow().isoformat()
            cursor.execute(
                "INSERT INTO BLOCKED_USERS (blockId, eventId, ipAddress, participantName, blockedAt) VALUES (?, ?, ?, ?, ?)",
                (block_id, event_id, ip_address, participant_name, blocked_at)
            )

            # Get all participant IDs with this IP before deletion
            cursor.execute(
                "SELECT participantId FROM PARTICIPANTS WHERE eventId = ? AND ipAddress = ?",
                (event_id, ip_address)
            )
            participant_ids = [row[0] for row in cursor.fetchall()]

            # Delete all votes from participants with this IP
            for pid in participant_ids:
                cursor.execute(
                    "DELETE FROM VOTES WHERE eventId = ? AND participantId = ?",
                    (event_id, pid)
                )

            # Delete all participants with this IP from this event
            cursor.execute(
                "DELETE FROM PARTICIPANTS WHERE eventId = ? AND ipAddress = ?",
                (event_id, ip_address)
            )

            conn.commit()

        # Emit WebSocket event to notify all clients
        socketio.emit('user_blocked', {
            'participantId': participant_id,
            'participantName': participant_name,
            'ipAddress': ip_address
        }, room=event_id)

        return jsonify({"message": "User blocked successfully"}), 200
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
