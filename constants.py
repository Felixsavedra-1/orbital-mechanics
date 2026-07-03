G = 6.67430e-11          # m^3 kg^-1 s^-2, CODATA 2018
AU = 149_597_870_700.0   # meters, IAU 2012 Resolution B2

SUN_MASS = 1.98892e30    # kg, IAU 2015 Resolution B3
EARTH_MASS = 5.9722e24   # kg, NASA Earth fact sheet (2024)

# Standard gravitational parameters mu = G*M (m^3 s^-2), used directly because published
# mu values are far more precise than G or M alone. Sources: IAU 2015 / JPL DE440 / NASA.
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

# Higher-order zonal harmonics (axisymmetric gravity). Unnormalized J_n coefficients from
# EGM96; together with J2 they capture the dominant non-spherical field for orbits that do
# not resolve longitude-dependent (tesseral) terms. Same reference radius as J2.
EARTH_J3 = -2.53265649e-6   # dimensionless, EGM96
EARTH_J4 = -1.61962159e-6   # dimensionless, EGM96
EARTH_J5 = -2.27296083e-7   # dimensionless, EGM96
EARTH_J6 =  5.40681239e-7   # dimensionless, EGM96
EARTH_ZONAL_J2_TO_J6 = (EARTH_J2, EARTH_J3, EARTH_J4, EARTH_J5, EARTH_J6)

# Solar radiation pressure at 1 AU: P = solar irradiance / c = 1361 / 2.998e8.
SOLAR_PRESSURE_1AU = 4.5604e-6  # N/m^2 (Vallado, Fundamentals of Astrodynamics, Sec. 8.6)

# Banded exponential atmosphere: piecewise rho(h) = rho0 * exp(-(h - h0)/H) with the base
# altitude h0 (m), base density rho0 (kg/m^3), and scale height H (m) selected by altitude
# band. Source: Vallado Table 8-4 (exponential atmospheric model, derived from CIRA-72/US
# Standard 1976). Far more realistic across the LEO range than a single anchor; still an
# analytic model, not a substitute for NRLMSISE-00. Bands listed by ascending base altitude.
ATMOSPHERE_BANDS = (
    # (h0_m,      rho0_kg_m3,   scale_height_m)
    (0.0,         1.225,        7_249.0),
    (25_000.0,    3.899e-2,     6_349.0),
    (30_000.0,    1.774e-2,     6_682.0),
    (40_000.0,    3.972e-3,     7_554.0),
    (50_000.0,    1.057e-3,     8_382.0),
    (60_000.0,    3.206e-4,     7_714.0),
    (70_000.0,    8.770e-5,     6_549.0),
    (80_000.0,    1.905e-5,     5_799.0),
    (90_000.0,    3.396e-6,     5_382.0),
    (100_000.0,   5.297e-7,     5_877.0),
    (110_000.0,   9.661e-8,     7_263.0),
    (120_000.0,   2.438e-8,     9_473.0),
    (130_000.0,   8.484e-9,     12_636.0),
    (140_000.0,   3.845e-9,     16_149.0),
    (150_000.0,   2.070e-9,     22_523.0),
    (180_000.0,   5.464e-10,    29_740.0),
    (200_000.0,   2.789e-10,    37_105.0),
    (250_000.0,   7.248e-11,    45_546.0),
    (300_000.0,   2.418e-11,    53_628.0),
    (350_000.0,   9.518e-12,    53_298.0),
    (400_000.0,   3.725e-12,    58_515.0),
    (450_000.0,   1.585e-12,    60_828.0),
    (500_000.0,   6.967e-13,    63_822.0),
    (600_000.0,   1.454e-13,    71_835.0),
    (700_000.0,   3.614e-14,    88_667.0),
    (800_000.0,   1.170e-14,    124_640.0),
    (900_000.0,   5.245e-15,    181_050.0),
    (1_000_000.0, 3.019e-15,    268_000.0),
)

# Parking / capture orbit defaults for the impulsive interplanetary delta-v budget.
EARTH_PARKING_ALTITUDE = 200_000.0  # m, typical LEO departure parking orbit
MARS_RADIUS = 3_389_500.0           # m, IAU mean radius (NASA Mars fact sheet, 2024)
MARS_CAPTURE_ALTITUDE = 400_000.0   # m, representative low-Mars capture periapsis
MARS_CAPTURE_ECCENTRICITY = 0.0     # circular capture orbit by default

DATA_VALIDATION_DATE = "2025-01-01"  # last verified against NASA/JPL/CODATA/IAU sources

# Orbital eccentricities at epoch J2000.0, from JPL Horizons
EARTH_ECCENTRICITY = 0.0167086   # NASA Earth fact sheet (2024)
MARS_ECCENTRICITY  = 0.0934      # NASA Mars fact sheet (2024)

STANDARD_GRAVITY = 9.80665  # m/s², exact by BIPM/IAU definition; used in Tsiolkovsky Isp conversion
