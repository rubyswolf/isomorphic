import json
import logging
import os
from typing import Optional

from flask import Flask, send_from_directory
from flask_sock import Sock
import mido

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
HTML_FILE = "isomorphic_keyboard_synth_single_html.html"
PORT = 5000
MIDI_PORT = "Python MIDI 1"

app = Flask(__name__, static_folder=BASE_DIR)
sock = Sock(app)


def open_midi_output() -> Optional[mido.ports.BaseOutput]:
    if MIDI_PORT:
        try:
            return mido.open_output(MIDI_PORT)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed opening preferred MIDI port %s: %s", MIDI_PORT, exc)
    try:
        return mido.open_output()
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed opening default MIDI port: %s", exc)
        return None


@app.route("/")
def root():
    return send_from_directory(BASE_DIR, HTML_FILE)


@app.route("/<path:asset>")
def assets(asset: str):
    return send_from_directory(BASE_DIR, asset)


@sock.route("/ws")
def websocket(ws):
    out = open_midi_output()
    status = {
        "type": "status",
        "connected": bool(out),
        "port": getattr(out, "name", None),
        "outputs": mido.get_output_names(),
    }
    try:
        ws.send(json.dumps(status))
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed sending status to client: %s", exc)

    try:
        while True:
            try:
                raw = ws.receive()
            except Exception as exc:  # noqa: BLE001
                logging.warning("WebSocket receive error: %s", exc)
                break
            if raw is None:
                break

            try:
                data = json.loads(raw)
            except Exception:
                continue

            msg_type = data.get("type")
            if msg_type == "note_on" and out:
                note = int(data.get("note", 60))
                velocity = int(data.get("velocity", 100))
                out.send(mido.Message("note_on", note=note, velocity=velocity))
            elif msg_type == "note_off" and out:
                note = int(data.get("note", 60))
                velocity = int(data.get("velocity", 0))
                out.send(mido.Message("note_off", note=note, velocity=velocity))
            elif msg_type == "pitch_bend" and out:
                try:
                    raw_val = int(data.get("value", 0))
                except Exception:
                    raw_val = 0
                raw_val = max(-8192, min(8191, raw_val))
                out.send(mido.Message("pitchwheel", pitch=raw_val))
            elif msg_type == "panic" and out:
                out.panic()
    finally:
        if out:
            out.close()


if __name__ == "__main__":
    logging.info("Serving %s on http://0.0.0.0:%s", HTML_FILE, PORT)
    app.run(host="0.0.0.0", port=PORT)
