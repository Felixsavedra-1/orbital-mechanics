import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO

from calculations import (
    calculate_escape_velocity,
    calculate_hohmann_delta_v,
    calculate_orbital_period,
    calculate_orbital_velocity,
    meters_to_km,
)
from constants import DATA_VALIDATION_DATE, EARTH_MASS, EARTH_RADIUS
from data import (
    CONCEPT_STATIONS,
    EARTH_ORBITS,
    ISS_TO_MOON_DISTANCE,
    PLANETS,
    TRANSFER_ORBITS,
    OrbitalBody,
)

LABEL_WIDTH = 36
VALUE_WIDTH = 14

REPORT_TITLE = "PLANET ORBITAL SIMULATION & SPACE EXPLORATION GUIDE"
REPORT_SCHEMA_VERSION = "1.2.0"
SECTION_ORDER = ["planets", "earth", "concepts", "mars-base", "transfers"]
# "mission" runs a live Lambert/porkchop search (needs numpy/scipy), so it is an
# explicit opt-in section, deliberately excluded from the default "all" aggregation to
# keep that path pure-stdlib and its record count stable.
VALID_SECTIONS = ["all", *SECTION_ORDER, "mission"]
VALID_OUTPUT_FORMATS = ["text", "json", "csv"]
SECTION_TITLES = {
    "planets": "PLANET ORBITAL VELOCITY & PERIOD DATA",
    "earth": "EARTH ORBITAL SYSTEMS",
    "concepts": "CONCEPT STATIONS",
    "mars-base": "MARS BASE CONCEPT",
    "transfers": "HOHMANN TRANSFER ORBITS",
    "mission": "EARTH-MARS TRANSFER OPPORTUNITY (LAMBERT/PORKCHOP)",
}


@dataclass
class MetricRecord:
    section: str
    label: str
    value: str
    value_num: float | None = None
    unit: str = ""
    note: str = ""


def _metric(section: str, label: str, value_num: float, unit: str,
            decimals: int, note: str = "") -> MetricRecord:
    """MetricRecord for a numeric value, formatted and rounded to `decimals` places."""
    return MetricRecord(section, label, f"{value_num:.{decimals}f}",
                        round(value_num, decimals), unit, note)


_YEARS_THRESHOLD_DAYS = 365.25 * 2


def _format_period(period_hours: float) -> tuple[str, str]:
    """Scale a period to a human-readable (value_str, unit_str) pair."""
    days = period_hours / 24
    if days >= _YEARS_THRESHOLD_DAYS:
        return f"{days / 365.25:.1f}", "Earth years"
    if days >= 2:
        return f"{days:.1f}", "Earth days"
    if period_hours >= 1:
        return f"{period_hours:.1f}", "hours"
    return f"{period_hours * 60:.0f}", "minutes"


def _body_orbit_records(section: str, bodies: list[OrbitalBody]) -> list[MetricRecord]:
    records = []
    for body in bodies:
        velocity_km = calculate_orbital_velocity(body.orbital_radius_m, body.central_mass_kg)
        records.append(_metric(section, f"{body.name} orbital velocity", velocity_km,
                               "km/s", 2, body.body_type))

        period_hours = calculate_orbital_period(body.orbital_radius_m, body.central_mass_kg)
        period_value, period_unit = _format_period(period_hours)
        records.append(MetricRecord(
            section=section,
            label=f"{body.name} orbital period",
            value=period_value,
            value_num=round(period_hours, 4),  # always hours for machine use
            unit=period_unit,
            note=body.body_type,
        ))
    return records


def _planet_velocity_records() -> list[MetricRecord]:
    return _body_orbit_records("planets", PLANETS)


def _earth_orbit_records() -> list[MetricRecord]:
    records = _body_orbit_records("earth", EARTH_ORBITS)
    iss_to_moon_km = meters_to_km(ISS_TO_MOON_DISTANCE)
    records.append(_metric("earth", "ISS distance from Moon", iss_to_moon_km, "km", 0))
    esc_km = calculate_escape_velocity(EARTH_RADIUS, EARTH_MASS)
    records.append(_metric("earth", "Earth escape velocity", esc_km, "km/s", 2, "From surface"))
    return records


def _concept_station_records() -> list[MetricRecord]:
    records = []
    for station in CONCEPT_STATIONS:
        midpoint_km = meters_to_km(station.distance_m)
        records.append(_metric("concepts", f"Concept station {station.name}",
                               midpoint_km, "km", 0, station.note))
    return records


def _mars_base_records() -> list[MetricRecord]:
    """Conceptual planning fields — not engineering-specified."""
    note = "Conceptual — not engineering-specified"
    return [
        MetricRecord("mars-base", "Location", "TBD", note=note),
        MetricRecord("mars-base", "Primary habitation", "TBD", note="Target crew habitat sizing"),
        MetricRecord("mars-base", "Core systems", "Habitat, life support, power, landing pad", note=note),
        MetricRecord("mars-base", "Life support", "Radiation shielding, water extraction, O2 generation", note=note),
        MetricRecord("mars-base", "Power profile", "Nuclear primary, solar secondary, battery reserve", note=note),
        MetricRecord("mars-base", "Safety controls", "Pressure auto-seal, dust airlocks, evacuation protocols", note=note),
        MetricRecord("mars-base", "Crew capacity", "TBD", note=note),
        MetricRecord("mars-base", "Mission duration", "TBD", note=note),
    ]


def _transfer_records() -> list[MetricRecord]:
    records = []
    for transfer in TRANSFER_ORBITS:
        dv1, dv2 = calculate_hohmann_delta_v(
            transfer.r1_m, transfer.r2_m, transfer.central_mass_kg
        )
        total = dv1 + dv2
        records.append(_metric("transfers", f"{transfer.name} departure Δv", dv1,
                               "km/s", 2, transfer.note))
        records.append(_metric("transfers", f"{transfer.name} arrival Δv", dv2,
                               "km/s", 2, transfer.note))
        records.append(_metric("transfers", f"{transfer.name} total Δv", total,
                               "km/s", 2, transfer.note))
    return records


# Earth->Mars launch-window search grid for the "mission" section. The span is fixed
# (covers the 2026 and 2028 opportunities) so the report is deterministic; 10-day
# departure resolution over ~3.2 years, flight times 100-360 days.
_MISSION_SEARCH_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
_MISSION_DEP_STEP_DAYS = 10.0
_MISSION_DEP_COUNT = 117
_MISSION_TOF_DAYS = [100.0 + 10.0 * k for k in range(27)]


def _mission_records() -> list[MetricRecord]:
    """Solve the optimal Earth->Mars transfer over the fixed launch-window grid.

    Uses the high-fidelity astrodynamics layer (approximate JPL ephemerides + a Lambert
    solver), imported lazily so the default report path stays pure stdlib. This is the
    real-ephemeris counterpart to the idealized Hohmann figure in the 'transfers' section.
    """
    from astrodynamics.ephemeris import datetime_to_jd, jd_to_datetime
    from astrodynamics.mission_design import mission_delta_v
    from astrodynamics.porkchop import best_transfer

    start_jd = datetime_to_jd(_MISSION_SEARCH_START)
    departure_jds = [start_jd + _MISSION_DEP_STEP_DAYS * k for k in range(_MISSION_DEP_COUNT)]
    best = best_transfer("Earth", "Mars", departure_jds, _MISSION_TOF_DAYS)
    budget = mission_delta_v(best)

    dep_date = jd_to_datetime(best.departure_jd).date().isoformat()
    arr_date = jd_to_datetime(best.arrival_jd).date().isoformat()
    method = "Lambert + approx. JPL ephemeris"
    impulsive = "Impulsive; excludes finite-burn/gravity losses and EDL"
    return [
        MetricRecord("mission", "Optimal departure (Earth)", dep_date,
                     value_num=round(best.departure_jd, 4), unit="JD", note=method),
        MetricRecord("mission", "Optimal arrival (Mars)", arr_date,
                     value_num=round(best.arrival_jd, 4), unit="JD", note=method),
        MetricRecord("mission", "Time of flight", f"{best.tof_days:.0f}",
                     value_num=round(best.tof_days, 1), unit="days"),
        MetricRecord("mission", "Departure C3", f"{best.c3_km2_s2:.2f}",
                     value_num=round(best.c3_km2_s2, 2), unit="km^2/s^2", note="Launch energy"),
        MetricRecord("mission", "Departure v-infinity", f"{best.v_inf_depart_km_s:.2f}",
                     value_num=round(best.v_inf_depart_km_s, 3), unit="km/s"),
        MetricRecord("mission", "Arrival v-infinity", f"{best.v_inf_arrive_km_s:.2f}",
                     value_num=round(best.v_inf_arrive_km_s, 3), unit="km/s"),
        MetricRecord("mission", "Total v-infinity", f"{best.total_v_inf_km_s:.2f}",
                     value_num=round(best.total_v_inf_km_s, 3), unit="km/s",
                     note="First-order delta-v proxy (departure + arrival)"),
        MetricRecord("mission", "Injection delta-v", f"{budget.injection_m_s / 1000.0:.2f}",
                     value_num=round(budget.injection_m_s / 1000.0, 3), unit="km/s",
                     note="200 km Earth parking orbit -> departure hyperbola"),
        MetricRecord("mission", "Capture delta-v", f"{budget.capture_m_s / 1000.0:.2f}",
                     value_num=round(budget.capture_m_s / 1000.0, 3), unit="km/s",
                     note="Arrival hyperbola -> 400 km circular Mars orbit"),
        MetricRecord("mission", "Total mission delta-v", f"{budget.total_m_s / 1000.0:.2f}",
                     value_num=round(budget.total_m_s / 1000.0, 3), unit="km/s",
                     note=impulsive),
    ]


def _validate_section(section: str) -> None:
    if section not in VALID_SECTIONS:
        valid_sections = ", ".join(VALID_SECTIONS)
        raise ValueError(f"Unsupported section '{section}'. Valid options: {valid_sections}")


def _validate_output_format(output_format: str) -> None:
    if output_format not in VALID_OUTPUT_FORMATS:
        valid_formats = ", ".join(VALID_OUTPUT_FORMATS)
        raise ValueError(f"Unsupported output format '{output_format}'. Valid options: {valid_formats}")


def collect_records(section: str) -> list[MetricRecord]:
    """Return ordered MetricRecords for the given section.

    Records are ordered by section (matching SECTION_ORDER); renderers that
    group by section rely on this ordering.

    Raises:
        ValueError: If section is not in VALID_SECTIONS.
    """
    _validate_section(section)
    by_section = {
        "planets": _planet_velocity_records,
        "earth": _earth_orbit_records,
        "concepts": _concept_station_records,
        "mars-base": _mars_base_records,
        "transfers": _transfer_records,
        "mission": _mission_records,
    }
    if section == "all":
        records = []
        for section_name in SECTION_ORDER:
            records.extend(by_section[section_name]())
        return records
    return by_section[section]()


def _format_text_metric(record: MetricRecord) -> str:
    label_text = f"{record.label}:".ljust(LABEL_WIDTH)
    value_text = f"{record.value:>{VALUE_WIDTH}}"
    unit_text = f" {record.unit}" if record.unit else ""
    note_text = f" ({record.note})" if record.note else ""
    return f"{label_text}{value_text}{unit_text}{note_text}"


def render_text(section: str) -> str:
    records = collect_records(section)
    lines = [f"--{REPORT_TITLE}--", "Project Summary: orbital data and conceptual mission planning"]
    active_sections = SECTION_ORDER if section == "all" else [section]

    by_section: dict[str, list[MetricRecord]] = {s: [] for s in active_sections}
    for r in records:
        by_section[r.section].append(r)

    for section_name in active_sections:
        lines.append(f"--{SECTION_TITLES[section_name]}--")
        lines.extend(_format_text_metric(r) for r in by_section[section_name])

    return "\n".join(lines)


def render_json(section: str) -> str:
    """Render a JSON payload including schema version, provenance, assumptions, and records."""
    records = [asdict(record) for record in collect_records(section)]
    payload = {
        "report_title": REPORT_TITLE,
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "section": section,
        "data_sources": {
            "gravitational_constant": "CODATA 2018",
            "astronomical_unit": "IAU 2012 Resolution B2",
            "solar_mass": "IAU 2015 Resolution B3",
            "planetary_semi_major_axes": "JPL Horizons, epoch J2000.0",
            "earth_moon_iss_data": "NASA fact sheets (2024)",
            "data_validation_date": DATA_VALIDATION_DATE,
        },
        "assumptions": [
            "Circular orbit approximation: v = sqrt(GM/r)",
            "Orbital period from Kepler's third law: T = 2*pi*sqrt(r^3/GM)",
            "Moon distance is semi-major axis (actual range 356,500-406,700 km)",
            "ISS altitude is approximate mean as of 2024-Q1",
            "Perturbations and eccentricity ignored except where noted",
        ],
        "records": records,
    }
    return json.dumps(payload, indent=2)


def render_csv(section: str) -> str:
    records = collect_records(section)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "label", "value", "value_num", "unit", "note"])
    for record in records:
        writer.writerow([
            record.section,
            record.label,
            record.value,
            "" if record.value_num is None else record.value_num,
            record.unit,
            record.note,
        ])
    return output.getvalue().rstrip("\n")


def render_report(section: str, output_format: str) -> str:
    """Validate output_format and dispatch to the appropriate renderer.
    Section validation is enforced by collect_records.

    Raises:
        ValueError: If output_format is invalid, or if section is invalid
                    (raised by collect_records via the renderer).
    """
    _validate_output_format(output_format)

    renderers = {
        "text": render_text,
        "json": render_json,
        "csv": render_csv,
    }
    try:
        return renderers[output_format](section)
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Renderer '{output_format}' failed for section '{section}': {e}"
        ) from e
