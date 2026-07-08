"""High-fidelity astrodynamics layer (numpy/scipy): full 6-element orbital state,
real transfer design, and perturbed propagation. The stdlib root engine does not
depend on this package.
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
