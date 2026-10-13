"""Тонкий HTTP-клиент MTS Exolve CRM API с ретраями и rate limit."""
import json
import random
import re
import threading
import time
import urllib.error
import urllib.request


DOMAIN_ERROR_MSG = "Некорректный домен или ошибка соединения"

# --- Параметры ретраев ---
MAX_ATTEMPTS = 3
BASE_BACKOFF = 0.5
MAX_BACKOFF = 8.0
RETRY_AFTER_CAP = 30.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# --- Параметры rate-limit ---
DEFAULT_RPS = 5.0
MIN_RPS = 1.0
MAX_RPS = 50.0

# Максимальная длина тела ответа, встраиваемого в ошибку
ERROR_BODY_MAX = 500


class ExolveApiError(Exception):
    """Ошибка обращения к Exolve API.

    Атрибуты:
        status_code — код HTTP (401, 403, 404, 429, 5xx) или None для сетевых
        retryable   — стоит ли повторять запрос
        retry_after — секунды из заголовка Retry-After (для 429), иначе None
        body        — тело ответа сервера (для HTTP-ошибок), иначе None
    """

    def __init__(self, message: str, status_code: int | None = None,
                 retryable: bool = False, retry_after: float | None = None,
                 body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after
        self.body = body


class _RateLimiter:
    """Простой клиентский rate limiter (token interval)."""

    def __init__(self, rps: float = DEFAULT_RPS):
        self._lock = threading.Lock()
        self._last = 0.0
        self._min_interval = 0.0
        self.set_rps(rps)

    def set_rps(self, rps: float):
        rps = max(MIN_RPS, min(float(rps), MAX_RPS))
        self._min_interval = 1.0 / rps

    def wait(self):
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._min_interval:
                time.sleep(self._min_interval - delta)
                now = time.monotonic()
            self._last = now


def _normalize_domain(domain: str) -> str:
    d = (domain or "").strip()
    d = re.sub(r"^https?://", "", d, flags=re.IGNORECASE)
    d = d.rstrip("/")
    if not d:
        raise ValueError(DOMAIN_ERROR_MSG)
    if any(ch in d for ch in " /?#\\"):
        raise ValueError(DOMAIN_ERROR_MSG)
    return d


def _validate_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        raise ValueError("Ключ не задан")
    try:
        k.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "Ключ содержит недопустимые символы.\n"
            "Разрешены только латинские буквы, цифры и стандартные символы ASCII."
        )
    return k


class ExolveClient:
    def __init__(self, domain: str, key: str, timeout: int = 10,
                 max_rps: float = DEFAULT_RPS):
        self.domain = _normalize_domain(domain)
        self.key = _validate_key(key)
        self.timeout = timeout
        self._limiter = _RateLimiter(max_rps)

    def set_rps(self, rps: float):
        self._limiter.set_rps(rps)

    # --- низкий уровень ---
    def _request(self, path: str, method: str = "GET", body: dict | None = None) -> str:
        last_error: ExolveApiError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._request_once(path, method, body)
            except ExolveApiError as e:
                last_error = e
                if not e.retryable or attempt >= MAX_ATTEMPTS:
                    raise
                time.sleep(self._compute_delay(attempt, e))
        if last_error is not None:
            raise last_error
        raise ExolveApiError("Не удалось выполнить запрос")

    @staticmethod
    def _compute_delay(attempt: int, err: ExolveApiError) -> float:
        if err.retry_after is not None:
            return min(float(err.retry_after), RETRY_AFTER_CAP)
        base = min(BASE_BACKOFF * (2 ** (attempt - 1)), MAX_BACKOFF)
        jitter = random.uniform(0, base * 0.2)
        return base + jitter

    def _request_once(self, path: str, method: str = "GET",
                      body: dict | None = None) -> str:
        self._limiter.wait()

        url = f"https://{self.domain}{path}"
        headers = {"X-API-KEY": self.key, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            code = e.code
            retryable = code in RETRYABLE_STATUS
            retry_after = None
            if code == 429 and e.headers is not None:
                ra = e.headers.get("Retry-After")
                if ra:
                    try:
                        retry_after = float(ra)
                    except (ValueError, TypeError):
                        retry_after = None

            # Читаем тело ответа — оно содержит причину 400/422 и т.п.
            body_text = ""
            try:
                raw = e.read()
                if raw:
                    body_text = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                body_text = ""
            if len(body_text) > ERROR_BODY_MAX:
                body_text = body_text[:ERROR_BODY_MAX] + "…"

            message = self._format_http_error(e)
            if body_text:
                # Однострочный вариант — для тостов
                snippet = body_text.replace("\r", " ").replace("\n", " ")
                if len(snippet) > 200:
                    snippet = snippet[:200] + "…"
                message = f"{message}\n{snippet}"

            raise ExolveApiError(
                message,
                status_code=code,
                retryable=retryable,
                retry_after=retry_after,
                body=body_text or None,
            ) from e
        except urllib.error.URLError as e:
            raise ExolveApiError(DOMAIN_ERROR_MSG, retryable=True) from e
        except TimeoutError as e:
            raise ExolveApiError(DOMAIN_ERROR_MSG, retryable=True) from e
        except Exception as e:
            raise ExolveApiError(f"Неизвестная ошибка: {e}") from e

    @staticmethod
    def _format_http_error(e: urllib.error.HTTPError) -> str:
        code = e.code
        if code == 401:
            return "Неверный X-API-KEY (401). Проверьте ключ в шапке."
        if code == 403:
            return "Доступ запрещён (403). У ключа нет прав на эту операцию."
        if code == 404:
            return DOMAIN_ERROR_MSG
        if code == 429:
            return "Слишком много запросов (429). Подождите и попробуйте снова."
        if code == 400:
            return "Некорректный запрос (400)."
        if code == 422:
            return "Ошибка валидации (422)."
        if 500 <= code < 600:
            return f"Ошибка сервера Exolve ({code}). Попробуйте позже."
        return f"HTTP {code}: {e.reason}"

    def _get_list(self, path: str, keys: tuple[str, ...]) -> tuple[list, str]:
        raw = self._request(path)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ExolveApiError(DOMAIN_ERROR_MSG) from e

        items = []
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and "items" in data[0]:
                items = data[0].get("items", [])
            else:
                items = data
        elif isinstance(data, dict):
            for k in keys:
                if k in data and isinstance(data[k], list):
                    items = data[k]
                    break
        return items, raw

    # --- высокий уровень ---
    def get_users(self) -> tuple[list, str]:
        return self._get_list("/crmapi/v1/users/", ("items", "users", "data"))

    def get_groups(self) -> tuple[list, str]:
        return self._get_list("/crmapi/v1/groups", ("items", "groups", "data"))

    def get_telnums(self) -> tuple[list, str]:
        return self._get_list("/crmapi/v1/telnums", ("items", "numbers", "data"))

    def enable_telnum(self, telnum: str) -> str:
        return self._request(f"/crmapi/v1/telnums/{telnum}/enabled", method="POST")

    def disable_telnum(self, telnum: str) -> str:
        return self._request(f"/crmapi/v1/telnums/{telnum}/enabled", method="DELETE")

    def set_telnum_route(self, telnum: str, params: dict) -> str:
        """POST /crmapi/v1/telnums/{telnum}.

        Минимальный корректный body для смены маршрута:
            {"type": "user", "user": "...", "disabled": false}
            {"type": "group", "group": "...", "disabled": false}
        Поле disabled=false одновременно включает приём звонков — отдельный
        вызов /enabled не требуется.
        """
        return self._request(f"/crmapi/v1/telnums/{telnum}",
                             method="POST", body=params)

    def bind_telnum(self, login: str, telnum: str) -> str:
        return self._request(
            "/crmapi/v1/caller-ids/users",
            method="POST",
            body={"login": login, "telnum": telnum},
        )