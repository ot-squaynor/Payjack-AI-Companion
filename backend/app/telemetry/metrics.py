from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class DurationMetric:
    name: str
    milliseconds: float


def measure_duration(name: str, start_time: float) -> DurationMetric:
    return DurationMetric(
        name=name,
        milliseconds=round((time.perf_counter() - start_time) * 1000, 3),
    )
