import streamlit as st

from contract_view import render_contract_browser
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
    st.session_state.pop("pending_map_reference", None)
    st.session_state.pop("selected_contract", None)
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


st.set_page_config(page_title="Fejlretningskort", page_icon="🗺️", layout="wide")
st.markdown(
    """
    <style>
        .stApp,
        [data-testid="stAppViewContainer"],
        .stMain,
        .stMainBlockContainer {
            background: #ffffff;
        }
        .stMainBlockContainer { padding-top: .35rem; padding-bottom: .5rem; }
        .app-title {
            color: #2f303d;
            font-size: 1.8rem;
            font-weight: 750;
            line-height: 1.1;
            margin: 0 0 .35rem;
        }
        div[data-testid="stSelectbox"] label {
            font-size: .8rem; margin-bottom: -.25rem;
        }
        div[data-baseweb="select"] > div { min-height: 2.25rem; }
        div[data-testid="stButton"] button {
            min-height: 2.25rem; height: 2.25rem;
            padding-top: .25rem; padding-bottom: .25rem;
        }
        .st-key-contract_details h3 {
            font-size: 1.35rem; line-height: 1.2;
            margin-top: .15rem; margin-bottom: .25rem;
        }
        .st-key-contract_details {
            background: #ffffff;
        }
        .st-key-contract_details p {
            font-size: .92rem; line-height: 1.4; margin-bottom: .2rem;
        }
        .st-key-contract_details .contract-category {
            display: flex; justify-content: space-between;
            margin: .5rem 0 .25rem; color: #777;
            font-size: .72rem; font-weight: 700;
            letter-spacing: .07em; text-transform: uppercase;
        }
        .st-key-contract_details .contract-eyebrow {
            color: #07885f; font-size: .75rem; font-weight: 700;
            letter-spacing: .06em; text-transform: uppercase;
        }
        .st-key-contract_details .contract-eyebrow.sikring { color: #d97706; }
        .st-key-contract_details .contract-eyebrow.beredskab { color: #dc2626; }
        .st-key-contract_navigation {
            border-right: 1px solid #d9d9d9;
            padding-right: 1rem;
            background: #ffffff;
            scrollbar-gutter: stable;
        }
        .st-key-contract_content {
            padding-left: .35rem;
            scrollbar-gutter: stable;
        }
        .st-key-contract_navigation details {
            border: 0;
            border-top: 1px solid #ececec;
            border-radius: 0;
            background: transparent;
        }
        .st-key-contract_navigation details summary {
            color: #777;
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .06em;
            text-transform: uppercase;
        }
        .st-key-contract_navigation div[data-testid="stButton"] button {
            height: auto;
            min-height: 2rem;
            justify-content: flex-start;
            border: 0;
            background: transparent;
            box-shadow: none;
            padding-left: .25rem;
            text-align: left;
        }
        .st-key-contract_navigation div[data-testid="stButton"] button p {
            width: 100%;
            text-align: left;
            white-space: normal;
        }
        .st-key-category_strom details summary,
        .st-key-category_strom details summary p { color: #07885f !important; }
        .st-key-category_sikring details summary,
        .st-key-category_sikring details summary p { color: #d97706 !important; }
        .st-key-category_beredskab details summary,
        .st-key-category_beredskab details summary p { color: #dc2626 !important; }
        .st-key-contract_navigation div[data-testid="stButton"] button:hover {
            background: #f5f5f5;
            color: inherit;
        }
        .st-key-selected_contract_item div[data-testid="stButton"] button {
            font-weight: 650;
        }
        .st-key-contract_details .contract-field {
            font-size: .92rem; line-height: 1.4; margin-bottom: .7rem;
        }
        .st-key-contract_details .contract-field-label {
            color: #777; font-size: .72rem; font-weight: 700;
            letter-spacing: .04em; margin-bottom: .12rem;
            text-transform: uppercase;
        }
        .st-key-contract_details button[data-baseweb="tab"] {
            font-size: .78rem; padding-left: .45rem; padding-right: .45rem;
        }
        .st-key-contract_details button[kind="tertiary"] {
            height: auto; min-height: 2rem; justify-content: flex-start;
            text-align: left; white-space: normal;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="app-title">Fejlretningskort</div>', unsafe_allow_html=True)

pending_map_reference = st.session_state.pop("pending_map_reference", None)
if pending_map_reference:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)
    reference_type, reference_value = pending_map_reference
    filter_key = "banenumber" if reference_type == "BANENR" else "tib"
    st.session_state[filter_key] = reference_value

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

filter_columns = st.columns([0.8, 0.7, 1, 1.15, 1.25, 0.4], vertical_alignment="bottom")
with filter_columns[0]:
    selected_banenumber = st.selectbox(
        "Banenummer",
        banenumber_options,
        index=None,
        placeholder="Vælg banenummer",
        key="banenumber",
        on_change=reset_dependent_filters,
        args=(("station", "section", "kilometer")),
    )
with filter_columns[1]:
    selected_tib = st.selectbox(
        "TIB",
        tib_options,
        format_func=tib_label,
        index=None,
        placeholder="Vælg TIB",
        key="tib",
        on_change=reset_dependent_filters,
        args=(("banenumber", "station", "section", "kilometer")),
    )
with filter_columns[2]:
    selected_station = st.selectbox(
        "Station",
        station_options,
        index=None,
        placeholder="Vælg station",
        key="station",
        on_change=reset_dependent_filters,
        args=(("kilometer",)),
    )
with filter_columns[3]:
    selected_section = st.selectbox(
        "Strækning",
        section_options,
        index=None,
        placeholder="Vælg strækning",
        key="section",
        on_change=reset_dependent_filters,
        args=(("station", "kilometer")),
    )
with filter_columns[4]:
    selected_kilometer = st.selectbox(
        "Kilometrering",
        kilometer_options,
        format_func=lambda option: option[1],
        index=None,
        placeholder="Vælg kilometrering",
        key="kilometer",
        on_change=reset_dependent_filters,
    )
with filter_columns[5]:
    st.button("Ryd", on_click=reset_filters, width="stretch")

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

map_column, information_column = st.columns([1.05, 1], gap="large")
with map_column:
    map_event = st.pydeck_chart(
        build_cached_map(highlighted_ids),
        key=f"danmarkskort-{st.session_state.get('map_revision', 0)}",
        on_select="rerun",
        selection_mode="single-object",
        height=720,
    )

selected_objects = map_event.selection["objects"].get("banestraekninger", [])
if selected_objects:
    properties = selected_objects[0].get("properties", selected_objects[0])
    clicked_banenumber = str(properties.get("BANENR") or "").strip()
    clicked_tib = next(
        (tib.strip() for tib in str(properties.get("TIB") or "").split(",") if tib.strip()),
        "",
    )
    clicked_reference = (
        ("BANENR", clicked_banenumber)
        if clicked_banenumber
        else ("TIB", clicked_tib)
        if clicked_tib
        else None
    )
    current_reference = (
        ("BANENR", selected_banenumber)
        if selected_banenumber
        else ("TIB", selected_tib)
        if selected_tib
        else None
    )
    if clicked_reference and clicked_reference != current_reference:
        st.session_state["pending_map_reference"] = clicked_reference
        st.session_state.pop("selected_contract", None)
        st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
        st.rerun()

selected_ids = feature_ids(filtered_features) if has_active_filter else []
has_single_banenumber = (
    len({feature.get("properties", {}).get("BANENR") for feature in filtered_features}) == 1
)
if selected_banenumber and filtered_features:
    result_title = feature_title(filtered_features[0].get("properties", {}))
elif selected_tib:
    result_title = f"TIB {tib_label(selected_tib)}"
elif has_active_filter and has_single_banenumber:
    result_title = feature_title(filtered_features[0].get("properties", {}))
else:
    result_title = "Info"

information = information_column.container(height=720, border=True, key="contract_details")
information.subheader(result_title)
if not selected_ids:
    information.caption("Vælg et filter eller klik på en strækning på kortet.")
else:
    reference_type = "BANENR" if selected_banenumber else "TIB" if selected_tib else None
    reference_value = selected_banenumber or selected_tib
    strom_contracts = contracts_for_features(
        tuple(selected_ids),
        reference_type=reference_type,
        reference_value=reference_value,
    )
    sikring_contracts = contracts_for_sheet("Sikring")
    beredskab_contracts = contracts_for_sheet("Beredskab (interne krav)")

    kilometer_values = []
    for feature in filtered_features:
        properties = feature.get("properties", {})
        start = properties.get("FRA_KM")
        end = properties.get("TIL_KM")
        if start == 0 and end == 0:
            continue
        kilometer_values.extend(value for value in (start, end) if isinstance(value, int | float))
    summary = []
    if kilometer_values:
        summary.append(f"{min(kilometer_values):.1f}–{max(kilometer_values):.1f} km")
    if strom_contracts.height:
        area = strom_contracts.row(0, named=True).get("Geografisk område")
        if area:
            summary.append(str(area))
    summary.append("Sikring og Beredskab vises altid")
    information.caption(" · ".join(summary))
    information.divider()
    render_contract_browser(information, strom_contracts, sikring_contracts, beredskab_contracts)
