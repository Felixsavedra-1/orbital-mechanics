import math
import unittest

import numpy as np

from astrodynamics.forces import (
    ForceModel,
    atmospheric_density,
    j2_acceleration,
    third_body_acceleration,
    two_body_acceleration,
)
from astrodynamics.integrators import (
    Trajectory,
    max_relative_energy_drift,
    propagate,
    specific_angular_momentum,
    specific_energy,
)
from astrodynamics.state import (
    OrbitalElements,
    StateVector,
    elements_to_state,
    propagate_kepler,
    state_to_elements,
)
from constants import ATMOSPHERE_H0, ATMOSPHERE_RHO0, EARTH_J2, EARTH_RADIUS_EQUATORIAL, MU_EARTH


def _leo_state(a=7.0e6, e=0.001, i_deg=45.0, raan_deg=30.0, argp_deg=0.0, nu_deg=0.0):
    elements = OrbitalElements(
        a=a, e=e, i=math.radians(i_deg),
        raan=math.radians(raan_deg), argp=math.radians(argp_deg), nu=math.radians(nu_deg),
    )
    return elements, elements_to_state(elements, MU_EARTH)


def _period(a):
    return 2.0 * math.pi * math.sqrt(a**3 / MU_EARTH)


class TestForceFunctions(unittest.TestCase):
    def test_two_body_magnitude_and_direction(self):
        r = np.array([7.0e6, 0.0, 0.0])
        a = two_body_acceleration(r, MU_EARTH)
        self.assertAlmostEqual(np.linalg.norm(a), MU_EARTH / 7.0e6**2, places=6)
        # Points back toward the central body (-x here).
        self.assertLess(a[0], 0.0)
        self.assertAlmostEqual(a[1], 0.0)
        self.assertAlmostEqual(a[2], 0.0)

    def test_j2_is_small_perturbation(self):
        r = np.array([7.0e6, 0.0, 0.0])
        ratio = np.linalg.norm(j2_acceleration(r, MU_EARTH, EARTH_J2, EARTH_RADIUS_EQUATORIAL)) \
            / np.linalg.norm(two_body_acceleration(r, MU_EARTH))
        self.assertTrue(1e-4 < ratio < 1e-2, f"J2/two-body = {ratio}")

    def test_third_body_vanishes_at_origin(self):
        # A satellite co-located with the central body feels ~no differential pull.
        a = third_body_acceleration(np.zeros(3), np.array([1.5e11, 0.0, 0.0]), 1.327e20)
        self.assertLess(np.linalg.norm(a), 1e-12)

    def test_atmospheric_density_reference(self):
        self.assertAlmostEqual(atmospheric_density(ATMOSPHERE_H0), ATMOSPHERE_RHO0, places=18)
        self.assertLess(atmospheric_density(ATMOSPHERE_H0 + 100e3), atmospheric_density(ATMOSPHERE_H0))


class TestTwoBodyConservation(unittest.TestCase):
    def test_energy_and_momentum_conserved(self):
        _, state = _leo_state(e=0.2)
        fm = ForceModel(mu=MU_EARTH)  # point mass only
        traj = propagate(state.r, state.v, (0.0, 10.0 * _period(7.0e6)), fm, n_eval=300, rtol=1e-11)

        self.assertLess(max_relative_energy_drift(traj, MU_EARTH), 1e-9)
        h0 = specific_angular_momentum(traj.r[0], traj.v[0])
        hf = specific_angular_momentum(traj.final_r, traj.final_v)
        np.testing.assert_allclose(hf, h0, rtol=1e-9)

    def test_matches_analytic_kepler(self):
        # The numeric integrator must reproduce the exact two-body solution.
        elements, state = _leo_state(e=0.15)
        dt = 0.7 * _period(elements.a)
        fm = ForceModel(mu=MU_EARTH)
        traj = propagate(state.r, state.v, (0.0, dt), fm, n_eval=2, rtol=1e-12, atol=1e-9)

        analytic = elements_to_state(propagate_kepler(elements, dt, MU_EARTH), MU_EARTH)
        np.testing.assert_allclose(traj.final_r, analytic.r, atol=1.0)      # within 1 m
        np.testing.assert_allclose(traj.final_v, analytic.v, atol=1e-3)     # within 1 mm/s


class TestJ2Regression(unittest.TestCase):
    def test_no_j2_means_no_nodal_drift(self):
        elements, state = _leo_state()
        traj = propagate(state.r, state.v, (0.0, 8.0 * _period(elements.a)),
                         ForceModel(mu=MU_EARTH), n_eval=2, rtol=1e-11)
        final = state_to_elements(StateVector(traj.final_r, traj.final_v), MU_EARTH)
        drift = ((final.raan - elements.raan + math.pi) % (2 * math.pi)) - math.pi
        self.assertLess(abs(drift), 1e-4)

    def test_nodal_regression_matches_secular_rate(self):
        # Sampling after an integer number of orbits cancels the short-period osculating
        # term, leaving the J2 secular nodal regression to compare against theory:
        #   raan_dot = -1.5 * n * J2 * (R_eq / p)^2 * cos(i)
        a, e, i = 7.0e6, 0.001, math.radians(45.0)
        elements, state = _leo_state(a=a, e=e, i_deg=45.0)
        n_orbits = 16
        t_total = n_orbits * _period(a)

        fm = ForceModel(mu=MU_EARTH, use_j2=True)
        traj = propagate(state.r, state.v, (0.0, t_total), fm, n_eval=2, rtol=1e-12, atol=1e-9)
        final = state_to_elements(StateVector(traj.final_r, traj.final_v), MU_EARTH)

        n = math.sqrt(MU_EARTH / a**3)
        p = a * (1.0 - e * e)
        raan_dot = -1.5 * n * EARTH_J2 * (EARTH_RADIUS_EQUATORIAL / p) ** 2 * math.cos(i)
        expected = raan_dot * t_total
        measured = ((final.raan - elements.raan + math.pi) % (2 * math.pi)) - math.pi

        self.assertTrue(expected < 0, "prograde orbit should regress (raan decreasing)")
        self.assertAlmostEqual(measured / expected, 1.0, delta=0.05)  # within 5%


class TestDragDecay(unittest.TestCase):
    def test_drag_removes_energy(self):
        # A high area-to-mass object at 400 km: drag must strictly reduce orbital energy.
        r0 = EARTH_RADIUS_EQUATORIAL + 400e3
        elements, state = _leo_state(a=r0, e=0.0, i_deg=30.0)
        fm = ForceModel(mu=MU_EARTH, use_drag=True, cd_area_over_mass=0.5)
        traj = propagate(state.r, state.v, (0.0, 20.0 * _period(r0)), fm, n_eval=2, rtol=1e-10)

        e_before = specific_energy(traj.r[0], traj.v[0], MU_EARTH)
        e_after = specific_energy(traj.final_r, traj.final_v, MU_EARTH)
        self.assertLess(e_after, e_before)  # energy decreased -> orbit decaying
        a_after = state_to_elements(StateVector(traj.final_r, traj.final_v), MU_EARTH).a
        self.assertLess(a_after, r0)


class TestPropagateValidation(unittest.TestCase):
    def test_rejects_degenerate_span(self):
        _, state = _leo_state()
        with self.assertRaises(ValueError):
            propagate(state.r, state.v, (0.0, 0.0), ForceModel())


if __name__ == "__main__":
    unittest.main()
