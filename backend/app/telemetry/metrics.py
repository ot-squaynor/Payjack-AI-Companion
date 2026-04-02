# \backend\app\telemetry\metrics.py
'''This module defines a DurationMetric dataclass and a measure_duration function to calculate the duration of an operation in milliseconds. The DurationMetric dataclass has two fields: name (a string representing the name of the metric) and milliseconds (a float representing the duration in milliseconds). The measure_duration function takes a name and a start_time (in seconds) as input, calculates the elapsed time since start_time, converts it to milliseconds, rounds it to three decimal places, and returns a DurationMetric instance with the provided name and calculated duration. This allows for easy tracking and reporting of operation durations in the application.
Example usage:
start_time = time.perf_counter()'''

# --- IGNORE ---
from __future__ import annotations

#IMPORTS
from dataclasses import dataclass
import time

#
@dataclass(frozen=True, slots=True)
class DurationMetric:
    name: str
    milliseconds: float

# 
def measure_duration(name: str, start_time: float) -> DurationMetric:
    return DurationMetric(
        name=name,
        milliseconds=round((time.perf_counter() - start_time) * 1000, 3),
    )
