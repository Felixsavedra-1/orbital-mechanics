"""Impulsive delta-v budget: parking-orbit injection and arrival capture burns from
the porkchop v-infinity values (Curtis Ch. 8). Excludes finite-burn/gravity losses,
ascent, mid-course corrections, and EDL. SI units; speeds in m/s unless noted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from constants import (
    EARTH_PARKING_ALTITUDE,
    EARTH_RADIUS,
    MARS_CAPTURE_ALTITUDE,
    MARS_CAPTURE_ECCENTRICITY,
    MARS_RADIUS,
    MU_EARTH,
    MU_MARS,
)
from astrodynamics.porkchop import TransferOpportunity


def injection_delta_v(v_inf: float, mu: float, r_park: float) -> float:
    """Burn (m/s) from a circular parking orbit onto the departure hyperbola (Curtis Eq. 8.41)."""
    if mu <= 0.0 or r_park <= 0.0:
        raise ValueError("mu and r_park must be positive")
    v_hyperbola = math.sqrt(v_inf * v_inf + 2.0 * mu / r_park)
    v_circular = math.sqrt(mu / r_park)
    return v_hyperbola - v_circular


def capture_delta_v(v_inf: float, mu: float, r_capture: float, e_capture: float = 0.0) -> float:
    """Periapsis burn (m/s) from the arrival hyperbola into the target orbit (Curtis Eq. 8.66)."""
    if mu <= 0.0 or r_capture <= 0.0:
        raise ValueError("mu and r_capture must be positive")
    if not 0.0 <= e_capture < 1.0:
        raise ValueError("e_capture must satisfy 0 <= e < 1")
    v_hyperbola = math.sqrt(v_inf * v_inf + 2.0 * mu / r_capture)
    v_capture_orbit = math.sqrt((1.0 + e_capture) * mu / r_capture)
    return v_hyperbola - v_capture_orbit


@dataclass
class DeltaVBudget:
    """Impulsive delta-v budget for one transfer opportunity (m/s)."""

    injection_m_s: float   # parking orbit -> departure hyperbola
    capture_m_s: float     # arrival hyperbola -> capture orbit
    total_m_s: float


def mission_delta_v(
    opportunity: TransferOpportunity,
    mu_depart: float = MU_EARTH,
    r_park: float = EARTH_RADIUS + EARTH_PARKING_ALTITUDE,
    mu_arrive: float = MU_MARS,
    r_capture: float = MARS_RADIUS + MARS_CAPTURE_ALTITUDE,
    e_capture: float = MARS_CAPTURE_ECCENTRICITY,
) -> DeltaVBudget:
    """Impulsive injection + capture delta-v for a solved transfer (Earth->Mars defaults)."""
    v_inf_dep = opportunity.v_inf_depart_km_s * 1000.0
    v_inf_arr = opportunity.v_inf_arrive_km_s * 1000.0
    injection = injection_delta_v(v_inf_dep, mu_depart, r_park)
    capture = capture_delta_v(v_inf_arr, mu_arrive, r_capture, e_capture)
    return DeltaVBudget(injection_m_s=injection, capture_m_s=capture, total_m_s=injection + capture)
