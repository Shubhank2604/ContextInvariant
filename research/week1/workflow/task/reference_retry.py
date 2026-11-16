"""Known task-oracle reference; never an offline model-generated patch."""


def should_retry(status_code: int, attempts_made: int, retry_limit: int = 2) -> bool:
    return status_code == 503 and 0 <= attempts_made < retry_limit
