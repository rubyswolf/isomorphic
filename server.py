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
MIDI_CHANNEL = 0
PITCH_BEND_MIN = -8192
PITCH_BEND_MAX = 8191
PITCH_BEND_RANGE_MIN = 1
PITCH_BEND_RANGE_MAX = 96

app = Flask(__name__, static_folder=BASE_DIR)
sock = Sock(app)


def clamp_int(value, minimum: int, maximum: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def send_pitch_bend_range(out: mido.ports.BaseOutput, semitones: int) -> None:
    # RPN 0 selects pitch-bend sensitivity. DiffOsc consumes the MSB as semitones.
    for control, value in ((101, 0), (100, 0), (6, semitones), (101, 127), (100, 127)):
        out.send(mido.Message("control_change", channel=MIDI_CHANNEL,
                              control=control, value=value))


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
    pitch_bend_range = None
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
                note = clamp_int(data.get("note"), 0, 127, 60)
                velocity = clamp_int(data.get("velocity"), 0, 127, 100)
                out.send(mido.Message("note_on", channel=MIDI_CHANNEL,
                                      note=note, velocity=velocity))
            elif msg_type == "note_off" and out:
                note = clamp_int(data.get("note"), 0, 127, 60)
                velocity = clamp_int(data.get("velocity"), 0, 127, 0)
                out.send(mido.Message("note_off", channel=MIDI_CHANNEL,
                                      note=note, velocity=velocity))
            elif msg_type == "pitch_bend" and out:
                requested_range = data.get("range")
                if requested_range is not None:
                    requested_range = clamp_int(requested_range, PITCH_BEND_RANGE_MIN,
                                                PITCH_BEND_RANGE_MAX, 12)
                    if requested_range != pitch_bend_range:
                        send_pitch_bend_range(out, requested_range)
                        pitch_bend_range = requested_range
                raw_val = clamp_int(data.get("value"), PITCH_BEND_MIN,
                                    PITCH_BEND_MAX, 0)
                out.send(mido.Message("pitchwheel", channel=MIDI_CHANNEL,
                                      pitch=raw_val))
            elif msg_type == "panic" and out:
                out.panic()
    finally:
        if out:
            out.close()


if __name__ == "__main__":
    logging.info("Serving %s on http://0.0.0.0:%s", HTML_FILE, PORT)
    app.run(host="0.0.0.0", port=PORT)
