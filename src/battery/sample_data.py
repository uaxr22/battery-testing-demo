"""A typical GB winter day of half-hourly prices (GBP/MWh), 48 periods.

Cheap overnight, a morning bump, and the evening peak at 17:00-19:00.
"""
SAMPLE_DAY_PRICES = [
    42, 40, 38, 36, 35, 34, 33, 33, 34, 36, 38, 42,         # 00:00-06:00
    50, 58, 66, 72, 75, 74, 70, 66, 62, 60, 58, 56,         # 06:00-12:00
    55, 54, 54, 56, 60, 66, 78, 95, 120, 150, 165, 140,     # 12:00-18:00
    118, 96, 84, 76, 70, 64, 60, 56, 52, 48, 46, 44,        # 18:00-24:00
]
