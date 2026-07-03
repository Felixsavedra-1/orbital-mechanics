import math
import unittest

import numpy as np

from astrodynamics.forces import (
    ForceModel,
    atmospheric_density,
    j2_acceleration,
    srp_acceleration,
    third_body_acceleration,
    two_body_acceleration,
    zonal_acceleration,
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
from constants import (
    ATMOSPHERE_BANDS,
    AU,
    EARTH_J2,
    EARTH_RADIUS,
    EARTH_RADIUS_EQUATORIAL,
    EARTH_ZONAL_J2_TO_J6,
    MU_EARTH,
    SOLAR_PRESSURE_1AU,
)


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
        # At each band's base altitude the density equals that band's base value exactly.
        for h0, rho0, _ in ATMOSPHERE_BANDS:
            self.assertAlmostEqual(atmospheric_density(h0), rho0, delta=rho0 * 1e-12)
        # Density falls off monotonically with altitude.
        self.assertLess(atmospheric_density(500e3), atmospheric_density(400e3))
        self.assertLess(atmospheric_density(400e3), atmospheric_density(200e3))

    def test_zonal_reduces_to_j2(self):
        # zonal_acceleration with only J2 must reproduce the standalone J2 term.
        for r in (np.array([7.0e6, 1.2e6, 0.8e6]), np.array([6.8e6, 0.0, 3.0e6])):
            z = zonal_acceleration(r, MU_EARTH, EARTH_RADIUS_EQUATORIAL, (EARTH_J2,))
            j = j2_acceleration(r, MU_EARTH, EARTH_J2, EARTH_RADIUS_EQUATORIAL)
            np.testing.assert_allclose(z, j, rtol=1e-10)

    def test_higher_order_zonal_is_small_correction(self):
        # J3..J6 perturb the J2 acceleration by a fraction of a percent, never more than J2.
        r = np.array([7.0e6, 1.2e6, 0.8e6])
        j2_only = zonal_acceleration(r, MU_EARTH, EARTH_RADIUS_EQUATORIAL, (EARTH_J2,))
        full = zonal_acceleration(r, MU_EARTH, EARTH_RADIUS_EQUATORIAL, EARTH_ZONAL_J2_TO_J6)
        rel = np.linalg.norm(full - j2_only) / np.linalg.norm(j2_only)
        self.assertTrue(0.0 < rel < 0.05, f"higher-order/J2 = {rel}")

    def test_srp_magnitude_and_shadow(self):
        # Sunlit satellite: |a| = P(1AU) * (AU/d)^2 * Cr*A/m, directed away from the Sun.
        r_sun = np.array([AU, 0.0, 0.0])
        r_sat = np.array([7.0e6, 0.0, 0.0])  # sunlit (between Earth and Sun side)
        cr_am = 0.02
        a = srp_acceleration(r_sat, r_sun, cr_am)
        d = np.linalg.norm(r_sun - r_sat)
        expected = SOLAR_PRESSURE_1AU * (AU / d) ** 2 * cr_am
        self.assertAlmostEqual(np.linalg.norm(a), expected, delta=expected * 1e-9)
        self.assertLess(a[0], 0.0)  # pushed away from the Sun (-x)

        # Eclipsed satellite (directly behind Earth, anti-Sun side): zero SRP.
        r_eclipsed = np.array([-7.0e6, 0.0, 0.0])
        self.assertEqual(np.linalg.norm(srp_acceleration(r_eclipsed, r_sun, cr_am)), 0.0)


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


class TestForceModelComposition(unittest.TestCase):
    def test_srp_requires_sun_position(self):
        _, state = _leo_state()
        with self.assertRaises(ValueError):
            propagate(state.r, state.v, (0.0, 100.0), ForceModel(use_srp=True))

    def test_zonal_and_srp_compose(self):
        # Full zonal field + SRP (with a fixed Sun direction) integrates to a finite,
        # near-circular LEO state — the perturbations are small corrections to two-body.
        _, state = _leo_state()
        sun = np.array([AU, 0.0, 0.0])
        fm = ForceModel(
            mu=MU_EARTH, zonal=EARTH_ZONAL_J2_TO_J6,
            use_srp=True, cr_area_over_mass=0.01, sun_position=lambda t: sun,
        )
        traj = propagate(state.r, state.v, (0.0, 2.0 * _period(7.0e6)), fm, n_eval=50, rtol=1e-10)
        self.assertTrue(np.all(np.isfinite(traj.final_r)))
        self.assertTrue(EARTH_RADIUS < np.linalg.norm(traj.final_r) < 8.0e6)


class TestPropagateValidation(unittest.TestCase):
    def test_rejects_degenerate_span(self):
        _, state = _leo_state()
        with self.assertRaises(ValueError):
            propagate(state.r, state.v, (0.0, 0.0), ForceModel())


if __name__ == "__main__":
    unittest.main()
