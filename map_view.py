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
        initial_view_state=pdk.ViewState(latitude=56.1, longitude=10.2, zoom=6),
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
