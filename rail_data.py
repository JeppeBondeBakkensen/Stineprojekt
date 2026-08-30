import json
from pathlib import Path
from typing import Any

import polars as pl
import streamlit as st

from extract import (
    is_active_banenumber,
    is_s_bane,
    load_combined_data,
    normalize_tibs,
)

GEOJSON_PATH = Path(__file__).with_name("Danmarkskort_med_strækninger.geojson")
WEB_GEOJSON_PATH = Path(__file__).with_name("Danmarkskort_web.geojson")
MAP_SIMPLIFICATION_TOLERANCE = 0.00001
BEREDSKAB_SIZE_COLUMN = (
    "Antal arbejdshold og personer pr. hold, som leverandøren har pligt "
    "til at stille med."
)

RESULT_COLUMNS = [
    "Kontraktens titel",
    "Leverandørnavn",
    "Strækningsbeskrivelse",
    "Geografisk område",
    "Referencetype",
    "Referenceværdi",
    "Responstid",
    "Beskrivelse af beredskabet",
    BEREDSKAB_SIZE_COLUMN,
    "Beskrivelse af boderne",
    "Beskrevet fremgangsmåde omkring fejlretning",
    "Områdebeskrivelse",
    "Vedligeholdelsesforvalter",
    "Vedligeholdelsesforvalter - Initialer",
    "GFS",
    "Kontraktansvarlig (leder)",
    "SAP nummer",
]

RESULT_COLUMN_RENAMES = {BEREDSKAB_SIZE_COLUMN: "Størrelse på beredskabet"}

# Banenumre hvor Excel-arket mangler en beskrivelse, eller hvor beskrivelsen er
# tvetydig. Endestationerne er kontrolleret mod banekortet og GeoJSON-segmenterne.
BANENUMBER_DESCRIPTION_OVERRIDES = {
    "14": "Korsør - Nyborg",
    "17": "Odense Vest - Kavslunde",
    "22": "Nykøbing Falster - Rødby Færge",
    "27": "Snoghøj - Taulov",
    "30": "Nykøbing Falster - Gedser",
    "32": "Langå - Struer",
    "36": "Aarhus H - Grenaa",
    "43": "Ringe - Korinth",
    "44": "Tommerup - Assens",
    "47": "Bramming - Grindsted",
    "49": "Tinglev - Tønder",
    "54": "Haderslev - Vojens",
    "58": "Dalmose - Skælskør",
    "59": "Slagelse - Næstved",
    "77": "Rødekro - Aabenraa",
    "82": "Svanemøllen - Hillerød",
    "84": "Svanemøllen - Farum",
    "96": "Tønder - Tønder Grænse",
}


def _format_km(value: object) -> str:
    if not isinstance(value, int | float):
        return "Ikke angivet"
    return f"{value:.1f}"


def _simplify_ring(
    coordinates: list[list[float]], tolerance: float
) -> list[list[float]]:
    """Forenkl en lukket polygonring med Ramer-Douglas-Peucker."""
    if len(coordinates) <= 4:
        return coordinates

    closed = coordinates[0] == coordinates[-1]
    points = coordinates[:-1] if closed else coordinates

    def simplify(points_to_simplify: list[list[float]]) -> list[list[float]]:
        if len(points_to_simplify) <= 2:
            return points_to_simplify

        start_x, start_y = points_to_simplify[0][:2]
        end_x, end_y = points_to_simplify[-1][:2]
        delta_x = end_x - start_x
        delta_y = end_y - start_y
        length_squared = delta_x * delta_x + delta_y * delta_y
        max_distance_squared = -1.0
        split_index = 0

        for index, point in enumerate(points_to_simplify[1:-1], start=1):
            point_x, point_y = point[:2]
            if length_squared == 0:
                projected_x, projected_y = start_x, start_y
            else:
                projection = (
                    (point_x - start_x) * delta_x
                    + (point_y - start_y) * delta_y
                ) / length_squared
                projection = max(0.0, min(1.0, projection))
                projected_x = start_x + projection * delta_x
                projected_y = start_y + projection * delta_y
            distance_squared = (point_x - projected_x) ** 2 + (
                point_y - projected_y
            ) ** 2
            if distance_squared > max_distance_squared:
                max_distance_squared = distance_squared
                split_index = index

        if max_distance_squared > tolerance * tolerance:
            left = simplify(points_to_simplify[: split_index + 1])
            right = simplify(points_to_simplify[split_index:])
            return left[:-1] + right
        return [points_to_simplify[0], points_to_simplify[-1]]

    simplified = simplify(points)
    if closed:
        simplified.append(simplified[0])
    return simplified if len(simplified) >= 4 else coordinates


def _simplify_geometry(geometry: dict[str, Any]) -> None:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        geometry["coordinates"] = [
            _simplify_ring(ring, MAP_SIMPLIFICATION_TOLERANCE)
            for ring in coordinates
        ]
    elif geometry.get("type") == "MultiPolygon":
        geometry["coordinates"] = [
            [
                _simplify_ring(ring, MAP_SIMPLIFICATION_TOLERANCE)
                for ring in polygon
            ]
            for polygon in coordinates
        ]


def prepare_geojson() -> dict[str, Any]:
    """Create the filtered and simplified map payload used by the web app."""
    with GEOJSON_PATH.open(encoding="utf-8") as file:
        geojson = json.load(file)

    active_features = []
    for feature in geojson["features"]:
        properties = feature["properties"]
        if not is_active_banenumber(properties.get("BANENR")) or is_s_bane(
            properties.get("TIB"), properties.get("BANENR")
        ):
            continue
        _simplify_geometry(feature.get("geometry", {}))
        properties["TIB"] = normalize_tibs(properties.get("TIB"))
        properties["FRA_KM_DISPLAY"] = _format_km(properties.get("FRA_KM"))
        properties["TIL_KM_DISPLAY"] = _format_km(properties.get("TIL_KM"))
        active_features.append(feature)

    geojson["features"] = active_features
    return geojson


@st.cache_resource(show_spinner="Indlæser kortdata...")
def load_geojson() -> dict[str, Any]:
    # Avoid filtering and simplifying 23 MB of source geometry at startup.
    # prepare_geojson.py rebuilds this asset when the source map changes.
    if WEB_GEOJSON_PATH.exists():
        with WEB_GEOJSON_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    return prepare_geojson()


def _natural_reference_sort_key(value: str) -> tuple[bool, int, str]:
    number = ""
    for character in value:
        if not character.isdigit():
            break
        number += character
    if number:
        return False, int(number), value[len(number) :].casefold()
    return True, 0, value.casefold()


def _reference_sort_key(
    reference: tuple[str, str],
) -> tuple[int, tuple[bool, int, str]]:
    reference_type, value = reference
    return 0 if reference_type == "TIB" else 1, _natural_reference_sort_key(value)


def get_references(geojson: dict[str, Any]) -> list[tuple[str, str]]:
    references: set[tuple[str, str]] = set()

    for feature in geojson["features"]:
        properties = feature.get("properties", {})
        banenummer = str(properties.get("BANENR") or "").strip()
        if banenummer:
            references.add(("BANENR", banenummer))

        for tib in str(properties.get("TIB") or "").split(","):
            if tib := tib.strip():
                references.add(("TIB", tib))

    return sorted(references, key=_reference_sort_key)


def get_tibs(features: list[dict[str, Any]]) -> list[str]:
    tibs = {
        tib.strip()
        for feature in features
        for tib in str(feature.get("properties", {}).get("TIB") or "").split(",")
        if tib.strip()
    }
    return sorted(tibs, key=_natural_reference_sort_key)


def tib_label(tib: str) -> str:
    if len(tib) == 4 and tib.startswith("10") and tib.isdigit():
        return f"{int(tib[2:])} (datakode {tib})"
    return tib


def get_banenumbers(features: list[dict[str, Any]]) -> list[str]:
    banenumbers = {
        value
        for feature in features
        if (value := str(feature.get("properties", {}).get("BANENR") or "").strip())
    }
    return sorted(banenumbers, key=_natural_reference_sort_key)


@st.cache_data(show_spinner=False)
def banenumber_description(banenumber: str) -> str | None:
    if description := BANENUMBER_DESCRIPTION_OVERRIDES.get(banenumber):
        return description

    descriptions = (
        load_combined_data().filter(
            (pl.col("Referencetype") == "BANENR")
            & (pl.col("Referenceværdi") == banenumber)
        )
        .select("Strækningsbeskrivelse")
        .drop_nulls()
        .unique()
        .to_series()
        .to_list()
    )
    descriptions = sorted(
        {
            str(description).replace("(", "").replace(")", "").strip()
            for description in descriptions
            if str(description).strip()
        }
    )
    if not descriptions:
        return None
    return descriptions[0]


def reference_label(reference: tuple[str, str]) -> str:
    reference_type, value = reference
    label = "TIB" if reference_type == "TIB" else "Banenummer"
    return f"{label} · {value}"


def features_for_reference(
    geojson: dict[str, Any], reference: tuple[str, str] | None
) -> list[dict[str, Any]]:
    if reference is None:
        return geojson["features"]

    reference_type, reference_value = reference
    return [
        feature
        for feature in geojson["features"]
        if reference_value in _feature_references(feature, reference_type)
    ]


def features_for_tib(
    features: list[dict[str, Any]], tib: str | None
) -> list[dict[str, Any]]:
    if tib is None:
        return features
    return [
        feature for feature in features if tib in _feature_references(feature, "TIB")
    ]


def features_for_banenumber(
    features: list[dict[str, Any]], banenumber: str | None
) -> list[dict[str, Any]]:
    if banenumber is None:
        return features
    return [
        feature
        for feature in features
        if banenumber in _feature_references(feature, "BANENR")
    ]


def _feature_references(feature: dict[str, Any], reference_type: str) -> set[str]:
    properties = feature.get("properties", {})
    if reference_type == "BANENR":
        value = str(properties.get("BANENR") or "").strip()
        return {value} if value else set()
    return {
        value.strip()
        for value in str(properties.get("TIB") or "").split(",")
        if value.strip()
    }


def get_stations(features: list[dict[str, Any]]) -> list[str]:
    stations = set()
    for feature in features:
        name = str(feature.get("properties", {}).get("NAVN") or "").strip()
        if name:
            stations.update(part.strip() for part in name.split(" - "))
    return sorted(stations)


def features_for_station(
    features: list[dict[str, Any]], station: str | None
) -> list[dict[str, Any]]:
    if station is None:
        return features
    return [
        feature
        for feature in features
        if station
        in {
            part.strip()
            for part in str(feature.get("properties", {}).get("NAVN") or "").split(
                " - "
            )
        }
    ]


def get_sections(features: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            name
            for feature in features
            if " - "
            in (name := str(feature.get("properties", {}).get("NAVN") or "").strip())
        }
    )


def features_for_section(
    features: list[dict[str, Any]], section: str | None
) -> list[dict[str, Any]]:
    if section is None:
        return features
    return [
        feature
        for feature in features
        if str(feature.get("properties", {}).get("NAVN") or "").strip() == section
    ]


def get_kilometer_options(
    features: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    options = []
    for feature in features:
        properties = feature.get("properties", {})
        feature_id = properties.get("GLOBALID")
        if feature_id is None:
            continue
        start = _format_km(properties.get("FRA_KM")).replace(".", ",")
        end = _format_km(properties.get("TIL_KM")).replace(".", ",")
        name = str(properties.get("NAVN") or "Ukendt strækning")
        options.append((str(feature_id), f"{name} · Km {start} - {end}"))
    return sorted(set(options), key=lambda option: option[1])


def features_for_id(
    features: list[dict[str, Any]], feature_id: str | None
) -> list[dict[str, Any]]:
    if feature_id is None:
        return features
    return [
        feature
        for feature in features
        if str(feature.get("properties", {}).get("GLOBALID")) == feature_id
    ]


def filter_features(
    geojson: dict[str, Any],
    reference: tuple[str, str] | None = None,
    tib: str | None = None,
    banenumber: str | None = None,
    station: str | None = None,
    section: str | None = None,
    feature_id: str | None = None,
) -> list[dict[str, Any]]:
    features = features_for_reference(geojson, reference)
    features = features_for_tib(features, tib)
    features = features_for_banenumber(features, banenumber)
    features = features_for_station(features, station)
    features = features_for_section(features, section)
    return features_for_id(features, feature_id)


@st.cache_resource(show_spinner=False)
def _feature_filter_index() -> dict[str, dict[str, frozenset[int]]]:
    """Index feature positions once so filter reruns avoid full-list scans."""
    mutable_index: dict[str, dict[str, set[int]]] = {
        "tib": {},
        "banenumber": {},
        "station": {},
        "section": {},
        "feature_id": {},
    }

    for position, feature in enumerate(load_geojson()["features"]):
        properties = feature.get("properties", {})
        values = {
            "tib": {
                value.strip()
                for value in str(properties.get("TIB") or "").split(",")
                if value.strip()
            },
            "banenumber": {str(properties.get("BANENR") or "").strip()},
            "station": {
                part.strip()
                for part in str(properties.get("NAVN") or "").split(" - ")
                if part.strip()
            },
            "section": {str(properties.get("NAVN") or "").strip()},
            "feature_id": {str(properties.get("GLOBALID") or "").strip()},
        }
        for filter_name, filter_values in values.items():
            for value in filter_values:
                if value:
                    mutable_index[filter_name].setdefault(value, set()).add(position)

    return {
        filter_name: {
            value: frozenset(positions) for value, positions in values.items()
        }
        for filter_name, values in mutable_index.items()
    }


@st.cache_resource(show_spinner=False)
def cached_filter_features(
    tib: str | None = None,
    banenumber: str | None = None,
    station: str | None = None,
    section: str | None = None,
    feature_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return indexed filter results cached by small, stable selection values."""
    features = load_geojson()["features"]
    positions = set(range(len(features)))
    index = _feature_filter_index()
    for filter_name, value in (
        ("tib", tib),
        ("banenumber", banenumber),
        ("station", station),
        ("section", section),
        ("feature_id", feature_id),
    ):
        if value is not None:
            positions.intersection_update(index[filter_name].get(value, ()))
    return [
        feature
        for position, feature in enumerate(features)
        if position in positions
    ]


def feature_ids(features: list[dict[str, Any]]) -> list[str]:
    return [
        str(feature["properties"]["GLOBALID"])
        for feature in features
        if feature.get("properties", {}).get("GLOBALID") is not None
    ]


@st.cache_data(show_spinner=False)
def contracts_for_reference(reference_type: str, reference_value: str) -> pl.DataFrame:
    return load_combined_data().filter(
        (pl.col("Referencetype") == reference_type)
        & (pl.col("Referenceværdi") == reference_value)
    )


@st.cache_data(show_spinner=False)
def contracts_for_features(
    ids: tuple[str, ...],
    reference_type: str | None = None,
    reference_value: str | None = None,
) -> pl.DataFrame:
    if not ids:
        return pl.DataFrame()

    if reference_type and reference_value:
        contracts = contracts_for_reference(reference_type, reference_value)
    else:
        contracts = load_combined_data()
    contracts = contracts.filter(pl.col("Id").is_in(ids))

    return (
        contracts
        .select(RESULT_COLUMNS)
        .rename(RESULT_COLUMN_RENAMES)
        .unique()
        .sort("Kontraktens titel")
    )
