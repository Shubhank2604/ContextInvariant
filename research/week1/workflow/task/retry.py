"""Small replay task: fix retry filtering and honor the supplied attempt limit."""


def should_retry(status_code: int, attempts_made: int, retry_limit: int = 2) -> bool:
    return status_code >= 500 and attempts_made < 1
