from decimal import Decimal

from nailsize_ml.size_calibration import (
    CHART_ID as CALIBRATION_CHART_ID,
)
from nailsize_ml.size_calibration import (
    CHART_VERSION as CALIBRATION_CHART_VERSION,
)
from nailsize_ml.size_calibration import CHART_WIDTHS_MM, _recommend_size

from app.size_chart import CHART, CHART_ID, CHART_VERSION, recommend_size


def test_model_calibration_uses_the_exact_production_chart_contract() -> None:
    assert CALIBRATION_CHART_ID == CHART_ID
    assert CALIBRATION_CHART_VERSION == CHART_VERSION
    assert CHART_WIDTHS_MM == tuple(float(width) for _, width in CHART)
    for width in (*CHART_WIDTHS_MM, 14.2, 18.1, 8.9):
        production = recommend_size(width)
        calibration = _recommend_size(width)
        assert calibration == (None if production is None else int(production.recommended_size))
    assert all(isinstance(width, Decimal) for _, width in CHART)
