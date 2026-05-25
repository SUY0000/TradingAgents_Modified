import json
import os


def load_custom_headers(env_var: str) -> dict[str, str] | None:
    """Parse CUSTOM_*_HEADERS env var. Returns None if unset/empty.

    Raises ValueError with the env var name on malformed JSON or non-dict.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{env_var} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"{env_var} must be a JSON object (got {type(parsed).__name__})"
        )
    return {k: str(v) for k, v in parsed.items()}
