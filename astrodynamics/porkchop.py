"""Interplanetary transfer / launch-window analysis (porkchop search).

For each (departure date, time-of-flight) pair, look up the departure/arrival planet
positions (ephemeris.py), solve Lambert for the connecting heliocentric transfer, and
difference the transfer velocities against the planet velocities to get the hyperbolic
excess speeds:

    v_inf_depart = |v1 - v_planet_dep|   ->   C3 = v_inf_depart^2   (launch energy)
    v_inf_arrive = |v2 - v_planet_arr|                              (arrival energy)

Scanning a grid of dates and flight times gives the classic porkchop trade space; the
minimum-energy cell is a real launch opportunity. Total v_infinity (departure + arrival)
is reported as a first-order delta-v proxy — a full budget would add launch injection
and capture/EDL, which depend on vehicle and mission specifics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

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
    """Solve a single planet-to-planet transfer and return its energy metrics.

    Raises:
        ValueError: If tof_days <= 0 or the Lambert geometry is singular/non-convergent.
    """
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
    departure_jds,
    tof_days_grid,
    mu: float = MU_SUN,
    prograde: bool = True,
) -> TransferOpportunity:
    """Scan a (departure date x flight time) grid and return the minimum-energy transfer.

    The objective is total v_infinity (departure + arrival). Grid cells whose Lambert
    geometry is singular or fails to converge are skipped.

    Raises:
        ValueError: If no grid cell yields a valid transfer.
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
