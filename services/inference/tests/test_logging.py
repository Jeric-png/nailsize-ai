import logging

import pytest

from app.logging_config import safe_log


@pytest.mark.parametrize(
    "field",
    ["filename", "image", "contour", "projected_width_mm", "recommended_size", "result_summary"],
)
def test_sensitive_log_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="Unsafe log fields"):
        safe_log(logging.getLogger("test"), logging.INFO, event="test", **{field: "secret"})
