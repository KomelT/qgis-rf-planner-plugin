"""HTTP client for RF Planner backend connectivity and coverage tasks."""

import json
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse
from typing import Optional

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsMessageLog, Qgis


class ApiClient(QObject):
    connectionSucceeded = pyqtSignal(str)
    connectionFailed = pyqtSignal(str)
    coverageSubmitted = pyqtSignal(str)
    coverageCompleted = pyqtSignal(str)
    coverageFailed = pyqtSignal(str)
    debugMessage = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    def test_connection(self, base_url: str) -> None:
        threading.Thread(target=self._test_connection_worker, args=(base_url,), daemon=True).start()

    def submit_coverage(self, base_url: str, payload: dict) -> None:
        threading.Thread(
            target=self._submit_coverage_worker,
            args=(base_url, payload),
            daemon=True,
        ).start()

    def _test_connection_worker(self, base_url: str) -> None:
        endpoint = self._build_url(base_url, "openapi.json")
        self._debug(f"GET {endpoint}")

        try:
            body, status_code, headers = self._http_request("GET", endpoint)
            self._debug(f"Connection response status={status_code}, headers={dict(headers)}, body={body[:500]!r}")
            if status_code < 400:
                self.connectionSucceeded.emit("Connected to API.")
            else:
                self.connectionFailed.emit(body or "Unable to reach API.")
        except Exception as error:
            self._debug(f"Connection request error: {error}")
            self.connectionFailed.emit(str(error))

    def _submit_coverage_worker(self, base_url: str, payload: dict) -> None:
        try:
            coverage_endpoint = self._build_url(base_url, "coverage")
            self._debug(f"POST {coverage_endpoint}")
            self._debug(f"Coverage payload: {json.dumps(payload, ensure_ascii=False)}")

            body, status_code, headers = self._http_request(
                "POST",
                coverage_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
            )
            self._debug(f"Coverage submit response status={status_code}, headers={dict(headers)}, body={body[:1000]!r}")

            if status_code >= 400:
                self.coverageFailed.emit(body or "Failed to start coverage task.")
                return

            data = json.loads(body)
            task_id = data.get("task_id")
            if not task_id:
                self.coverageFailed.emit("Coverage task response did not include a task_id.")
                return

            self.coverageSubmitted.emit(task_id)
            self._poll_task_worker(base_url, task_id)
        except Exception as error:
            self._debug(f"Coverage submit error: {error}")
            self.coverageFailed.emit(str(error))

    def _poll_task_worker(self, base_url: str, task_id: str) -> None:
        task_endpoint = self._build_url(base_url, f"task/{task_id}")

        while True:
            try:
                self._debug(f"GET {task_endpoint}")
                body, status_code, headers = self._http_request("GET", task_endpoint)
                self._debug(f"Task {task_id} response status={status_code}, headers={dict(headers)}, body={body[:1000]!r}")

                if status_code >= 400:
                    self.coverageFailed.emit(body or f"Failed to poll task {task_id}.")
                    return

                data = json.loads(body)
                status = data.get("status")
                if status == "completed":
                    self.coverageCompleted.emit(task_id)
                    return

                if status == "failed":
                    self.coverageFailed.emit(data.get("error", f"Coverage task {task_id} failed."))
                    return

                threading.Event().wait(1.0)
            except Exception as error:
                self._debug(f"Task poll error for {task_id}: {error}")
                self.coverageFailed.emit(str(error))
                return

    def _http_request(
        self,
        method: str,
        url: str,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[str, int, dict]:
        request = urllib.request.Request(url=url, data=data, method=method)
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        # Some edge/WAF layers are stricter with non-browser user agents.
        request.add_header(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        request.add_header("Accept", "application/json, text/plain, */*")
        request.add_header("Origin", origin)
        request.add_header("Referer", origin + "/")
        if content_type:
            request.add_header("Content-Type", content_type)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
                return body, getattr(response, "status", 200), dict(response.headers.items())
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace") if error.fp else ""
            error_headers = dict(error.headers.items()) if error.headers else {}
            return error_body, int(error.code), error_headers

    def _build_url(self, base_url: str, path: str) -> str:
        url = base_url.strip()
        if not url.endswith("/"):
            url += "/"
        return url + path.lstrip("/")

    def _debug(self, message: str) -> None:
        QgsMessageLog.logMessage(message, "RF Planner", Qgis.MessageLevel.Info)
        self.debugMessage.emit(message)
