"""Perturbing accelerations: zonal gravity (J2..Jn), atmospheric drag, solar radiation
pressure, and third-body. Each is a free function; `ForceModel` composes the enabled
ones for the integrator. ECI frame, SI units; the zonal z-axis is the spin axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from constants import (
    ATMOSPHERE_BANDS,
    AU,
    EARTH_ANGULAR_VELOCITY,
    EARTH_J2,
    EARTH_RADIUS,
    EARTH_RADIUS_EQUATORIAL,
    MU_EARTH,
    SOLAR_PRESSURE_1AU,
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


def zonal_acceleration(r: np.ndarray, mu: float, r_eq: float, j: tuple[float, ...]) -> np.ndarray:
    """Zonal-harmonic acceleration (gradient of the disturbing potential), ECI frame.

    ``j`` lists unnormalized coefficients starting at J2. Legendre recurrence per
    Vallado Sec. 8.6 / Montenbruck & Gill Sec. 3.2; j=(J2,) reproduces j2_acceleration.
    """
    r = np.asarray(r, dtype=float)
    x, y, z = r
    r_mag = float(np.linalg.norm(r))
    s = z / r_mag  # sin(latitude)

    n_max = len(j) + 1
    p = [0.0] * (n_max + 1)
    dp = [0.0] * (n_max + 1)
    p[0], p[1] = 1.0, s
    dp[0], dp[1] = 0.0, 1.0
    for n in range(2, n_max + 1):
        p[n] = ((2 * n - 1) * s * p[n - 1] - (n - 1) * p[n - 2]) / n
        dp[n] = n * (s * p[n] - p[n - 1]) / (s * s - 1.0) if s * s != 1.0 else 0.0

    # U_p = -(mu/r) * sum_n Jn (R/r)^n P_n(s); dU_dr is the radial partial, dU_dlat
    # the partial wrt s = sin(latitude).
    dU_dr = 0.0
    dU_dlat = 0.0
    for n in range(2, n_max + 1):
        jn = j[n - 2]
        rn = (r_eq / r_mag) ** n
        dU_dr += (n + 1) * rn * jn * p[n]
        dU_dlat += rn * jn * dp[n]
    dU_dr *= mu / (r_mag * r_mag)
    dU_dlat *= mu / r_mag

    # Project onto ECI axes: ds/dx = -xz/r^3, ds/dy = -yz/r^3, ds/dz = (x^2+y^2)/r^3.
    rho_xy_sq = x * x + y * y
    common_r = dU_dr / r_mag
    ax = common_r * x + dU_dlat * (x * z) / (r_mag ** 3)
    ay = common_r * y + dU_dlat * (y * z) / (r_mag ** 3)
    az = common_r * z - dU_dlat * rho_xy_sq / (r_mag ** 3)
    return np.array([ax, ay, az])


def atmospheric_density(altitude_m: float) -> float:
    """Banded exponential density (kg/m^3) from ATMOSPHERE_BANDS (Vallado Table 8-4)."""
    band = ATMOSPHERE_BANDS[0]
    for candidate in ATMOSPHERE_BANDS:
        if altitude_m >= candidate[0]:
            band = candidate
        else:
            break
    h0, rho0, scale_height = band
    return rho0 * math.exp(-(altitude_m - h0) / scale_height)


def srp_acceleration(
    r_sat: np.ndarray,
    r_sun: np.ndarray,
    cr_area_over_mass: float,
    occulting_radius: float = EARTH_RADIUS,
) -> np.ndarray:
    """Cannonball SRP with a cylindrical shadow (Vallado Sec. 8.6), ECI frame.

    a = -P(1AU) * (Cr*A/m) * (AU/d_sun)^2 * u_sun; zero inside the umbra behind the
    occulting body. ``cr_area_over_mass`` is Cr*A/m (m^2/kg).
    """
    r_sat = np.asarray(r_sat, dtype=float)
    r_sun = np.asarray(r_sun, dtype=float)
    sat_to_sun = r_sun - r_sat
    d_sun = float(np.linalg.norm(sat_to_sun))
    u_sun = sat_to_sun / d_sun

    sun_hat = r_sun / float(np.linalg.norm(r_sun))
    along = float(np.dot(r_sat, sun_hat))
    perp = float(np.linalg.norm(r_sat - along * sun_hat))
    if along < 0.0 and perp < occulting_radius:
        return np.zeros(3)

    pressure = SOLAR_PRESSURE_1AU * (AU / d_sun) ** 2
    return -pressure * cr_area_over_mass * u_sun


def drag_acceleration(
    r: np.ndarray,
    v: np.ndarray,
    cd_area_over_mass: float,
    omega: float = EARTH_ANGULAR_VELOCITY,
) -> np.ndarray:
    """Drag a = -0.5 * rho * |v_rel| * (Cd*A/m) * v_rel, relative to a co-rotating atmosphere."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    altitude = float(np.linalg.norm(r)) - EARTH_RADIUS
    rho = atmospheric_density(altitude)
    v_rel = v - np.cross([0.0, 0.0, omega], r)
    v_rel_mag = float(np.linalg.norm(v_rel))
    return -0.5 * rho * v_rel_mag * cd_area_over_mass * v_rel


def third_body_acceleration(r: np.ndarray, r_third: np.ndarray, mu_third: float) -> np.ndarray:
    """Third-body perturbation a = mu * ((r_third - r)/|r_third - r|^3 - r_third/|r_third|^3)."""
    r = np.asarray(r, dtype=float)
    r_third = np.asarray(r_third, dtype=float)
    d = r_third - r
    return mu_third * (d / float(np.linalg.norm(d)) ** 3
                       - r_third / float(np.linalg.norm(r_third)) ** 3)


@dataclass
class ForceModel:
    """Composable acceleration model; enable only the perturbations you need.

    ``zonal`` (a tuple starting at J2) supersedes ``use_j2`` when set. SRP requires
    ``sun_position(t) -> r_sun``; ``third_bodies`` is (mu, position_func(t)) pairs.
    """

    mu: float = MU_EARTH
    use_j2: bool = False
    j2: float = EARTH_J2
    r_eq: float = EARTH_RADIUS_EQUATORIAL
    zonal: tuple[float, ...] | None = None
    use_drag: bool = False
    cd_area_over_mass: float = 0.02
    use_srp: bool = False
    cr_area_over_mass: float = 0.01
    sun_position: Callable[[float], np.ndarray] | None = None
    third_bodies: tuple[tuple[float, Callable[[float], np.ndarray]], ...] = field(default_factory=tuple)

    def acceleration(self, t: float, r: np.ndarray, v: np.ndarray) -> np.ndarray:
        a = two_body_acceleration(r, self.mu)
        if self.zonal is not None:
            a = a + zonal_acceleration(r, self.mu, self.r_eq, self.zonal)
        elif self.use_j2:
            a = a + j2_acceleration(r, self.mu, self.j2, self.r_eq)
        if self.use_drag:
            a = a + drag_acceleration(r, v, self.cd_area_over_mass)
        if self.use_srp:
            if self.sun_position is None:
                raise ValueError("use_srp requires sun_position(t) -> r_sun")
            a = a + srp_acceleration(r, self.sun_position(t), self.cr_area_over_mass)
        for mu_third, position_func in self.third_bodies:
            a = a + third_body_acceleration(r, position_func(t), mu_third)
        return a
