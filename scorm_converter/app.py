from __future__ import annotations

import json
import mimetypes
import shutil
import tempfile
import warnings
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

warnings.filterwarnings(
    "ignore",
    message="'cgi' is deprecated.*",
    category=DeprecationWarning,
)

import cgi

from converter import LEGACY_EXTENSIONS, SUPPORTED_EXTENSIONS, convert_file_to_scorm


APP_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = APP_DIR / "output"
STATIC_DIR = APP_DIR / "static"
HOST = "127.0.0.1"
PORT = 8765


class ScormConverterHandler(BaseHTTPRequestHandler):
    server_version = "BeyondRisXScormConverter/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path.startswith("/static/"):
            static_path = (STATIC_DIR / unquote(parsed.path.removeprefix("/static/"))).resolve()
            if STATIC_DIR.resolve() not in static_path.parents and static_path != STATIC_DIR.resolve():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self.send_file(static_path)
            return
        if parsed.path.startswith("/downloads/"):
            download_path = (OUTPUT_DIR / unquote(parsed.path.removeprefix("/downloads/"))).resolve()
            if OUTPUT_DIR.resolve() not in download_path.parents and download_path != OUTPUT_DIR.resolve():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self.send_file(download_path, "application/zip")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/convert":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.handle_convert()

    def handle_convert(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            self.send_json({"ok": False, "error": "Expected multipart form data."}, HTTPStatus.BAD_REQUEST)
            return

        with tempfile.TemporaryDirectory(prefix="scorm-upload-") as temp_name:
            upload_dir = Path(temp_name)
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )
            files = form["files"] if "files" in form else []
            if not isinstance(files, list):
                files = [files]

            saved_files = []
            for item in files:
                if not getattr(item, "filename", ""):
                    continue
                source_name = Path(item.filename).name
                suffix = Path(source_name).suffix.lower()
                if suffix not in SUPPORTED_EXTENSIONS and suffix not in LEGACY_EXTENSIONS:
                    continue
                destination = upload_dir / source_name
                with destination.open("wb") as handle:
                    shutil.copyfileobj(item.file, handle)
                saved_files.append(destination)

            if not saved_files:
                self.send_json(
                    {"ok": False, "error": "No .docx or .pptx files were found in that selection."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            results = []
            for source_path in saved_files:
                try:
                    result = convert_file_to_scorm(source_path, OUTPUT_DIR)
                    results.append(
                        {
                            "source": result.source_name,
                            "status": "converted",
                            "package": result.package_name,
                            "downloadUrl": f"/downloads/{result.package_name}",
                        }
                    )
                except Exception as error:
                    results.append(
                        {
                            "source": source_path.name,
                            "status": "failed",
                            "error": str(error),
                        }
                    )

        self.send_json({"ok": True, "results": results})

    def send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if content_type is None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        if path.suffix == ".zip":
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), ScormConverterHandler)
    print(f"SCORM converter running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
