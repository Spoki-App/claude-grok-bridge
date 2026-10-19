import importlib.util
import io
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "claude" / "skills" / "grok-bridge"
GROK = ROOT / "grok"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_config(folder, data, mode=0o600):
    path = os.path.join(folder, "config.json")
    pathlib.Path(path).write_text(json.dumps(data))
    os.chmod(path, mode)
    return path


def stream_line(text):
    """One `claude -p --output-format stream-json` event whose tool result carries `text`."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": [{"type": "text", "text": text}]}]}})


def tool_use_line(name, tool_input):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": name, "input": tool_input}]}})


def result_line(text):
    return json.dumps({"type": "result", "subtype": "success", "result": text})


class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(body.encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Recorder:
    """Stands in for urllib.request.urlopen and keeps the last request."""

    def __init__(self, body='{"success":true}', status=200):
        self.body, self.status, self.request = body, status, None

    def __call__(self, request, timeout=None):
        self.request = request
        return FakeResponse(self.body, self.status)
