import streamlit as st

from map_view import build_cached_map
from rail_data import (
    banenumber_description,
    cached_filter_features,
    contracts_for_features,
    contracts_for_sheet,
    feature_ids,
    get_banenumbers,
    get_kilometer_options,
    get_sections,
    get_stations,
    get_tibs,
    tib_label,
)

FILTER_KEYS = ["tib", "banenumber", "station", "section", "kilometer"]


def reset_map_selection() -> None:
    st.session_state.pop("pending_banenumber", None)
    st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1


def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state[key] = None
    reset_map_selection()


def reset_dependent_filters(*keys: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)
    reset_map_selection()


def feature_title(properties: dict) -> str:
    banenumber = str(properties.get("BANENR") or "").strip()
    description = banenumber_description(banenumber) if banenumber else None
    if banenumber and description:
        return f"Banenummer {banenumber} · {description}"
    if banenumber:
        return f"Banenummer {banenumber} · {properties.get('NAVN', 'Valgt strækning')}"
    return str(properties.get("NAVN") or "Valgt strækning")


st.set_page_config(
    page_title="Krav til leverandør af oursourcet fejlretning og vedligehold",
    page_icon="🗺️",
    layout="wide",
)
st.title("Krav til leverandør af oursourcet fejlretning og vedligehold")

pending_banenumber = st.session_state.pop("pending_banenumber", None)
if pending_banenumber:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state["banenumber"] = pending_banenumber

filter_column, map_column = st.columns([1, 2], gap="large")

current_tib = st.session_state.get("tib")
current_banenumber = st.session_state.get("banenumber")
current_station = st.session_state.get("station")
current_section = st.session_state.get("section")
current_kilometer = st.session_state.get("kilometer")
current_feature_id = current_kilometer[0] if current_kilometer else None

tib_options = get_tibs(
    cached_filter_features(
        banenumber=current_banenumber,
        station=current_station,
        section=current_section,
        feature_id=current_feature_id,
    )
)
banenumber_options = get_banenumbers(
    cached_filter_features(
        tib=current_tib,
        station=current_station,
        section=current_section,
        feature_id=current_feature_id,
    )
)
station_options = get_stations(
    cached_filter_features(
        tib=current_tib,
        banenumber=current_banenumber,
        section=current_section,
        feature_id=current_feature_id,
    )
)
section_options = get_sections(
    cached_filter_features(
        tib=current_tib,
        banenumber=current_banenumber,
        station=current_station,
        feature_id=current_feature_id,
    )
)
kilometer_options = get_kilometer_options(
    cached_filter_features(
        tib=current_tib,
        banenumber=current_banenumber,
        station=current_station,
        section=current_section,
    )
)
with filter_column:
    st.subheader("Filtre")
    selected_tib = st.selectbox(
        "TIB",
        tib_options,
        format_func=tib_label,
        index=None,
        placeholder="Søg eller vælg TIB",
        key="tib",
        on_change=reset_dependent_filters,
        args=(("banenumber", "station", "section", "kilometer")),
    )

    selected_banenumber = st.selectbox(
        "Banenummer",
        banenumber_options,
        index=None,
        placeholder="Søg eller vælg banenummer",
        key="banenumber",
        on_change=reset_dependent_filters,
        args=(("station", "section", "kilometer")),
    )

    selected_section = st.selectbox(
        "Strækning",
        section_options,
        index=None,
        placeholder="Søg eller vælg strækning",
        key="section",
        on_change=reset_dependent_filters,
        args=(("station", "kilometer")),
    )

    selected_station = st.selectbox(
        "Station",
        station_options,
        index=None,
        placeholder="Søg eller vælg station",
        key="station",
        on_change=reset_dependent_filters,
        args=(("kilometer",)),
    )

    selected_kilometer = st.selectbox(
        "Kilometrering",
        kilometer_options,
        format_func=lambda option: option[1],
        index=None,
        placeholder="Søg eller vælg kilometrering",
        key="kilometer",
        on_change=reset_dependent_filters,
    )
    st.button("Nulstil filtre", on_click=reset_filters, width="stretch")

selected_feature_id = selected_kilometer[0] if selected_kilometer else None
filtered_features = cached_filter_features(
    tib=selected_tib,
    banenumber=selected_banenumber,
    station=selected_station,
    section=selected_section,
    feature_id=selected_feature_id,
)
has_active_filter = any(
    value is not None
    for value in (
        selected_tib,
        selected_banenumber,
        selected_station,
        selected_section,
        selected_kilometer,
    )
)
highlighted_features = filtered_features if has_active_filter else []
highlighted_ids = tuple(feature_ids(highlighted_features))

with map_column:
    map_event = st.pydeck_chart(
        build_cached_map(highlighted_ids),
        key=f"danmarkskort-{st.session_state.get('map_revision', 0)}",
        on_select="rerun",
        selection_mode="single-object",
        height=700,
    )

selected_objects = map_event.selection["objects"].get("banestraekninger", [])
selected_ids = feature_ids(filtered_features) if has_active_filter else []
has_single_banenumber = (
    len({feature.get("properties", {}).get("BANENR") for feature in filtered_features})
    == 1
)
if selected_banenumber and filtered_features:
    result_title = feature_title(filtered_features[0].get("properties", {}))
elif selected_tib:
    result_title = f"TIB {tib_label(selected_tib)}"
elif has_active_filter and has_single_banenumber:
    result_title = feature_title(filtered_features[0].get("properties", {}))
else:
    result_title = None

if selected_objects:
    properties = selected_objects[0].get("properties", selected_objects[0])
    clicked_banenumber = str(properties.get("BANENR") or "").strip()
    if clicked_banenumber and clicked_banenumber != selected_banenumber:
        st.session_state["pending_banenumber"] = clicked_banenumber
        st.rerun()

with filter_column:
    if result_title:
        st.subheader(result_title)
    if not selected_ids:
        st.info("Vælg et filter eller klik på en strækning på kortet.")
    else:
        selected_reference_type = None
        selected_reference_value = None
        if selected_banenumber:
            selected_reference_type = "BANENR"
            selected_reference_value = selected_banenumber
        elif selected_tib:
            selected_reference_type = "TIB"
            selected_reference_value = selected_tib

        contracts = contracts_for_features(
            tuple(selected_ids),
            reference_type=selected_reference_type,
            reference_value=selected_reference_value,
        )
        result_features = (
            filtered_features if has_active_filter else highlighted_features
        )

        kilometer_values = [
            value
            for feature in result_features
            for value in (
                feature.get("properties", {}).get("FRA_KM"),
                feature.get("properties", {}).get("TIL_KM"),
            )
            if isinstance(value, int | float)
        ]
        if kilometer_values:
            kilometer_start = min(kilometer_values)
            kilometer_end = max(kilometer_values)
            st.caption(
                f"Samlet kilometrering: {kilometer_start:.1f}–{kilometer_end:.1f} km"
            )

        strom_contracts = contracts
        sikring_contracts = contracts_for_sheet("Sikring")
        beredskab_contracts = contracts_for_sheet("Beredskab (interne krav)")

        rendered_sections = 0
        if strom_contracts.height:
            rendered_sections += 1
            with st.container(border=True):
                st.subheader("Strøm og Materiel")
                for contract_number, contract in enumerate(
                    strom_contracts.iter_rows(named=True), start=1
                ):
                    title = contract.get("Kontraktens titel") or (
                        f"Kontrakt {contract_number}"
                    )
                    with st.expander(str(title), expanded=strom_contracts.height == 1):
                        vertical_contract = {
                            "Felt": [key for key in contract.keys() if key != "Ark"],
                            "Værdi": [
                                "Ikke angivet"
                                if contract.get(key) is None
                                else str(contract.get(key))
                                for key in contract.keys()
                                if key != "Ark"
                            ],
                        }
                        st.dataframe(
                            vertical_contract,
                            hide_index=True,
                            width="stretch",
                            column_config={
                                "Felt": st.column_config.TextColumn(width="medium"),
                                "Værdi": st.column_config.TextColumn(width="large"),
                            },
                        )

        if sikring_contracts.height:
            rendered_sections += 1
            with st.container(border=True):
                st.subheader("Sikring")
                for contract_number, contract in enumerate(
                    sikring_contracts.iter_rows(named=True), start=1
                ):
                    title = contract.get("Kontraktens titel") or (
                        f"Kontrakt {contract_number}"
                    )
                    with st.expander(
                        str(title), expanded=sikring_contracts.height == 1
                    ):
                        vertical_contract = {
                            "Felt": [key for key in contract.keys() if key != "Ark"],
                            "Værdi": [
                                "Ikke angivet"
                                if contract.get(key) is None
                                else str(contract.get(key))
                                for key in contract.keys()
                                if key != "Ark"
                            ],
                        }
                        st.dataframe(
                            vertical_contract,
                            hide_index=True,
                            width="stretch",
                            column_config={
                                "Felt": st.column_config.TextColumn(width="medium"),
                                "Værdi": st.column_config.TextColumn(width="large"),
                            },
                        )

        if beredskab_contracts.height:
            rendered_sections += 1
            with st.container(border=True):
                st.subheader("Beredskab (interne krav)")
                for contract_number, contract in enumerate(
                    beredskab_contracts.iter_rows(named=True), start=1
                ):
                    title = (
                        f"{contract.get('Afdeling ') or 'Afdeling'} · "
                        f"{contract.get('Region') or 'Region'}"
                    )
                    with st.expander(
                        str(title), expanded=beredskab_contracts.height == 1
                    ):
                        vertical_contract = {
                            "Felt": [key for key in contract.keys() if key != "Ark"],
                            "Værdi": [
                                "Ikke angivet"
                                if contract.get(key) is None
                                else str(contract.get(key))
                                for key in contract.keys()
                                if key != "Ark"
                            ],
                        }
                        st.dataframe(
                            vertical_contract,
                            hide_index=True,
                            width="stretch",
                            column_config={
                                "Felt": st.column_config.TextColumn(width="medium"),
                                "Værdi": st.column_config.TextColumn(width="large"),
                            },
                        )

        if rendered_sections == 0:
            st.info("Der blev ikke fundet kontrakter for dette valg.")
