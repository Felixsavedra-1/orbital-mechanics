"""Validation against JPL Horizons ground-truth state vectors.

This is the credibility capstone: the approximate ephemeris and the numerical propagator
are checked against authoritative NASA/JPL Horizons data, not just against themselves.

Reference vectors were retrieved from the JPL Horizons API
(https://ssd.jpl.nasa.gov/api/horizons.api) with:
    EPHEM_TYPE=VECTORS, CENTER='500@10' (Sun), REF_PLANE=ECLIPTIC, REF_SYSTEM=J2000,
    VEC_TABLE=2, OUT_UNITS=KM-S
for the Earth-Moon barycenter (COMMAND='3', matching the Standish 'Earth' row) and the
Mars barycenter (COMMAND='4'). Units below are SI (m, m/s).

Tolerances are set with margin above the observed errors and documented inline. The
Standish approximate ephemeris is sub-arcsecond-to-arcsecond here (~1300 km Earth,
~10000 km Mars at 1-1.5 AU); the two-body propagator tracks real Earth motion to ~14 km
over a week, the residual being the planetary perturbations a two-body model omits.
"""

import unittest

import numpy as np

from astrodynamics.ephemeris import planet_state
from astrodynamics.forces import ForceModel
from astrodynamics.integrators import propagate
from constants import MU_SUN

_KM = 1000.0
_DAY = 86400.0

# JD 2461406.5 TDB = A.D. 2027-Jan-01 00:00:00.0 (heliocentric, ecliptic J2000).
_JD_EPOCH = 2461406.5
_HORIZONS = {
    "Earth": {  # COMMAND='3' (Earth-Moon Barycenter)
        "r": np.array([-2.541047480590650e07, 1.448936154946475e08, -8.935287214748561e03]) * _KM,
        "v": np.array([-2.982544951504148e01, -5.258485798178566e00, 4.875343952035482e-04]) * _KM,
    },
    "Mars": {  # COMMAND='4' (Mars Barycenter)
        "r": np.array([-1.532446117500856e08, 1.927147721956801e08, 7.796052716044843e06]) * _KM,
        "v": np.array([-1.805050209328578e01, -1.301696781950783e01, 1.697758444657609e-01]) * _KM,
    },
}

# Earth-Moon Barycenter 7 days later: JD 2461413.5 TDB = 2027-Jan-08 00:00:00.0.
_JD_EPOCH_PLUS_7 = 2461413.5
_EARTH_PLUS_7 = {
    "r": np.array([-4.320959428503995e07, 1.406179295134815e08, -8.572642230778933e03]) * _KM,
    "v": np.array([-2.895926019970437e01, -8.862687613212557e00, 7.101721033562214e-04]) * _KM,
}


class TestEphemerisAgainstHorizons(unittest.TestCase):
    def test_earth_position_and_velocity(self):
        state = planet_state("Earth", _JD_EPOCH)
        d_pos = np.linalg.norm(state.r - _HORIZONS["Earth"]["r"]) / _KM
        d_vel = np.linalg.norm(state.v - _HORIZONS["Earth"]["v"])
        self.assertLess(d_pos, 5_000.0, f"Earth position error {d_pos:.0f} km")   # observed ~1315
        self.assertLess(d_vel, 3.0, f"Earth velocity error {d_vel:.3f} m/s")       # observed ~0.66

    def test_mars_position_and_velocity(self):
        state = planet_state("Mars", _JD_EPOCH)
        d_pos = np.linalg.norm(state.r - _HORIZONS["Mars"]["r"]) / _KM
        d_vel = np.linalg.norm(state.v - _HORIZONS["Mars"]["v"])
        self.assertLess(d_pos, 30_000.0, f"Mars position error {d_pos:.0f} km")    # observed ~10340
        self.assertLess(d_vel, 5.0, f"Mars velocity error {d_vel:.3f} m/s")        # observed ~1.35


class TestPropagatorAgainstHorizons(unittest.TestCase):
    def test_two_body_tracks_real_earth_over_a_week(self):
        # Seed the propagator with the real Horizons state and integrate 7 days under
        # Sun point-mass gravity; compare to the real state a week later.
        r0 = _HORIZONS["Earth"]["r"]
        v0 = _HORIZONS["Earth"]["v"]
        dt = (_JD_EPOCH_PLUS_7 - _JD_EPOCH) * _DAY

        traj = propagate(r0, v0, (0.0, dt), ForceModel(mu=MU_SUN), n_eval=2, rtol=1e-12, atol=1e-6)
        d_pos = np.linalg.norm(traj.final_r - _EARTH_PLUS_7["r"]) / _KM
        d_vel = np.linalg.norm(traj.final_v - _EARTH_PLUS_7["v"])
        # Residual is omitted planetary perturbations, not integration error. Observed ~14 km.
        self.assertLess(d_pos, 200.0, f"7-day propagation error {d_pos:.1f} km")
        self.assertLess(d_vel, 1.0, f"7-day velocity error {d_vel:.3f} m/s")


if __name__ == "__main__":
    unittest.main()
