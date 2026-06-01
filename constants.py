G = 6.67430e-11          # m^3 kg^-1 s^-2, CODATA 2018
AU = 149_597_870_700.0   # meters, IAU 2012 Resolution B2

SUN_MASS = 1.98892e30    # kg, IAU 2015 Resolution B3
EARTH_MASS = 5.9722e24   # kg, NASA Earth fact sheet (2024)

# Standard gravitational parameters mu = G*M (m^3 s^-2). Published mu values are
# measured far more precisely than G or M individually, so the astrodynamics layer
# uses these directly rather than reconstructing G*M (which would inherit G's ~22 ppm
# uncertainty). Sources: IAU 2015 / JPL DE440 / NASA planetary fact sheets.
MU_SUN = 1.32712440018e20   # m^3 s^-2, IAU 2015 (heliocentric)
MU_EARTH = 3.986004418e14   # m^3 s^-2, EGM2008 / WGS84
MU_MARS = 4.282837e13       # m^3 s^-2, JPL Mars GM
MU_MOON = 4.9028000e12      # m^3 s^-2, JPL Lunar GM

# Semi-major axis of lunar orbit; actual range 356,500–406,700 km (e ≈ 0.0549)
MOON_ORBITAL_RADIUS = 384_400_000.0  # m, NASA Moon fact sheet (2024)

EARTH_RADIUS = 6_371_000.0  # m, volumetric mean, NASA Earth fact sheet (2024)
ISS_ALTITUDE = 408_000.0    # m, approximate mean as of 2024-Q1; decays ~2 km/year

# Perturbation-model parameters (Earth). J2 is the dominant non-spherical gravity term;
# the equatorial radius (not the volumetric mean above) is the reference radius it scales
# against, so they must be used together.
EARTH_J2 = 1.08262668e-3          # dimensionless, EGM96 oblateness coefficient
EARTH_RADIUS_EQUATORIAL = 6_378_137.0  # m, WGS84 equatorial radius (J2 reference)
EARTH_ANGULAR_VELOCITY = 7.2921159e-5  # rad/s, sidereal rotation (co-rotating atmosphere)

# Coarse exponential atmosphere anchored at 400 km (rho = RHO0 * exp(-(h - H0)/H_SCALE)).
# Adequate to show drag-driven decay for LEO demonstrations; not a substitute for NRLMSISE.
ATMOSPHERE_RHO0 = 3.614e-12   # kg/m^3 at the reference altitude (Vallado, ~400 km)
ATMOSPHERE_H0 = 400_000.0     # m, reference altitude
ATMOSPHERE_SCALE_HEIGHT = 60_000.0  # m, representative scale height near 400-500 km

DATA_VALIDATION_DATE = "2025-01-01"  # last verified against NASA/JPL/CODATA/IAU sources; update manually when re-verified

# Orbital eccentricities at epoch J2000.0, from JPL Horizons
EARTH_ECCENTRICITY = 0.0167086   # NASA Earth fact sheet (2024)
MARS_ECCENTRICITY  = 0.0934      # NASA Mars fact sheet (2024)

STANDARD_GRAVITY = 9.80665  # m/s², exact by BIPM/IAU definition; used in Tsiolkovsky Isp conversion
