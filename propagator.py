import math

from calculations import require_positive_finite
from constants import G

_State = tuple[float, float, float, float]  # (x_m, y_m, vx_ms, vy_ms)


def _derivatives(state: _State, GM: float) -> _State:
    x, y, vx, vy = state
    r_sq = x * x + y * y
    if r_sq == 0.0:
        raise ValueError("Collision: position vector has zero magnitude during integration.")
    r_cubed = r_sq * math.sqrt(r_sq)
    factor = -GM / r_cubed
    return (vx, vy, factor * x, factor * y)


def _rk4_step(state: _State, GM: float, dt: float) -> _State:
    x, y, vx, vy = state
    k1 = _derivatives(state, GM)
    s2: _State = (x + 0.5*dt*k1[0], y + 0.5*dt*k1[1], vx + 0.5*dt*k1[2], vy + 0.5*dt*k1[3])
    k2 = _derivatives(s2, GM)
    s3: _State = (x + 0.5*dt*k2[0], y + 0.5*dt*k2[1], vx + 0.5*dt*k2[2], vy + 0.5*dt*k2[3])
    k3 = _derivatives(s3, GM)
    s4: _State = (x + dt*k3[0], y + dt*k3[1], vx + dt*k3[2], vy + dt*k3[3])
    k4 = _derivatives(s4, GM)
    c = dt / 6.0
    return (
        x  + c * (k1[0] + 2.0*k2[0] + 2.0*k3[0] + k4[0]),
        y  + c * (k1[1] + 2.0*k2[1] + 2.0*k3[1] + k4[1]),
        vx + c * (k1[2] + 2.0*k2[2] + 2.0*k3[2] + k4[2]),
        vy + c * (k1[3] + 2.0*k2[3] + 2.0*k3[3] + k4[3]),
    )


def propagate_two_body(
    x0_m: float,
    y0_m: float,
    vx0_ms: float,
    vy0_ms: float,
    central_mass_kg: float,
    dt_s: float,
    n_steps: int,
    gravitational_constant: float = G,
) -> list[tuple[float, float, float, float, float]]:
    """Propagate a two-body orbit using 4th-order Runge-Kutta integration.

    Central body is fixed at the origin. All quantities in SI units.
    Returns n_steps+1 tuples of (t_s, x_m, y_m, vx_ms, vy_ms), starting at t=0.

    Raises:
        ValueError: If central_mass_kg <= 0, dt_s <= 0, n_steps < 1,
                    gravitational_constant <= 0, or r=0 encountered during integration.
    """
    require_positive_finite("central_mass_kg", central_mass_kg)
    require_positive_finite("dt_s", dt_s)
    if n_steps < 1:
        raise ValueError("n_steps must be >= 1")
    require_positive_finite("gravitational_constant", gravitational_constant)

    GM = gravitational_constant * central_mass_kg
    state: _State = (x0_m, y0_m, vx0_ms, vy0_ms)
    results: list[tuple[float, float, float, float, float]] = [(0.0, x0_m, y0_m, vx0_ms, vy0_ms)]
    for step in range(n_steps):
        state = _rk4_step(state, GM, dt_s)
        results.append(((step + 1) * dt_s, state[0], state[1], state[2], state[3]))
    return results
