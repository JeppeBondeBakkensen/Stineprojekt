from typing import Any, cast

import pydeck as pdk


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

    return pdk.Deck(
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
