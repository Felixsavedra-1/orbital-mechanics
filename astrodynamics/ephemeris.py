"""Approximate heliocentric planetary ephemerides (Standish, JPL approx_pos.html,
valid 1800-2050): J2000 ecliptic elements plus linear rates per Julian century.
Sub-arcmin for the inner planets — adequate for launch-window analysis without
SPICE kernels. All states heliocentric, J2000 ecliptic frame, SI units.
"""

from __future__ import annotations

import datetime as _dt
import math

from constants import AU, MU_SUN
from astrodynamics.state import OrbitalElements, StateVector, elements_to_state, solve_kepler, true_from_eccentric

# Standard epoch J2000.0 = 2000-01-01 12:00 TT.
J2000_JD = 2451545.0
_DAYS_PER_CENTURY = 36525.0

# Per planet: J2000 values then rates per Julian century, columns a (AU), e, I (deg),
# L (deg), longitude of perihelion (deg), longitude of ascending node (deg).
_ELEMENTS = {
    "Mercury": (
        (0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593),
        (0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081),
    ),
    "Venus": (
        (0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255),
        (0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418),
    ),
    "Earth": (  # Earth-Moon barycenter
        (1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0),
        (0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0),
    ),
    "Mars": (
        (1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891),
        (0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343),
    ),
    "Jupiter": (
        (5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909),
        (-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106),
    ),
    "Saturn": (
        (9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448),
        (-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794),
    ),
    "Uranus": (
        (19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503),
        (-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589),
    ),
    "Neptune": (
        (30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574),
        (0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664),
    ),
}


def datetime_to_jd(when: _dt.datetime) -> float:
    """Julian Date from a UTC datetime (UTC treated as TT; the offset is negligible here)."""
    year, month = when.year, when.month
    day_frac = when.day + (when.hour + when.minute / 60.0 + when.second / 3600.0) / 24.0
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day_frac + b - 1524.5
    )


def jd_to_datetime(jd: float) -> _dt.datetime:
    """Inverse of datetime_to_jd (UTC), to second resolution."""
    jd += 0.5
    f, z = math.modf(jd)
    z = int(z)
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day_int = int(day)
    seconds = int(round((day - day_int) * 86400.0))
    return _dt.datetime(year, month, day_int) + _dt.timedelta(seconds=seconds)


def planet_elements(name: str, jd: float) -> OrbitalElements:
    """Heliocentric J2000-ecliptic orbital elements of a planet at the given JD."""
    if name not in _ELEMENTS:
        raise ValueError(f"unknown planet '{name}'; known: {', '.join(_ELEMENTS)}")
    base, rate = _ELEMENTS[name]
    t = (jd - J2000_JD) / _DAYS_PER_CENTURY  # Julian centuries past J2000

    a_au = base[0] + rate[0] * t
    e = base[1] + rate[1] * t
    inc = base[2] + rate[2] * t
    mean_longitude = base[3] + rate[3] * t
    long_peri = base[4] + rate[4] * t
    long_node = base[5] + rate[5] * t

    argp_deg = long_peri - long_node
    mean_anom_deg = (mean_longitude - long_peri + 180.0) % 360.0 - 180.0  # wrap to [-180,180)

    E = solve_kepler(math.radians(mean_anom_deg), e)
    nu = true_from_eccentric(E, e)
    return OrbitalElements(
        a=a_au * AU,
        e=e,
        i=math.radians(inc),
        raan=math.radians(long_node) % (2.0 * math.pi),
        argp=math.radians(argp_deg) % (2.0 * math.pi),
        nu=nu,
        epoch=jd,
    )


def planet_state(name: str, jd: float) -> StateVector:
    """Heliocentric J2000-ecliptic Cartesian state (m, m/s) of a planet at the given JD."""
    return elements_to_state(planet_elements(name, jd), MU_SUN)
