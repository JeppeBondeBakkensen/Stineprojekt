import streamlit as st

from map_view import build_map
from rail_data import (
    contracts_for_features,
    feature_ids,
    filter_features,
    get_kilometer_options,
    get_references,
    get_sections,
    get_stations,
    load_geojson,
    reference_label,
)

FILTER_KEYS = ["reference", "station", "section", "kilometer"]


def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


st.set_page_config(page_title="Danmarkskort", page_icon="🗺️", layout="wide")
st.title("Danmarkskort med strækninger")

geojson = load_geojson()
filter_column, map_column = st.columns([1, 2], gap="large")

current_reference = st.session_state.get("reference")
current_station = st.session_state.get("station")
current_section = st.session_state.get("section")
current_kilometer = st.session_state.get("kilometer")
current_feature_id = current_kilometer[0] if current_kilometer else None

reference_options = get_references(
    {
        "features": filter_features(
            geojson,
            station=current_station,
            section=current_section,
            feature_id=current_feature_id,
        )
    }
)
station_options = get_stations(
    filter_features(
        geojson,
        reference=current_reference,
        section=current_section,
        feature_id=current_feature_id,
    )
)
section_options = get_sections(
    filter_features(
        geojson,
        reference=current_reference,
        station=current_station,
        feature_id=current_feature_id,
    )
)
kilometer_options = get_kilometer_options(
    filter_features(
        geojson,
        reference=current_reference,
        station=current_station,
        section=current_section,
    )
)

with filter_column:
    st.subheader("Filtre")
    selected_reference = st.selectbox(
        "TIB eller banenummer",
        reference_options,
        format_func=reference_label,
        index=None,
        placeholder="Søg eller vælg TIB eller banenummer",
        key="reference",
    )

    selected_station = st.selectbox(
        "Station",
        station_options,
        index=None,
        placeholder="Søg eller vælg station",
        key="station",
    )

    selected_section = st.selectbox(
        "Strækning",
        section_options,
        index=None,
        placeholder="Søg eller vælg strækning",
        key="section",
    )

    selected_kilometer = st.selectbox(
        "Kilometrering",
        kilometer_options,
        format_func=lambda option: option[1],
        index=None,
        placeholder="Søg eller vælg kilometrering",
        key="kilometer",
    )
    st.button("Nulstil filtre", on_click=reset_filters, width="stretch")

selected_feature_id = selected_kilometer[0] if selected_kilometer else None
filtered_features = filter_features(
    geojson,
    reference=selected_reference,
    station=selected_station,
    section=selected_section,
    feature_id=selected_feature_id,
)
has_active_filter = any(
    value is not None
    for value in (
        selected_reference,
        selected_station,
        selected_section,
        selected_kilometer,
    )
)
highlighted_features = filtered_features if has_active_filter else []

with map_column:
    map_event = st.pydeck_chart(
        build_map(geojson, highlighted_features),
        key="danmarkskort",
        on_select="rerun",
        selection_mode="single-object",
        height=700,
    )

selected_objects = map_event.selection["objects"].get("banestraekninger", [])
selected_ids = feature_ids(filtered_features) if has_active_filter else []
result_title = "Valgte Strøm-data"

if not has_active_filter and selected_objects:
    properties = selected_objects[0].get("properties", selected_objects[0])
    selected_id = properties.get("GLOBALID")
    selected_ids = [str(selected_id)] if selected_id is not None else []
    result_title = properties.get("NAVN", "Valgt strækning")

with filter_column:
    st.subheader(result_title)
    if not selected_ids:
        st.info("Vælg et filter eller klik på en strækning på kortet.")
    else:
        contracts = contracts_for_features(selected_ids)
        if contracts.height:
            st.dataframe(contracts, hide_index=True, width="stretch")
        else:
            st.info("Der blev ikke fundet Strøm-data for dette valg.")
