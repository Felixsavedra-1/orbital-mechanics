"""Adaptive propagation of perturbed orbits: scipy DOP853 (8th-order Dormand-Prince)
driven by an arbitrary ForceModel, plus energy/momentum conservation diagnostics
whose drift under point-mass gravity bounds the numerical error.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.integrate import solve_ivp

from astrodynamics.forces import ForceModel


@dataclass
class Trajectory:
    """Sampled propagation result. r and v are (N, 3); t is (N,)."""

    t: np.ndarray
    r: np.ndarray
    v: np.ndarray

    @property
    def final_r(self) -> np.ndarray:
        return self.r[-1]

    @property
    def final_v(self) -> np.ndarray:
        return self.v[-1]


def propagate(
    r0: npt.ArrayLike,
    v0: npt.ArrayLike,
    t_span: tuple[float, float],
    force_model: ForceModel,
    n_eval: int = 200,
    rtol: float = 1e-10,
    atol: float = 1e-12,
) -> Trajectory:
    """Propagate an initial state over t_span under force_model using DOP853."""
    r0 = np.asarray(r0, dtype=float).reshape(3)
    v0 = np.asarray(v0, dtype=float).reshape(3)
    t0, t1 = t_span
    if n_eval < 2:
        raise ValueError("n_eval must be >= 2")
    if not np.isfinite([t0, t1]).all() or t1 == t0:
        raise ValueError("t_span must be finite and non-degenerate")

    def rhs(t, y):
        r = y[:3]
        v = y[3:]
        return np.concatenate((v, force_model.acceleration(t, r, v)))

    t_eval = np.linspace(t0, t1, n_eval)
    sol = solve_ivp(
        rhs, (t0, t1), np.concatenate((r0, v0)),
        method="DOP853", t_eval=t_eval, rtol=rtol, atol=atol,
    )
    if not sol.success:
        raise RuntimeError(f"integration failed: {sol.message}")
    return Trajectory(t=sol.t, r=sol.y[:3].T, v=sol.y[3:].T)


def specific_energy(r: npt.ArrayLike, v: npt.ArrayLike, mu: float) -> float:
    """Specific orbital energy eps = v^2/2 - mu/r (J/kg)."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    return 0.5 * float(np.dot(v, v)) - mu / float(np.linalg.norm(r))


def specific_angular_momentum(r: npt.ArrayLike, v: npt.ArrayLike) -> np.ndarray:
    """Specific angular momentum vector h = r x v (m^2/s)."""
    return np.cross(np.asarray(r, dtype=float), np.asarray(v, dtype=float))


def max_relative_energy_drift(trajectory: Trajectory, mu: float) -> float:
    """Largest |E(t) - E(0)| / |E(0)| over the trajectory. ~0 for point-mass gravity."""
    energies = np.array([specific_energy(r, v, mu) for r, v in zip(trajectory.r, trajectory.v)])
    return float(np.max(np.abs(energies - energies[0]) / abs(energies[0])))
