import math
import unittest

import numpy as np

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
from calculations import calculate_orbital_period, calculate_orbital_velocity
from constants import EARTH_MASS, MU_EARTH

_TWO_PI = 2.0 * math.pi


class TestKeplerSolver(unittest.TestCase):
    def test_circular_returns_mean_anomaly(self):
        # e = 0 makes Kepler's equation E = M.
        for m in (0.0, 0.5, math.pi, 4.0):
            self.assertAlmostEqual(solve_kepler(m, 0.0), m % _TWO_PI, places=12)

    def test_satisfies_keplers_equation(self):
        # E - e*sin(E) must reproduce the input mean anomaly across the elliptical range.
        for e in (0.0, 0.1, 0.5, 0.9, 0.99):
            for m in np.linspace(-math.pi, math.pi, 9):
                E = solve_kepler(m, e)
                # Compare modulo 2pi: +pi and -pi are the same anomaly, opposite wrap.
                residual = math.remainder((E - e * math.sin(E)) - m, _TWO_PI)
                self.assertAlmostEqual(residual, 0.0, places=10)

    def test_boundary_anomalies(self):
        self.assertAlmostEqual(solve_kepler(0.0, 0.7), 0.0, places=12)
        self.assertAlmostEqual(solve_kepler(math.pi, 0.7), math.pi, places=10)

    def test_invalid_eccentricity_raises(self):
        for bad_e in (-0.1, 1.0, 1.5, float("nan")):
            with self.assertRaises(ValueError):
                solve_kepler(0.5, bad_e)


class TestAnomalyConversions(unittest.TestCase):
    def test_round_trip_true_eccentric(self):
        for e in (0.0, 0.2, 0.7, 0.95):
            for nu in np.linspace(0.1, _TWO_PI - 0.1, 7):
                E = eccentric_from_true(nu, e)
                self.assertAlmostEqual(true_from_eccentric(E, e), nu, places=10)

    def test_mean_from_eccentric_matches_keplers_equation(self):
        e = 0.3
        E = 1.234
        self.assertAlmostEqual(mean_from_eccentric(E, e), (E - e * math.sin(E)) % _TWO_PI, places=12)


class TestElementsStateRoundTrip(unittest.TestCase):
    def _assert_elements_close(self, got, want, places=6):
        self.assertAlmostEqual(got.a, want.a, delta=abs(want.a) * 1e-9)
        self.assertAlmostEqual(got.e, want.e, places=places)
        self.assertAlmostEqual(got.i, want.i, places=places)
        self.assertAlmostEqual(got.raan, want.raan, places=places)
        self.assertAlmostEqual(got.argp, want.argp, places=places)
        self.assertAlmostEqual(got.nu, want.nu, places=places)

    def test_canonical_round_trip(self):
        # A generic, non-singular orbit (inclined, eccentric) recovers exactly.
        elements = OrbitalElements(
            a=7.0e6, e=0.05, i=math.radians(45.0),
            raan=math.radians(60.0), argp=math.radians(30.0), nu=math.radians(120.0),
        )
        recovered = state_to_elements(elements_to_state(elements, MU_EARTH), MU_EARTH)
        self._assert_elements_close(recovered, elements)

    def test_randomized_round_trip(self):
        rng = np.random.default_rng(42)
        for _ in range(200):
            elements = OrbitalElements(
                a=rng.uniform(7.0e6, 5.0e11),
                e=rng.uniform(0.01, 0.8),
                i=rng.uniform(0.05, math.pi - 0.05),
                raan=rng.uniform(0.05, _TWO_PI - 0.05),
                argp=rng.uniform(0.05, _TWO_PI - 0.05),
                nu=rng.uniform(0.05, _TWO_PI - 0.05),
            )
            recovered = state_to_elements(elements_to_state(elements, MU_EARTH), MU_EARTH)
            self._assert_elements_close(recovered, elements, places=5)


class TestStateToElementsTextbook(unittest.TestCase):
    def test_curtis_example_4_3(self):
        # Curtis, Orbital Mechanics for Engineering Students, Example 4.3.
        # mu = 398600 km^3/s^2; r, v in km and km/s. Published results below.
        mu = 398600e9  # the textbook's mu, in SI
        r = np.array([-6045.0, -3490.0, 2500.0]) * 1000.0
        v = np.array([-3.457, 6.618, 2.533]) * 1000.0
        coe = state_to_elements(StateVector(r, v), mu)

        self.assertAlmostEqual(coe.a / 1000.0, 8788.0, delta=1.0)         # km
        self.assertAlmostEqual(coe.e, 0.1712, places=4)
        self.assertAlmostEqual(math.degrees(coe.i), 153.2, delta=0.1)
        self.assertAlmostEqual(math.degrees(coe.raan), 255.3, delta=0.1)
        self.assertAlmostEqual(math.degrees(coe.argp), 20.07, delta=0.1)
        self.assertAlmostEqual(math.degrees(coe.nu), 28.45, delta=0.1)


class TestSingularCases(unittest.TestCase):
    def test_circular_equatorial(self):
        # e=0, i=0: argp and raan undefined -> 0; in-plane angle carried in nu.
        elements = OrbitalElements(a=7.0e6, e=0.0, i=0.0, raan=0.0, argp=0.0, nu=math.radians(75.0))
        recovered = state_to_elements(elements_to_state(elements, MU_EARTH), MU_EARTH)
        self.assertAlmostEqual(recovered.e, 0.0, places=9)
        self.assertAlmostEqual(recovered.i, 0.0, places=9)
        self.assertAlmostEqual(recovered.nu, math.radians(75.0), places=6)

    def test_circular_inclined(self):
        # e=0, i!=0: nu carries the argument of latitude (node -> position).
        elements = OrbitalElements(
            a=7.0e6, e=0.0, i=math.radians(50.0), raan=math.radians(40.0), argp=0.0, nu=math.radians(100.0)
        )
        recovered = state_to_elements(elements_to_state(elements, MU_EARTH), MU_EARTH)
        self.assertAlmostEqual(recovered.e, 0.0, places=9)
        self.assertAlmostEqual(math.degrees(recovered.i), 50.0, places=6)
        self.assertAlmostEqual(math.degrees(recovered.raan), 40.0, places=6)
        self.assertAlmostEqual(math.degrees(recovered.nu), 100.0, places=5)


class TestConsistencyWithRootEngine(unittest.TestCase):
    """The high-fidelity layer must agree with the proven two-body engine on circular orbits."""

    def test_circular_speed_matches_calculations(self):
        radius = 7.0e6
        elements = OrbitalElements(a=radius, e=0.0, i=0.0, raan=0.0, argp=0.0, nu=0.0)
        state = elements_to_state(elements, MU_EARTH)
        # calculate_orbital_velocity uses G*M; convert its km/s result to m/s for comparison.
        expected_ms = calculate_orbital_velocity(radius, EARTH_MASS) * 1000.0
        # MU_EARTH and G*EARTH_MASS differ at the ~1e-4 level, so compare with a loose rel tol.
        self.assertAlmostEqual(state.v_mag / expected_ms, 1.0, places=3)

    def test_full_period_returns_to_start(self):
        radius = 7.0e6
        elements = OrbitalElements(a=radius, e=0.1, i=math.radians(30.0),
                                   raan=0.0, argp=0.0, nu=math.radians(10.0))
        period_s = calculate_orbital_period(radius, EARTH_MASS) * 3600.0
        advanced = propagate_kepler(elements, period_s, MU_EARTH)
        # One full period returns to the same true anomaly (mod 2pi).
        diff = (advanced.nu - elements.nu) % _TWO_PI
        self.assertTrue(min(diff, _TWO_PI - diff) < 1e-3, f"nu drift {diff}")


class TestPropagateKepler(unittest.TestCase):
    def test_energy_conserved(self):
        elements = OrbitalElements(a=2.0e7, e=0.3, i=0.5, raan=1.0, argp=2.0, nu=0.5)
        advanced = propagate_kepler(elements, 1234.0, MU_EARTH)
        self.assertAlmostEqual(advanced.a, elements.a, delta=elements.a * 1e-12)
        self.assertEqual(advanced.e, elements.e)

    def test_epoch_advances(self):
        elements = OrbitalElements(a=2.0e7, e=0.3, i=0.5, raan=1.0, argp=2.0, nu=0.5, epoch=100.0)
        self.assertEqual(propagate_kepler(elements, 50.0, MU_EARTH).epoch, 150.0)


class TestValidation(unittest.TestCase):
    def test_elements_to_state_rejects_bad_a(self):
        with self.assertRaises(ValueError):
            elements_to_state(OrbitalElements(a=-1.0, e=0.1, i=0, raan=0, argp=0, nu=0), MU_EARTH)

    def test_rejects_bad_mu(self):
        elements = OrbitalElements(a=7e6, e=0.1, i=0, raan=0, argp=0, nu=0)
        with self.assertRaises(ValueError):
            elements_to_state(elements, 0.0)

    def test_state_to_elements_rejects_zero_radius(self):
        with self.assertRaises(ValueError):
            state_to_elements(StateVector([0, 0, 0], [1, 0, 0]), MU_EARTH)

    def test_hyperbolic_eccentricity_rejected(self):
        with self.assertRaises(ValueError):
            eccentric_from_true(0.5, 1.2)


if __name__ == "__main__":
    unittest.main()
