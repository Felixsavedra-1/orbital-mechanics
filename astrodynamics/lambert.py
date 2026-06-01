"""Lambert's problem: find the transfer orbit connecting two position vectors in a
given time of flight.

This is the engine behind real interplanetary mission design — given where the
departure body is now and where the target body will be after a chosen cruise time,
Lambert returns the heliocentric velocities at both ends, from which departure C3 and
arrival v-infinity follow.

Implementation: the universal-variable formulation (Bate-Mueller-White; Curtis,
*Orbital Mechanics for Engineering Students*, Algorithm 5.2), with a Newton iteration
on the universal variable z. Single-revolution transfers only; multi-rev is a future
extension. Validated against Curtis Example 5.2.
"""

from __future__ import annotations

import math

import numpy as np

_TWO_PI = 2.0 * math.pi


def _stumpff_c(z: float) -> float:
    """Stumpff function C(z), series-stabilized near z = 0."""
    if z > 1e-6:
        sz = math.sqrt(z)
        return (1.0 - math.cos(sz)) / z
    if z < -1e-6:
        sz = math.sqrt(-z)
        return (math.cosh(sz) - 1.0) / (-z)
    return 0.5 - z / 24.0 + z * z / 720.0


def _stumpff_s(z: float) -> float:
    """Stumpff function S(z), series-stabilized near z = 0."""
    if z > 1e-6:
        sz = math.sqrt(z)
        return (sz - math.sin(sz)) / sz**3
    if z < -1e-6:
        sz = math.sqrt(-z)
        return (math.sinh(sz) - sz) / sz**3
    return 1.0 / 6.0 - z / 120.0 + z * z / 5040.0


def solve_lambert(
    r1,
    r2,
    tof: float,
    mu: float,
    prograde: bool = True,
    tol: float = 1e-9,
    max_iter: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve Lambert's problem for the single-revolution transfer.

    Args:
        r1, r2: initial and final position vectors (m), inertial frame.
        tof:    time of flight (s, > 0).
        mu:     gravitational parameter of the central body (m^3/s^2).
        prograde: True for a prograde transfer, False for retrograde.

    Returns:
        (v1, v2): velocity vectors (m/s) at r1 and r2 on the transfer orbit.

    Raises:
        ValueError: For non-physical inputs, a 0 or 180 degree transfer (the
                    geometry is singular), or failure to converge.
    """
    r1 = np.asarray(r1, dtype=float).reshape(3)
    r2 = np.asarray(r2, dtype=float).reshape(3)
    if not math.isfinite(tof) or tof <= 0.0:
        raise ValueError("tof must be a finite positive number")
    if not math.isfinite(mu) or mu <= 0.0:
        raise ValueError("mu must be a finite positive number")

    R1 = float(np.linalg.norm(r1))
    R2 = float(np.linalg.norm(r2))
    if R1 == 0.0 or R2 == 0.0:
        raise ValueError("position vectors must be non-zero")

    cross = np.cross(r1, r2)
    cos_dnu = max(-1.0, min(1.0, float(np.dot(r1, r2)) / (R1 * R2)))
    dnu = math.acos(cos_dnu)
    # Resolve the transfer direction from the sign of the orbit normal's z-component.
    if prograde:
        if cross[2] < 0.0:
            dnu = _TWO_PI - dnu
    else:
        if cross[2] >= 0.0:
            dnu = _TWO_PI - dnu

    sin_dnu = math.sin(dnu)
    # A 0 or 180 degree transfer leaves the orbit plane undefined. Test the angle
    # itself (scale-independent) rather than A, whose size scales with distance.
    if abs(sin_dnu) < 1e-8:
        raise ValueError("transfer angle is ~0 or 180 degrees; Lambert geometry is singular")
    A = sin_dnu * math.sqrt(R1 * R2 / (1.0 - cos_dnu))

    def y_of(z: float) -> float:
        return R1 + R2 + A * (z * _stumpff_s(z) - 1.0) / math.sqrt(_stumpff_c(z))

    # Start at z = 0, nudging upward until y is positive so sqrt(y) is real.
    z = 0.0
    while y_of(z) < 0.0:
        z += 0.1

    sqrt_mu_tof = math.sqrt(mu) * tof
    ratio = 1.0
    for _ in range(max_iter):
        # Physical single-rev solutions sit in a bounded z window; a step running far
        # past it means this date/TOF pairing has no such transfer (skip the cell).
        if not math.isfinite(z) or z < -1.0e5:
            raise ValueError("Lambert iteration diverged (no single-rev transfer for this geometry)")
        C = _stumpff_c(z)
        S = _stumpff_s(z)
        y = y_of(z)
        if y < 0.0:
            raise ValueError("Lambert iteration left the feasible region (y < 0)")
        F = (y / C) ** 1.5 * S + A * math.sqrt(y) - sqrt_mu_tof
        if abs(z) > 1e-6:
            dF = (y / C) ** 1.5 * (
                (1.0 / (2.0 * z)) * (C - 3.0 * S / (2.0 * C)) + 3.0 * S * S / (4.0 * C)
            ) + (A / 8.0) * (3.0 * (S / C) * math.sqrt(y) + A * math.sqrt(C / y))
        else:
            y0 = y_of(0.0)
            dF = (math.sqrt(2.0) / 40.0) * y0**1.5 + (A / 8.0) * (
                math.sqrt(y0) + A * math.sqrt(1.0 / (2.0 * y0))
            )
        if dF == 0.0 or not math.isfinite(dF):
            raise ValueError("Lambert iteration became unstable (zero/non-finite derivative)")
        ratio = F / dF
        z -= ratio
        if abs(ratio) < tol:
            break
    else:
        raise ValueError(f"Lambert solver did not converge in {max_iter} iterations")

    y = y_of(z)
    f = 1.0 - y / R1            # Lagrange coefficients
    g = A * math.sqrt(y / mu)
    g_dot = 1.0 - y / R2

    v1 = (r2 - f * r1) / g
    v2 = (g_dot * r2 - r1) / g
    return v1, v2
