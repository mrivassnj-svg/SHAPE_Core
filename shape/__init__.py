"""
SHAPE — Self-Healing Autonomous Programming Engine
Group 3 | ITAI2376-14562
Members: Cherluk Sumdin, Olubukola Kukoyi, Taki Eddine Boubekri, Michael Rivas
"""
__version__ = "2.0.0"
__authors__ = [
    "Cherluk Sumdin",
    "Olubukola Kukoyi",
    "Taki Eddine Boubekri",
    "Michael Rivas",
]
# Public API
from shape.agent   import build_agent, SHAPEAgent  # noqa: F401
from shape.parser  import parse_llm_output          # noqa: F401
from shape.safety  import InputGuard                # noqa: F401
from shape.rewards import FeedbackMemory            # noqa: F401
from shape.sensors import parse_csv_line, SensorReading  # noqa: F401
