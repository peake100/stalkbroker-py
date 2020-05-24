from protogen.stalk_proto import models_pb2 as backend
from stalkbroker import models

# We're going to use the same color as discord's dark theme for the chart background.
CHART_BG_COLOR = "#2C2F33"
CHART_PADDING = 0.03


# Converts this bots price pattern enum values to our backend service model's enum
# values.
PATTERN_FROM_BACKEND = {
    backend.PricePatterns.UNKNOWN: models.Patterns.UNKNOWN,
    backend.PricePatterns.FLUCTUATING: models.Patterns.FLUCTUATING,
    backend.PricePatterns.DECREASING: models.Patterns.DECREASING,
    backend.PricePatterns.SMALLSPIKE: models.Patterns.SMALLSPIKE,
    backend.PricePatterns.BIGSPIKE: models.Patterns.BIGSPIKE,
}

PATTERN_TO_BACKEND = {v: k for k, v in PATTERN_FROM_BACKEND.items()}
