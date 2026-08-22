import json
from pathlib import Path
from typing import Any

import polars as pl
import streamlit as st

from extract import df_geojson_combined

GEOJSON_PATH = Path(__file__).with_name("Danmarkskort_med_strækninger.geojson")

RESULT_COLUMNS = [
    "Kontraktens titel",
    "Leverandørnavn",
    "Geografisk område",
    "Områdebeskrivelse",
    "Referencetype",
    "Referenceværdi",
    "Strækningsbeskrivelse",
]


def _format_km(value: object) -> str:
    if not isinstance(value, int | float):
        return "Ikke angivet"
    return f"{value:.1f}"


@st.cache_data
def load_geojson() -> dict[str, Any]:
    with GEOJSON_PATH.open(encoding="utf-8") as file:
        geojson = json.load(file)

    for feature in geojson["features"]:
        properties = feature["properties"]
        properties["FRA_KM_DISPLAY"] = _format_km(properties.get("FRA_KM"))
        properties["TIL_KM_DISPLAY"] = _format_km(properties.get("TIL_KM"))

    return geojson


def _reference_sort_key(reference: tuple[str, str]) -> tuple[int, bool, int | str]:
    reference_type, value = reference
    return (
        0 if reference_type == "TIB" else 1,
        not value.isdigit(),
        int(value) if value.isdigit() else value,
    )


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
    station: str | None = None,
    section: str | None = None,
    feature_id: str | None = None,
) -> list[dict[str, Any]]:
    features = features_for_reference(geojson, reference)
    features = features_for_station(features, station)
    features = features_for_section(features, section)
    return features_for_id(features, feature_id)


def feature_ids(features: list[dict[str, Any]]) -> list[str]:
    return [
        str(feature["properties"]["GLOBALID"])
        for feature in features
        if feature.get("properties", {}).get("GLOBALID") is not None
    ]


def contracts_for_features(ids: list[str]) -> pl.DataFrame:
    if not ids:
        return pl.DataFrame()

    return (
        df_geojson_combined.filter(pl.col("Id").is_in(ids))
        .select(RESULT_COLUMNS)
        .unique()
        .sort("Kontraktens titel")
    )
