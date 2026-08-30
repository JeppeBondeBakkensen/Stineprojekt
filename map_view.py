import math
from collections.abc import Iterator
from typing import Any, cast

import pydeck as pdk
import streamlit as st

from rail_data import load_geojson


class CachedDeck(pdk.Deck):
    """A Deck that serializes its immutable map specification only once."""

    _cached_json: str | None = None

    def to_json(self) -> str:
        if self._cached_json is None:
            self._cached_json = super().to_json()
        return self._cached_json


def _coordinate_pairs(coordinates: object) -> Iterator[tuple[float, float]]:
    if not isinstance(coordinates, list):
        return
    if (
        len(coordinates) >= 2
        and isinstance(coordinates[0], int | float)
        and isinstance(coordinates[1], int | float)
    ):
        yield float(coordinates[0]), float(coordinates[1])
        return
    for child in coordinates:
        yield from _coordinate_pairs(child)


def _view_state_for_features(features: list[dict[str, Any]]) -> pdk.ViewState:
    points = [
        point
        for feature in features
        for point in _coordinate_pairs(feature.get("geometry", {}).get("coordinates"))
    ]
    if not points:
        return pdk.ViewState(latitude=56.1, longitude=10.2, zoom=6)

    longitudes, latitudes = zip(*points, strict=True)
    min_longitude, max_longitude = min(longitudes), max(longitudes)
    min_latitude, max_latitude = min(latitudes), max(latitudes)
    longitude = (min_longitude + max_longitude) / 2
    latitude = (min_latitude + max_latitude) / 2

    # Fit the bounds to the approximately 900 × 720 px map with some padding.
    longitude_span = max(max_longitude - min_longitude, 0.002)
    latitude_span = max(max_latitude - min_latitude, 0.002)
    longitude_zoom = math.log2(900 * 360 * 0.78 / (256 * longitude_span))
    latitude_zoom = math.log2(
        720
        * 360
        * max(math.cos(math.radians(latitude)), 0.2)
        * 0.78
        / (256 * latitude_span)
    )
    zoom = max(6, min(12, longitude_zoom, latitude_zoom))
    return pdk.ViewState(latitude=latitude, longitude=longitude, zoom=zoom)


def build_map(
    geojson: dict[str, Any], highlighted_features: list[dict[str, Any]]
) -> pdk.Deck:
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            id="banestraekninger",
            data=geojson,
            pickable=True,
            auto_highlight=True,
            highlight_color=[226, 113, 0, 255],
            stroked=True,
            filled=True,
            get_fill_color=[3, 78, 162, 80],
            get_line_color=[3, 78, 162, 220],
            line_width_min_pixels=4,
        )
    ]

    if highlighted_features:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                id="valgt-tib",
                data={"type": "FeatureCollection", "features": highlighted_features},
                pickable=False,
                stroked=True,
                filled=True,
                get_fill_color=[226, 113, 0, 100],
                get_line_color=[226, 113, 0, 255],
                line_width_min_pixels=7,
            )
        )

    return CachedDeck(
        map_style=cast(str, None),
        initial_view_state=_view_state_for_features(highlighted_features),
        layers=layers,
        map_provider="carto",
        tooltip=cast(
            bool,
            {
                "html": (
                    "<b>{NAVN}</b><br/>"
                    "Hovedstrækning: {HVDSTRK_NAVN}<br/>"
                    "Banenummer: {BANENR}<br/>"
                    "Fra km: {FRA_KM_DISPLAY} - Til km: {TIL_KM_DISPLAY}"
                ),
                "style": {"backgroundColor": "#1f2937", "color": "white"},
            },
        ),
    )


@st.cache_resource(show_spinner=False)
def build_cached_map(highlighted_ids: tuple[str, ...]) -> pdk.Deck:
    """Reuse the Deck object until the highlighted feature set changes."""
    geojson = load_geojson()
    selected_ids = set(highlighted_ids)
    highlighted_features = (
        [
            feature
            for feature in geojson["features"]
            if str(feature.get("properties", {}).get("GLOBALID")) in selected_ids
        ]
        if selected_ids
        else []
    )
    return build_map(geojson, highlighted_features)
