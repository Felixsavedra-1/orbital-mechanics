"""Orbital state core: classical elements <-> Cartesian state, and Kepler propagation.

SI units (meters, seconds, radians), inertial frame whose +Z axis is the reference-plane
normal (ecliptic pole for heliocentric work, ECI for Earth). Conventions follow Curtis,
*Orbital Mechanics for Engineering Students* (Algorithms 4.1 and 4.5) and Vallado,
*Fundamentals of Astrodynamics and Applications* (RV2COE/COE2RV). Only elliptical orbits
(0 <= e < 1) are supported; hyperbolic transfers are handled by the Lambert solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Below these thresholds an orbit is treated as circular / equatorial, where the
# corresponding angle (argp / raan) is mathematically undefined and folded into the
# anomaly per the standard convention. Chosen well above float64 noise.
_CIRCULAR_TOL = 1e-11
_EQUATORIAL_TOL = 1e-11
_TWO_PI = 2.0 * math.pi


@dataclass
class OrbitalElements:
    """Classical (Keplerian) orbital elements.

    a:    semi-major axis (m, > 0 for ellipses)
    e:    eccentricity (0 <= e < 1)
    i:    inclination (rad, 0..pi)
    raan: right ascension of the ascending node / longitude of node (rad, 0..2pi)
    argp: argument of periapsis (rad, 0..2pi)
    nu:   true anomaly (rad, 0..2pi)
    epoch: optional seconds-since-reference tag carried through propagation
    """

    a: float
    e: float
    i: float
    raan: float
    argp: float
    nu: float
    epoch: float | None = None


@dataclass
class StateVector:
    """Inertial Cartesian state: position and velocity (m, m/s)."""

    r: np.ndarray
    v: np.ndarray
    epoch: float | None = None

    def __post_init__(self) -> None:
        self.r = np.asarray(self.r, dtype=float).reshape(3)
        self.v = np.asarray(self.v, dtype=float).reshape(3)

    @property
    def r_mag(self) -> float:
        """Position magnitude |r| (m)."""
        return float(np.linalg.norm(self.r))

    @property
    def v_mag(self) -> float:
        """Speed |v| (m/s)."""
        return float(np.linalg.norm(self.v))


def _require_eccentricity(e: float) -> None:
    if not math.isfinite(e) or e < 0.0 or e >= 1.0:
        raise ValueError(f"eccentricity must satisfy 0 <= e < 1 (elliptical); got {e}")


def _require_mu(mu: float) -> None:
    if not math.isfinite(mu) or mu <= 0.0:
        raise ValueError(f"mu must be a finite positive number; got {mu}")


def _require_semi_major_axis(a: float) -> None:
    if not math.isfinite(a) or a <= 0.0:
        raise ValueError(f"semi-major axis a must be finite and positive; got {a}")


def solve_kepler(mean_anomaly: float, e: float, tol: float = 1e-12, max_iter: int = 100) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for eccentric anomaly E (rad).

    Newton-Raphson from a robust initial guess. Converges to ~1e-12 in a handful of
    iterations across the full elliptical range, including e near 1.

    Raises:
        ValueError: If e is not in [0, 1), or the iteration fails to converge.
    """
    _require_eccentricity(e)
    if not math.isfinite(mean_anomaly):
        raise ValueError("mean_anomaly must be finite")

    m = math.remainder(mean_anomaly, _TWO_PI)  # wrap to [-pi, pi] for fast convergence
    # Danby's starter: biased toward apoapsis where curvature is worst.
    E = m + (0.85 * e if m >= 0 else -0.85 * e) if e > 0.8 else m + e * math.sin(m)

    for _ in range(max_iter):
        f = E - e * math.sin(E) - m
        f_prime = 1.0 - e * math.cos(E)
        dE = f / f_prime
        E -= dE
        if abs(dE) < tol:
            return E % _TWO_PI
    raise ValueError(
        f"Kepler solver did not converge for M={mean_anomaly}, e={e} in {max_iter} iterations"
    )


def true_from_eccentric(E: float, e: float) -> float:
    """True anomaly (rad, 0..2pi) from eccentric anomaly E."""
    _require_eccentricity(e)
    nu = 2.0 * math.atan2(math.sqrt(1.0 + e) * math.sin(E / 2.0),
                          math.sqrt(1.0 - e) * math.cos(E / 2.0))
    return nu % _TWO_PI


def eccentric_from_true(nu: float, e: float) -> float:
    """Eccentric anomaly (rad, 0..2pi) from true anomaly nu."""
    _require_eccentricity(e)
    E = 2.0 * math.atan2(math.sqrt(1.0 - e) * math.sin(nu / 2.0),
                        math.sqrt(1.0 + e) * math.cos(nu / 2.0))
    return E % _TWO_PI


def mean_from_eccentric(E: float, e: float) -> float:
    """Mean anomaly (rad, 0..2pi) from eccentric anomaly E via Kepler's equation."""
    _require_eccentricity(e)
    return (E - e * math.sin(E)) % _TWO_PI


def _rotation_perifocal_to_inertial(raan: float, i: float, argp: float) -> np.ndarray:
    """3-1-3 rotation Rz(raan) @ Rx(i) @ Rz(argp): perifocal (PQW) -> inertial."""
    cO, sO = math.cos(raan), math.sin(raan)
    ci, si = math.cos(i), math.sin(i)
    cw, sw = math.cos(argp), math.sin(argp)
    return np.array([
        [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
        [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
        [sw * si, cw * si, ci],
    ])


def elements_to_state(elements: OrbitalElements, mu: float) -> StateVector:
    """Convert classical elements to an inertial Cartesian state (Curtis Algorithm 4.5).

    Raises:
        ValueError: If mu <= 0, e not in [0, 1), or a <= 0.
    """
    _require_mu(mu)
    _require_eccentricity(elements.e)
    _require_semi_major_axis(elements.a)

    a, e, nu = elements.a, elements.e, elements.nu
    p = a * (1.0 - e * e)
    r_mag = p / (1.0 + e * math.cos(nu))

    # Perifocal (PQW) frame: periapsis along +P, motion toward +Q.
    r_pqw = r_mag * np.array([math.cos(nu), math.sin(nu), 0.0])
    v_pqw = math.sqrt(mu / p) * np.array([-math.sin(nu), e + math.cos(nu), 0.0])

    rot = _rotation_perifocal_to_inertial(elements.raan, elements.i, elements.argp)
    return StateVector(rot @ r_pqw, rot @ v_pqw, epoch=elements.epoch)


def _clamp_unit(x: float) -> float:
    """Clamp to [-1, 1] so floating-point drift never trips math.acos domain errors."""
    return max(-1.0, min(1.0, x))


def state_to_elements(state: StateVector, mu: float) -> OrbitalElements:
    """Convert an inertial Cartesian state to classical elements (Curtis Algorithm 4.1).

    Singular cases are handled per the standard convention: for a circular orbit the
    argument of periapsis is set to 0 and the in-plane angle is carried in nu (argument
    of latitude / true longitude); for an equatorial orbit the node longitude is 0.

    Raises:
        ValueError: If mu <= 0, or the state is degenerate (zero radius or zero
                    angular momentum, i.e. radial/rectilinear motion).
    """
    _require_mu(mu)
    r_vec = np.asarray(state.r, dtype=float).reshape(3)
    v_vec = np.asarray(state.v, dtype=float).reshape(3)

    r = float(np.linalg.norm(r_vec))
    v = float(np.linalg.norm(v_vec))
    if r == 0.0:
        raise ValueError("position vector has zero magnitude")

    h_vec = np.cross(r_vec, v_vec)
    h = float(np.linalg.norm(h_vec))
    if h == 0.0:
        raise ValueError("zero angular momentum (rectilinear motion has no orbital plane)")

    n_vec = np.cross([0.0, 0.0, 1.0], h_vec)  # node vector (points to ascending node)
    n = float(np.linalg.norm(n_vec))

    e_vec = (np.cross(v_vec, h_vec) / mu) - (r_vec / r)
    e = float(np.linalg.norm(e_vec))

    # Semi-major axis from the vis-viva / energy relation.
    energy = 0.5 * v * v - mu / r
    if abs(energy) < 1e-30:
        raise ValueError("parabolic state (zero specific energy) is not supported")
    a = -mu / (2.0 * energy)

    i = math.acos(_clamp_unit(h_vec[2] / h))

    equatorial = n < _EQUATORIAL_TOL
    circular = e < _CIRCULAR_TOL

    if not equatorial:
        raan = math.acos(_clamp_unit(n_vec[0] / n))
        if n_vec[1] < 0.0:
            raan = _TWO_PI - raan
    else:
        raan = 0.0

    if not circular and not equatorial:
        argp = math.acos(_clamp_unit(float(np.dot(n_vec, e_vec)) / (n * e)))
        if e_vec[2] < 0.0:
            argp = _TWO_PI - argp
    elif not circular and equatorial:
        # Elliptical equatorial: argp -> longitude of periapsis measured from +X.
        argp = math.acos(_clamp_unit(e_vec[0] / e))
        if e_vec[1] < 0.0:
            argp = _TWO_PI - argp
    else:
        argp = 0.0

    if not circular:
        nu = math.acos(_clamp_unit(float(np.dot(e_vec, r_vec)) / (e * r)))
        if float(np.dot(r_vec, v_vec)) < 0.0:
            nu = _TWO_PI - nu
    elif not equatorial:
        # Circular inclined: nu -> argument of latitude (node to position).
        nu = math.acos(_clamp_unit(float(np.dot(n_vec, r_vec)) / (n * r)))
        if r_vec[2] < 0.0:
            nu = _TWO_PI - nu
    else:
        # Circular equatorial: nu -> true longitude (X axis to position).
        nu = math.acos(_clamp_unit(r_vec[0] / r))
        if r_vec[1] < 0.0:
            nu = _TWO_PI - nu

    return OrbitalElements(a=a, e=e, i=i, raan=raan, argp=argp, nu=nu % _TWO_PI, epoch=state.epoch)


def propagate_kepler(elements: OrbitalElements, dt: float, mu: float) -> OrbitalElements:
    """Advance elements by dt seconds along the unperturbed two-body orbit.

    Analytic (no integration error): convert nu -> mean anomaly, advance by n*dt, solve
    Kepler's equation, convert back. Only nu (and epoch) change. This is the exact
    two-body solution and serves as ground truth for the numerical propagator.

    Raises:
        ValueError: If mu <= 0, e not in [0, 1), a <= 0, or dt is not finite.
    """
    _require_mu(mu)
    _require_eccentricity(elements.e)
    _require_semi_major_axis(elements.a)
    if not math.isfinite(dt):
        raise ValueError("dt must be finite")

    n_motion = math.sqrt(mu / elements.a**3)
    E0 = eccentric_from_true(elements.nu, elements.e)
    M0 = mean_from_eccentric(E0, elements.e)
    E1 = solve_kepler(M0 + n_motion * dt, elements.e)
    nu1 = true_from_eccentric(E1, elements.e)

    new_epoch = None if elements.epoch is None else elements.epoch + dt
    return OrbitalElements(
        a=elements.a, e=elements.e, i=elements.i,
        raan=elements.raan, argp=elements.argp, nu=nu1, epoch=new_epoch,
    )
