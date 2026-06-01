import datetime
import math
import unittest

import numpy as np

from astrodynamics.ephemeris import (
    datetime_to_jd,
    jd_to_datetime,
    J2000_JD,
    planet_state,
)
from astrodynamics.lambert import solve_lambert
from astrodynamics.porkchop import best_transfer, solve_transfer
from constants import AU, MU_SUN

_MU_EARTH_CURTIS = 398600e9  # km^3/s^2 -> SI, the textbook value


class TestLambertTextbook(unittest.TestCase):
    def test_curtis_example_5_2(self):
        # Curtis, Orbital Mechanics for Engineering Students, Example 5.2.
        # r in km, v in km/s, mu = 398600 km^3/s^2, prograde, tof = 3600 s.
        r1 = np.array([5000.0, 10000.0, 2100.0]) * 1000.0
        r2 = np.array([-14600.0, 2500.0, 7000.0]) * 1000.0
        v1, v2 = solve_lambert(r1, r2, 3600.0, _MU_EARTH_CURTIS, prograde=True)

        v1_expected = np.array([-5.9925, 1.9254, 3.2456]) * 1000.0
        v2_expected = np.array([-3.3125, -4.1966, -0.38529]) * 1000.0
        np.testing.assert_allclose(v1, v1_expected, rtol=0, atol=1.0)  # within 1 m/s
        np.testing.assert_allclose(v2, v2_expected, rtol=0, atol=1.0)

    def test_round_trip_consistency(self):
        # The solved v1 must actually carry r1 to r2: re-deriving from the orbit's
        # geometry, |v1| should match vis-viva at r1.
        r1 = np.array([7000e3, 0.0, 0.0])
        r2 = np.array([0.0, 8000e3, 0.0])
        v1, v2 = solve_lambert(r1, r2, 2000.0, _MU_EARTH_CURTIS)
        # Energy from r1,v1 and from r2,v2 must be equal (same transfer orbit).
        eps1 = 0.5 * np.dot(v1, v1) - _MU_EARTH_CURTIS / np.linalg.norm(r1)
        eps2 = 0.5 * np.dot(v2, v2) - _MU_EARTH_CURTIS / np.linalg.norm(r2)
        self.assertAlmostEqual(eps1 / eps2, 1.0, places=6)

    def test_singular_geometry_raises(self):
        r1 = np.array([7000e3, 0.0, 0.0])
        with self.assertRaises(ValueError):
            solve_lambert(r1, -r1, 2000.0, _MU_EARTH_CURTIS)  # 180-degree transfer

    def test_rejects_bad_tof(self):
        r1 = np.array([7000e3, 0.0, 0.0])
        r2 = np.array([0.0, 8000e3, 0.0])
        with self.assertRaises(ValueError):
            solve_lambert(r1, r2, 0.0, _MU_EARTH_CURTIS)


class TestEphemeris(unittest.TestCase):
    def test_julian_date_j2000(self):
        # 2000-01-01 12:00 UTC is JD 2451545.0 by definition.
        self.assertAlmostEqual(
            datetime_to_jd(datetime.datetime(2000, 1, 1, 12, 0, 0)), J2000_JD, places=6
        )

    def test_jd_datetime_round_trip(self):
        for dt in (
            datetime.datetime(2020, 7, 30, 11, 50, 0),
            datetime.datetime(1999, 12, 31, 23, 59, 0),
            datetime.datetime(2035, 6, 15, 6, 0, 0),
        ):
            recovered = jd_to_datetime(datetime_to_jd(dt))
            self.assertLess(abs((recovered - dt).total_seconds()), 2.0)

    def test_earth_heliocentric_distance(self):
        # Earth's heliocentric distance stays within [perihelion, aphelion] ~ [0.983, 1.017] AU.
        for year in range(2000, 2031, 3):
            jd = datetime_to_jd(datetime.datetime(year, 4, 1))
            r_au = planet_state("Earth", jd).r_mag / AU
            self.assertTrue(0.98 < r_au < 1.02, f"Earth r = {r_au} AU in {year}")

    def test_earth_near_perihelion_at_j2000(self):
        # Earth reaches perihelion in early January, so at J2000 it is near 0.983 AU.
        r_au = planet_state("Earth", J2000_JD).r_mag / AU
        self.assertAlmostEqual(r_au, 0.9833, delta=0.001)

    def test_earth_orbital_speed(self):
        v_km_s = planet_state("Earth", J2000_JD).v_mag / 1000.0
        self.assertAlmostEqual(v_km_s, 29.8, delta=0.5)

    def test_mars_heliocentric_distance(self):
        # Mars ranges ~1.38 (perihelion) to ~1.67 (aphelion) AU.
        for year in range(2000, 2031, 2):
            jd = datetime_to_jd(datetime.datetime(year, 1, 1))
            r_au = planet_state("Mars", jd).r_mag / AU
            self.assertTrue(1.35 < r_au < 1.70, f"Mars r = {r_au} AU in {year}")


class TestPorkchop(unittest.TestCase):
    def test_earth_mars_window_is_physical(self):
        # Scan ~3 years (covers at least one synodic window) and confirm the optimum
        # lands in the physically expected band for an Earth->Mars Hohmann-class transfer.
        start = datetime_to_jd(datetime.datetime(2024, 1, 1))
        departure_jds = [start + 15.0 * k for k in range(75)]      # ~3.1 years, 15-day steps
        tof_grid = [120.0 + 15.0 * k for k in range(17)]           # 120..360 days
        best = best_transfer("Earth", "Mars", departure_jds, tof_grid)

        # Real Earth->Mars minimum-energy departures sit around C3 ~ 8-20 km^2/s^2.
        self.assertTrue(7.0 < best.c3_km2_s2 < 25.0, f"C3 = {best.c3_km2_s2}")
        self.assertTrue(2.5 < best.v_inf_depart_km_s < 5.0, f"v_inf_dep = {best.v_inf_depart_km_s}")
        self.assertTrue(2.0 < best.v_inf_arrive_km_s < 4.0, f"v_inf_arr = {best.v_inf_arrive_km_s}")
        self.assertTrue(120.0 <= best.tof_days <= 360.0)

    def test_solve_transfer_rejects_bad_tof(self):
        with self.assertRaises(ValueError):
            solve_transfer("Earth", "Mars", J2000_JD, -5.0)


class TestMissionReportSection(unittest.TestCase):
    """The 'mission' report section wires the astrodynamics layer into the engine."""

    def test_section_is_valid_but_excluded_from_all(self):
        import report

        self.assertIn("mission", report.VALID_SECTIONS)
        self.assertNotIn("mission", report.SECTION_ORDER)  # keeps 'all' stdlib-only and stable

    def test_collect_records_count_and_physicality(self):
        from report import collect_records

        records = collect_records("mission")
        self.assertEqual(len(records), 7)
        by_label = {r.label: r for r in records}
        self.assertTrue(7.0 < by_label["Departure C3"].value_num < 25.0)
        self.assertTrue(120.0 <= by_label["Time of flight"].value_num <= 360.0)

    def test_renders_in_all_formats(self):
        from report import render_report

        text = render_report("mission", "text")
        self.assertIn("LAMBERT/PORKCHOP", text)
        self.assertIn("Departure C3", text)

        import json
        payload = json.loads(render_report("mission", "json"))
        self.assertEqual(len(payload["records"]), 7)

        csv_out = render_report("mission", "csv")
        self.assertEqual(csv_out.count("\n"), 7)  # header + 7 records, last line not trailing

    def test_all_section_unaffected(self):
        # The 'all' aggregation must still be exactly 38 records (mission excluded).
        from report import collect_records

        self.assertEqual(len(collect_records("all")), 38)


if __name__ == "__main__":
    unittest.main()
