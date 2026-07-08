import math

from constants import G, STANDARD_GRAVITY

_M_PER_KM = 1000.0
_S_PER_HOUR = 3600.0


def require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")


def _validate_inputs(radius_m: float, central_mass_kg: float, gravitational_constant: float) -> None:
    require_positive_finite("radius_m", radius_m)
    require_positive_finite("central_mass_kg", central_mass_kg)
    require_positive_finite("gravitational_constant", gravitational_constant)


def calculate_orbital_velocity(
    radius_m: float,
    central_mass_kg: float,
    gravitational_constant: float = G,
) -> float:
    """Circular orbital velocity in km/s: v = sqrt(GM / r). Raises ValueError for non-physical inputs."""
    _validate_inputs(radius_m, central_mass_kg, gravitational_constant)
    velocity_m_per_s = math.sqrt((gravitational_constant * central_mass_kg) / radius_m)
    return velocity_m_per_s / _M_PER_KM


def calculate_orbital_period(
    radius_m: float,
    central_mass_kg: float,
    gravitational_constant: float = G,
) -> float:
    """Orbital period in hours (Kepler's third law): T = 2π * sqrt(r³ / GM)."""
    _validate_inputs(radius_m, central_mass_kg, gravitational_constant)
    period_s = 2 * math.pi * math.sqrt(radius_m**3 / (gravitational_constant * central_mass_kg))
    return period_s / _S_PER_HOUR


def calculate_escape_velocity(
    radius_m: float,
    central_mass_kg: float,
    gravitational_constant: float = G,
) -> float:
    """Escape velocity in km/s: v_esc = sqrt(2GM / r)."""
    _validate_inputs(radius_m, central_mass_kg, gravitational_constant)
    velocity_m_per_s = math.sqrt((2 * gravitational_constant * central_mass_kg) / radius_m)
    return velocity_m_per_s / _M_PER_KM


def meters_to_km(distance_m: float) -> float:
    return distance_m / _M_PER_KM


def calculate_vis_viva_velocity(
    r_m: float,
    semi_major_axis_m: float,
    central_mass_kg: float,
    gravitational_constant: float = G,
) -> float:
    """Vis-viva speed at radius r_m on an ellipse with semi-major axis a, in km/s: v = sqrt(GM * (2/r - 1/a))."""
    _validate_inputs(r_m, central_mass_kg, gravitational_constant)
    require_positive_finite("semi_major_axis_m", semi_major_axis_m)
    discriminant = 2.0 / r_m - 1.0 / semi_major_axis_m
    if discriminant < 0:
        raise ValueError(
            f"Unphysical configuration: 2/r - 1/a < 0 (r={r_m}, a={semi_major_axis_m}). "
            "Radius must satisfy r <= 2 * semi_major_axis_m."
        )
    return math.sqrt(gravitational_constant * central_mass_kg * discriminant) / _M_PER_KM


def calculate_hohmann_delta_v(
    r1_m: float,
    r2_m: float,
    central_mass_kg: float,
    gravitational_constant: float = G,
) -> tuple[float, float]:
    """(departure, arrival) delta-v in km/s for a Hohmann transfer between circular orbits.

    Positive for ascending transfers (r2 > r1); negative (deceleration burns) for
    descending ones — take abs() for budget math.
    """
    _validate_inputs(r1_m, central_mass_kg, gravitational_constant)
    require_positive_finite("r2_m", r2_m)
    a = (r1_m + r2_m) / 2.0
    dv1 = (
        calculate_vis_viva_velocity(r1_m, a, central_mass_kg, gravitational_constant)
        - calculate_orbital_velocity(r1_m, central_mass_kg, gravitational_constant)
    )
    dv2 = (
        calculate_orbital_velocity(r2_m, central_mass_kg, gravitational_constant)
        - calculate_vis_viva_velocity(r2_m, a, central_mass_kg, gravitational_constant)
    )
    return dv1, dv2


def calculate_mass_ratio(delta_v_ms: float, isp_s: float) -> float:
    """Tsiolkovsky mass ratio m0/mf = exp(delta_v / (Isp * g0)), with delta_v in m/s and Isp in s."""
    if not math.isfinite(delta_v_ms) or delta_v_ms < 0:
        raise ValueError("delta_v_ms must be a finite non-negative number")
    require_positive_finite("isp_s", isp_s)
    return math.exp(delta_v_ms / (isp_s * STANDARD_GRAVITY))
