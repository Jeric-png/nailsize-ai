import pytest

from app.size_chart import CHART, recommend_size


def test_chart_is_immutable_zero_to_nine() -> None:
    assert CHART == tuple((str(size), 18 - size) for size in range(10))


@pytest.mark.parametrize(
    ("width", "expected"),
    [(18.0, "0"), (17.0, "1"), (14.0, "4"), (9.0, "9"), (14.2, "3")],
)
def test_next_wider_tip_selection(width: float, expected: str) -> None:
    assert recommend_size(width).recommended_size == expected


def test_outside_chart_is_not_clamped() -> None:
    assert recommend_size(18.1) is None
    assert recommend_size(8.9) is None


def test_uncertainty_can_return_adjacent_size() -> None:
    result = recommend_size(14.2, 0.3)
    assert result.recommended_size == "3"
    assert result.alternate_size == "4"
