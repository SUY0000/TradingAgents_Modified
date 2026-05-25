import requests


class FetchError(Exception):
    """Raised when the /models endpoint cannot be reached or returns unexpected data."""


def fetch_custom_models(
    provider: str,
    base_url: str,
    api_key: str,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """GET {base_url}/models, return sorted model id list.

    Raises FetchError on network/HTTP error or unexpected response shape.
    """
    url = base_url.rstrip("/") + "/models"
    headers = dict(extra_headers or {})

    if provider == "custom_anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"Network error fetching {url}: {exc}") from exc

    if not resp.ok:
        snippet = resp.text[:200]
        raise FetchError(
            f"HTTP {resp.status_code} from {url}: {snippet}"
        )

    try:
        body = resp.json()
    except ValueError as exc:
        raise FetchError(f"Invalid JSON from {url}: {exc}") from exc

    # Support both {"data": [...]} and {"models": [...]} shapes
    items = body.get("data") or body.get("models")
    if not isinstance(items, list):
        raise FetchError(
            f"Unexpected response shape from {url}: "
            f"expected 'data' or 'models' list, got {list(body.keys())}"
        )

    model_ids = [
        item["id"] for item in items
        if isinstance(item, dict) and "id" in item
    ]
    return sorted(model_ids)
