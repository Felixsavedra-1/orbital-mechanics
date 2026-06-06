"""Perturbing accelerations for high-fidelity orbit propagation.

Perturbations that matter most for near-Earth work, in rough order:

  * J2 oblateness  - Earth's equatorial bulge; drives nodal regression and apsidal
                     rotation. Larger than every other perturbation in LEO.
  * Atmospheric drag - non-conservative; saps energy and decays low orbits.
  * Third-body     - Sun/Moon gravity; significant for high orbits.

Each acceleration is a free function (easy to test in isolation); `ForceModel` composes
the enabled ones into the single acceleration the integrator calls. Earth-centred
inertial (ECI) frame, SI units; the J2 z-axis is the spin axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from constants import (
    ATMOSPHERE_H0,
    ATMOSPHERE_RHO0,
    ATMOSPHERE_SCALE_HEIGHT,
    EARTH_ANGULAR_VELOCITY,
    EARTH_J2,
    EARTH_RADIUS,
    EARTH_RADIUS_EQUATORIAL,
    MU_EARTH,
)


def two_body_acceleration(r: np.ndarray, mu: float) -> np.ndarray:
    """Point-mass gravity: a = -mu * r / |r|^3."""
    r = np.asarray(r, dtype=float)
    r_mag = float(np.linalg.norm(r))
    return -mu * r / r_mag**3


def j2_acceleration(r: np.ndarray, mu: float, j2: float, r_eq: float) -> np.ndarray:
    """J2 oblateness perturbation in ECI (Curtis Eq. 12.30; z is the spin axis)."""
    r = np.asarray(r, dtype=float)
    x, y, z = r
    r_mag = float(np.linalg.norm(r))
    common = -1.5 * j2 * mu * r_eq**2 / r_mag**5
    z_ratio = 5.0 * z * z / (r_mag * r_mag)
    return common * np.array([
        x * (1.0 - z_ratio),
        y * (1.0 - z_ratio),
        z * (3.0 - z_ratio),
    ])


def atmospheric_density(altitude_m: float) -> float:
    """Coarse exponential atmosphere (kg/m^3) above the reference altitude."""
    return ATMOSPHERE_RHO0 * math.exp(-(altitude_m - ATMOSPHERE_H0) / ATMOSPHERE_SCALE_HEIGHT)


def drag_acceleration(
    r: np.ndarray,
    v: np.ndarray,
    cd_area_over_mass: float,
    omega: float = EARTH_ANGULAR_VELOCITY,
) -> np.ndarray:
    """Atmospheric drag: a = -0.5 * rho * |v_rel| * (Cd*A/m) * v_rel.

    Velocity is taken relative to a co-rotating atmosphere. cd_area_over_mass is the
    inverse ballistic coefficient Cd*A/m (m^2/kg).
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    altitude = float(np.linalg.norm(r)) - EARTH_RADIUS
    rho = atmospheric_density(altitude)
    v_rel = v - np.cross([0.0, 0.0, omega], r)
    v_rel_mag = float(np.linalg.norm(v_rel))
    return -0.5 * rho * v_rel_mag * cd_area_over_mass * v_rel


def third_body_acceleration(r: np.ndarray, r_third: np.ndarray, mu_third: float) -> np.ndarray:
    """Third-body perturbation (Battin's formulation, cancels the common-mode term).

    a = mu_third * ( (r_third - r)/|r_third - r|^3  -  r_third/|r_third|^3 )
    """
    r = np.asarray(r, dtype=float)
    r_third = np.asarray(r_third, dtype=float)
    d = r_third - r
    return mu_third * (d / float(np.linalg.norm(d)) ** 3
                       - r_third / float(np.linalg.norm(r_third)) ** 3)


@dataclass
class ForceModel:
    """Composable acceleration model. Enable only the perturbations you need.

    mu:                central-body gravitational parameter (m^3/s^2).
    use_j2 / j2 / r_eq: oblateness term and its reference radius.
    use_drag / cd_area_over_mass: exponential-atmosphere drag (Cd*A/m, m^2/kg).
    third_bodies:      iterable of (mu_third, position_func(t) -> r_third).
    """

    mu: float = MU_EARTH
    use_j2: bool = False
    j2: float = EARTH_J2
    r_eq: float = EARTH_RADIUS_EQUATORIAL
    use_drag: bool = False
    cd_area_over_mass: float = 0.02
    third_bodies: tuple[tuple[float, Callable[[float], np.ndarray]], ...] = field(default_factory=tuple)

    def acceleration(self, t: float, r: np.ndarray, v: np.ndarray) -> np.ndarray:
        a = two_body_acceleration(r, self.mu)
        if self.use_j2:
            a = a + j2_acceleration(r, self.mu, self.j2, self.r_eq)
        if self.use_drag:
            a = a + drag_acceleration(r, v, self.cd_area_over_mass)
        for mu_third, position_func in self.third_bodies:
            a = a + third_body_acceleration(r, position_func(t), mu_third)
        return a
