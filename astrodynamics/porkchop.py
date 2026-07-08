"""Porkchop launch-window search: for each (departure date, time-of-flight) cell,
solve Lambert between ephemeris positions and difference the transfer velocities
against the planet velocities for the hyperbolic excess speeds (C3 = v_inf_depart^2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from constants import MU_SUN
from astrodynamics.ephemeris import planet_state
from astrodynamics.lambert import solve_lambert

_SECONDS_PER_DAY = 86400.0


@dataclass
class TransferOpportunity:
    """One solved transfer between two planets."""

    departure_jd: float
    arrival_jd: float
    tof_days: float
    c3_km2_s2: float          # departure launch energy, (km/s)^2
    v_inf_depart_km_s: float  # hyperbolic excess at departure
    v_inf_arrive_km_s: float  # hyperbolic excess at arrival
    total_v_inf_km_s: float   # departure + arrival, first-order delta-v proxy


def solve_transfer(
    departure_planet: str,
    arrival_planet: str,
    departure_jd: float,
    tof_days: float,
    mu: float = MU_SUN,
    prograde: bool = True,
) -> TransferOpportunity:
    """Solve a single planet-to-planet transfer and return its energy metrics."""
    if not math.isfinite(tof_days) or tof_days <= 0.0:
        raise ValueError("tof_days must be a finite positive number")

    arrival_jd = departure_jd + tof_days
    dep = planet_state(departure_planet, departure_jd)
    arr = planet_state(arrival_planet, arrival_jd)

    v1, v2 = solve_lambert(dep.r, arr.r, tof_days * _SECONDS_PER_DAY, mu, prograde)

    v_inf_dep = float(np.linalg.norm(v1 - dep.v)) / 1000.0  # km/s
    v_inf_arr = float(np.linalg.norm(v2 - arr.v)) / 1000.0
    return TransferOpportunity(
        departure_jd=departure_jd,
        arrival_jd=arrival_jd,
        tof_days=tof_days,
        c3_km2_s2=v_inf_dep * v_inf_dep,
        v_inf_depart_km_s=v_inf_dep,
        v_inf_arrive_km_s=v_inf_arr,
        total_v_inf_km_s=v_inf_dep + v_inf_arr,
    )


def best_transfer(
    departure_planet: str,
    arrival_planet: str,
    departure_jds: Iterable[float],
    tof_days_grid: Iterable[float],
    mu: float = MU_SUN,
    prograde: bool = True,
) -> TransferOpportunity:
    """Minimum total-v_infinity transfer over a (departure date x flight time) grid.

    Cells whose Lambert geometry is singular or fails to converge are skipped.
    """
    best: TransferOpportunity | None = None
    for dep_jd in departure_jds:
        for tof in tof_days_grid:
            try:
                candidate = solve_transfer(departure_planet, arrival_planet, dep_jd, tof, mu, prograde)
            except ValueError:
                continue
            if best is None or candidate.total_v_inf_km_s < best.total_v_inf_km_s:
                best = candidate
    if best is None:
        raise ValueError("no valid transfer found in the supplied grid")
    return best
