import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_output_path: Path | None = None

_CHAT_COMPLETION_RESPONSE = json.dumps(
    {
        "id": "fake-capture",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "captured"},
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
).encode()

_CHAT_COMPLETION_STREAM_CHUNKS = [
    {"id": "fake-capture", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "captured"}, "finish_reason": None}]},
    {"id": "fake-capture", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
]

_RESPONSE_ITEM = {
    "id": "item_0",
    "type": "message",
    "role": "assistant",
    "status": "completed",
    "content": [{"type": "output_text", "text": "captured"}],
}

_RESPONSES_API_RESPONSE = json.dumps(
    {
        "id": "fake-capture",
        "object": "response",
        "status": "completed",
        "output": [_RESPONSE_ITEM],
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
).encode()

_RESPONSES_STREAM_EVENTS = [
    ("response.created", {"response": {"id": "fake-capture", "object": "response", "status": "in_progress"}}),
    ("response.output_item.added", {"output_index": 0, "item": {"id": "item_0", "type": "message", "role": "assistant", "status": "in_progress", "content": []}}),
    ("response.content_part.added", {"item_id": "item_0", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}}),
    ("response.output_text.delta", {"item_id": "item_0", "output_index": 0, "content_index": 0, "delta": "captured"}),
    ("response.output_text.done", {"item_id": "item_0", "output_index": 0, "content_index": 0, "text": "captured"}),
    ("response.content_part.done", {"item_id": "item_0", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": "captured"}}),
    ("response.output_item.done", {"output_index": 0, "item": _RESPONSE_ITEM}),
    ("response.completed", {"response": {"id": "fake-capture", "object": "response", "status": "completed", "output": [_RESPONSE_ITEM], "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}}),
]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        captured = body.get("tools", body)
        if _output_path is not None:
            _output_path.write_text(json.dumps(captured, indent=2))

        is_responses_api = "input" in body
        if body.get("stream"):
            if is_responses_api:
                self._write_responses_stream()
            else:
                self._write_chat_completion_stream()
        elif is_responses_api:
            self._write_json(_RESPONSES_API_RESPONSE)
        else:
            self._write_json(_CHAT_COMPLETION_RESPONSE)

    def _write_json(self, payload: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _start_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def _write_chat_completion_stream(self):
        self._start_stream()
        for chunk in _CHAT_COMPLETION_STREAM_CHUNKS:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _write_responses_stream(self):
        self._start_stream()
        for event_type, payload in _RESPONSES_STREAM_EVENTS:
            data = json.dumps({"type": event_type, **payload})
            self.wfile.write(f"event: {event_type}\ndata: {data}\n\n".encode())
        self.wfile.flush()

    def log_message(self, *args):
        pass


def main():
    global _output_path
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--port", type=int, default=8812)
    args = parser.parse_args()
    _output_path = Path(args.output)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
