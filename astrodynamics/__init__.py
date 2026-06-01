"""High-fidelity astrodynamics layer.

This package sits alongside the dependency-light root engine (calculations.py,
propagator.py) and adds full 6-element orbital state, real transfer design, and
perturbed propagation. It depends on numpy/scipy; the root engine does not.
"""

from astrodynamics.state import (
    OrbitalElements,
    StateVector,
    eccentric_from_true,
    elements_to_state,
    mean_from_eccentric,
    propagate_kepler,
    solve_kepler,
    state_to_elements,
    true_from_eccentric,
)

__all__ = [
    "OrbitalElements",
    "StateVector",
    "eccentric_from_true",
    "elements_to_state",
    "mean_from_eccentric",
    "propagate_kepler",
    "solve_kepler",
    "state_to_elements",
    "true_from_eccentric",
]
