from typing import NamedTuple

from constants import AU, EARTH_ECCENTRICITY, EARTH_MASS, EARTH_RADIUS, ISS_ALTITUDE, MARS_ECCENTRICITY, MOON_ORBITAL_RADIUS, SUN_MASS


class OrbitalBody(NamedTuple):
    name: str
    orbital_radius_m: float
    central_mass_kg: float
    body_type: str = ""


class ConceptStation(NamedTuple):
    name: str
    distance_m: float
    note: str = ""


class TransferOrbit(NamedTuple):
    name: str
    r1_m: float
    r2_m: float
    central_mass_kg: float
    note: str = ""


# Semi-major axes (AU) from JPL Horizons, epoch J2000.0
PLANET_SEMIMAJOR_AXIS_AU: list[tuple[str, float]] = [
    ("Mercury", 0.38709927),
    ("Venus",   0.72333566),
    ("Earth",   1.00000261),
    ("Mars",    1.52371034),
    ("Jupiter", 5.20288700),
    ("Saturn",  9.53667594),
    ("Uranus",  19.18916464),
    ("Neptune", 30.06992276),
]

PLANETS: list[OrbitalBody] = [OrbitalBody(name, axis_au * AU, SUN_MASS) for name, axis_au in PLANET_SEMIMAJOR_AXIS_AU]

EARTH_ORBITS: list[OrbitalBody] = [
    OrbitalBody("Moon", MOON_ORBITAL_RADIUS, EARTH_MASS, "Natural satellite"),
    OrbitalBody("ISS", EARTH_RADIUS + ISS_ALTITUDE, EARTH_MASS, "Space station"),
]

ISS_TO_MOON_DISTANCE = MOON_ORBITAL_RADIUS - (EARTH_RADIUS + ISS_ALTITUDE)


def _find_planet(name: str) -> OrbitalBody:
    for body in PLANETS:
        if body.name == name:
            return body
    raise ValueError(f"Planet '{name}' not found in PLANETS list")


EARTH_ORBITAL_RADIUS = _find_planet("Earth").orbital_radius_m
MARS_ORBITAL_RADIUS = _find_planet("Mars").orbital_radius_m

# Lower-bound separation: Mars at perihelion, Earth at aphelion (coplanar heuristic).
# Not actual minimum conjunction distance; see constants.py for eccentricity sources.
EARTH_MARS_MIN_SEPARATION_LOWER_BOUND = (
    MARS_ORBITAL_RADIUS * (1 - MARS_ECCENTRICITY) - EARTH_ORBITAL_RADIUS * (1 + EARTH_ECCENTRICITY)
)

CONCEPT_STATIONS: list[ConceptStation] = [
    ConceptStation(
        "Earth-Moon midpoint",
        MOON_ORBITAL_RADIUS / 2,
        "Based on average Earth-Moon distance",
    ),
    ConceptStation(
        "Earth-Mars midpoint",
        EARTH_MARS_MIN_SEPARATION_LOWER_BOUND / 2,
        "Based on perihelion/aphelion lower-bound Earth-Mars separation",
    ),
]

TRANSFER_ORBITS: list[TransferOrbit] = [
    TransferOrbit(
        name="LEO-Moon",
        r1_m=EARTH_RADIUS + ISS_ALTITUDE,
        r2_m=MOON_ORBITAL_RADIUS,
        central_mass_kg=EARTH_MASS,
        note="Low Earth orbit (ISS altitude) to lunar orbit",
    ),
    TransferOrbit(
        name="Earth-Mars",
        r1_m=EARTH_ORBITAL_RADIUS,
        r2_m=MARS_ORBITAL_RADIUS,
        central_mass_kg=SUN_MASS,
        note="Earth heliocentric orbit to Mars heliocentric orbit",
    ),
]
