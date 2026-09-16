from datetime import datetime, timezone

import pytest


@pytest.fixture
def fixed_clock():
    return lambda: datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
