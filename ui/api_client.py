"""HTTP client for the RAG backend. The UI never touches Django directly."""
import requests

TIMEOUT_SECONDS = 180


class ApiError(RuntimeError):
    """A non-2xx response from the backend."""


class RagApiClient:
    def __init__(self, base_url: str, token: str | None = None):
        self._base_url = base_url.rstrip("/")
        self.token = token

    # ----- authentication -----
    def register(self, username: str, password: str, email: str = "") -> str:
        data = self._request(
            "POST", "/api/auth/register/", json={"username": username, "password": password, "email": email}
        )
        self.token = data["token"]
        return self.token

    def login(self, username: str, password: str) -> str:
        data = self._request(
            "POST", "/api/auth/login/", json={"username": username, "password": password}
        )
        self.token = data["token"]
        return self.token

    # ----- documents -----
    def list_documents(self) -> list[dict]:
        return self._request("GET", "/api/documents/")

    def upload_document(self, filename: str, content: bytes) -> dict:
        return self._request("POST", "/api/documents/", files={"file": (filename, content)})

    def delete_document(self, document_id: int) -> None:
        self._request("DELETE", f"/api/documents/{document_id}/")

    # ----- question answering -----
    def ask(
        self,
        question: str,
        *,
        mode: str | None = None,
        debug: bool = False,
        rerank: bool | None = None,
        history: list[dict] | None = None,
        document_ids: list[int] | None = None,
    ) -> dict:
        payload: dict = {"question": question, "debug": debug}
        if mode:
            payload["mode"] = mode
        if rerank is not None:
            payload["rerank"] = rerank
        if history:
            payload["history"] = history
        if document_ids:
            payload["document_ids"] = document_ids
        return self._request("POST", "/api/qa/ask/", json=payload)

    # ----- plumbing -----
    def _headers(self) -> dict:
        return {"Authorization": f"Token {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = requests.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                timeout=TIMEOUT_SECONDS,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Cannot reach the API: {exc}") from exc

        if response.status_code >= 400:
            raise ApiError(f"{response.status_code}: {response.text[:400]}")
        if not response.content:
            return {}
        return response.json()
