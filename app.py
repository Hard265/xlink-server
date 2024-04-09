from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)


@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('message')
def handle_message(message):
    print('Received message:', message)
    # Broadcast the received message to all connected clients
    emit('message', message, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@app.route('/')
def index():
    # Render the HTML template named "index.html" located in the "templates" folder
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, log_output=False)

#ngrok http --domain=trusted-currently-bobcat.ngrok-free.app 5000