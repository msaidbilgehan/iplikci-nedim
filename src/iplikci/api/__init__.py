"""The HTTP API (ADR-0007, architecture §16): FastAPI on 127.0.0.1. Every request comes to an allowed Host and proves
who sends it, with a session cookie or a token; a browser's writes also come from the service's own pages (Origin)
with the X-Iplikci header. The API uses only the use cases in `app`."""
