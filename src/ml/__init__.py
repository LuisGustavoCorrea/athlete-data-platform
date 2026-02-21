"""Machine Learning module for Athlete Data Platform.

This module provides ML training and inference functionality:
- Time Estimator: Predict race times (5K, 10K, 21K, 42K)
- Overtraining Detector: Identify overtraining risk
"""

from src.ml.config import MLConfig

__all__ = [
    "MLConfig",
]
