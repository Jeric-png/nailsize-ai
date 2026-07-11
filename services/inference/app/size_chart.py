from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SizeRecommendation:
    recommended_size: str
    alternate_size: str | None


CHART_ID = "platform-default"
CHART_VERSION = "1"
CHART: tuple[tuple[str, Decimal], ...] = tuple(
    (str(size), Decimal(18 - size)) for size in range(10)
)


def recommend_size(width_mm: float, uncertainty_mm: float = 0.0) -> SizeRecommendation | None:
    """Select the narrowest tip that is at least as wide as the projected nail."""
    width = Decimal(str(width_mm))
    uncertainty = Decimal(str(uncertainty_mm))
    if width > CHART[0][1] or width < CHART[-1][1]:
        return None

    recommended_index = next(
        index
        for index, (_, tip_width) in enumerate(CHART)
        if tip_width >= width and (index == len(CHART) - 1 or CHART[index + 1][1] < width)
    )
    recommended = CHART[recommended_index][0]

    lower = width - uncertainty
    upper = width + uncertainty
    candidates = [
        size for size, tip_width in CHART if lower <= tip_width <= upper and size != recommended
    ]
    alternate = min(candidates, key=lambda size: abs(CHART[int(size)][1] - width), default=None)
    return SizeRecommendation(recommended, alternate)
