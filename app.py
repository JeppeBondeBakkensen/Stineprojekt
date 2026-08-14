from __future__ import annotations

import json
from pathlib import Path

import pydeck as pdk
import streamlit as st


ROOT = Path(__file__).parent
GEOJSON_FILE = ROOT / "BI_BTR_RELEASEAFSNIT_OD_1972479174689089199.geojson"


@st.cache_data
def load_railway_geometry() -> dict:
    with GEOJSON_FILE.open(encoding="utf-8") as source:
        return json.load(source)


st.set_page_config(
    page_title="Banedanmark railway map",
    page_icon="🛤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    [data-testid="stAppViewContainer"] { background: #11151b; }
    [data-testid="stMainBlockContainer"] {
        max-width: none;
        padding: 0;
    }
    .stApp, .stApp > div { overflow: hidden; }
    iframe { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

railway_geometry = load_railway_geometry()

railway_layer = pdk.Layer(
    "GeoJsonLayer",
    railway_geometry,
    stroked=True,
    filled=True,
    get_fill_color=[218, 224, 232, 225],
    get_line_color=[235, 239, 244, 255],
    line_width_min_pixels=0.7,
    pickable=False,
)

deck = pdk.Deck(
    layers=[railway_layer],
    initial_view_state=pdk.ViewState(
        latitude=56.15,
        longitude=10.05,
        zoom=5.65,
        min_zoom=5,
        max_zoom=18,
    ),
    map_style="dark",
    tooltip=None,
)

st.pydeck_chart(
    deck,
    height=900,
    use_container_width=True,
)
