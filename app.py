import enum
import threading
from datetime import datetime, UTC, timedelta
from typing import Dict, TypedDict
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, rooms
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///messages.db"

db = SQLAlchemy(app)
socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")


sess_pool_timeout = timedelta(seconds=30)

MessageType = TypedDict(
    "MessageType",
    {
        "id": str,
        "chatId": str,
        "content": str,
        "sender": str,
        "receiver": str,
        "timestamp": str,
    },
)


SessionType = TypedDict(
    "SessionType", {"address": str, "sid": str, "timedelta": datetime}
)


class Session(db.Model):
    address = db.Column(db.String(30), primary_key=True)
    sid = db.Column(db.String(30), nullable=False)
    timedelta = db.Column(db.DateTime, default=datetime.now())

    def __init__(self, *args, data: SessionType) -> None:
        self.address = data["address"]
        self.sid = data["sid"]
        self.timedelta = data["timedelta"]


# # type {
# #   0: delivery report
# # }
# class Notification(db.Model):
#     type = Column("type", Integer, nullable=False)
#     address = db.Column(type_= String(30), nullable=False)
#     payload = Column("payload", String(30), nullable=False)

#     def __init__(self, type: int, address: str, payload: str) -> None:
#         self.type = type
#         self._address = address
#         self.payload = payload


class Message(db.Model):
    _id = db.Column("id", db.String(50), primary_key=True)
    chatId = db.Column(db.String(40), nullable=False)
    content = db.Column(db.Text, nullable=True)
    sender = db.Column(db.String(30), nullable=False)
    receiver = db.Column(db.String(30), nullable=False)
    timestamp = db.Column(db.String(30), default=datetime.now(UTC).__str__())

    def __init__(self, *arg, data: MessageType):
        self._id = data["id"]
        self.chatId = data["chatId"]
        self.content = data["content"]
        self.sender = data["sender"]
        self.receiver = data["receiver"]
        self.timestamp = data["timestamp"]

    def toJson(self) -> Dict[str, str]:
        return {
            "id": self._id,
            "chatId": self.chatId,
            "content": self.content,
            "sender": self.sender,
            "receiver": self.receiver,
            "timestamp": self.timestamp,
        }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/user-2")
def index2():
    return render_template("index2.html")


@socketio.on("connect")
def handle_connect():
    sid: str = request.sid  # type: ignore
    address: str | None = request.headers.get("user")
    if address is not None:

        if db.session.query(Session).get(address) is None:
            db.session.add(
                Session(
                    data={"address": address, "sid": sid, "timedelta": datetime.now()}
                )
            )
        else:
            db.session.query(Session).update(
                {"address": address, "sid": sid, "timedelta": datetime.now()},
            )

        db.session.commit()
        for message in db.session.query(Message).filter_by(receiver=address):
            emit("message", message.toJson(), to=sid, namespace="/")


@socketio.on("message")
def handle_message(data: MessageType):

    db.session.add(Message(data=data))
    db.session.commit()

    sess: Session | None = db.session.query(Session).get(data["receiver"])
    if sess is not None:
        sid = sess.sid
        emit(
            "message",
            data,
            to=sid,
            namespace="/",
        )
    db.session.flush()


@socketio.on("delivered")
def handle_delivered(data):
    sender_sess: Session | None = db.session.query(Session).get(data["sender"])

    if sender_sess is not None:
        sid = sender_sess.sid

        message = db.session.query(Message).filter(Message._id == data["id"])
        message.delete(synchronize_session="evaluate")
        db.session.commit()
        emit("delivered", data["id"], to=sid, namespace="/")
    else:
        # TODO: unimplement
        print("The sender of the message is offline to receiver delivery report")

    db.session.flush()


@socketio.on("disconnect")
def handle_disconnect():
    address: str | None = request.headers.get("user")
    if address is not None:
        db.session.query(Session).filter_by(address=address).delete(
            synchronize_session="evaluate"
        )
        db.session.commit()
        db.session.flush()


with app.app_context():
    db.create_all()

    def remove_inactive_sessions():
        current_time = datetime.now()
        with app.app_context():
            inactive_sessions = [
                sid
                for sid in db.session.query(Session).filter(
                    current_time - Session.timedelta > sess_pool_timeout  # type: ignore
                )
            ]

            for sid in inactive_sessions:
                db.session.delete(sid)
            db.session.commit()
            db.session.flush()


if __name__ == "__main__":
    socketio.run(app, debug=True, use_reloader=True, log_output=True)

with app.app_context():

    def schedule_session_cleanup():
        remove_inactive_sessions()
        threading.Timer(60, schedule_session_cleanup).start()

    schedule_session_cleanup()
# ngrok http --domain=trusted-currently-bobcat.ngrok-free.app 5000
