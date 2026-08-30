from dataclasses import dataclass
from html import escape
from typing import Any

import polars as pl
import streamlit as st

SIKRING_AREA_COLUMN = (
    "Geografisk område + Banenumre/TIB-strækning med responstid "
    "for den enkelte strækning"
)


@dataclass(frozen=True)
class ContractItem:
    key: str
    category: str
    title: str
    data: dict[str, Any]


def _text(value: object) -> str:
    if value is None or not str(value).strip():
        return "Ikke angivet"
    return str(value)


def _title_text(value: object) -> str:
    return " ".join(_text(value).split())


def _field(label: str, value: object) -> None:
    safe_label = escape(label)
    safe_value = escape(_text(value)).replace("\n", "<br>")
    st.markdown(
        f'<div class="contract-field">'
        f'<div class="contract-field-label">{safe_label}</div>'
        f'<div class="contract-field-value">{safe_value}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _items(
    strom: pl.DataFrame,
    sikring: pl.DataFrame,
    beredskab: pl.DataFrame,
    forsk: pl.DataFrame,
) -> list[ContractItem]:
    items = []
    for index, contract in enumerate(strom.iter_rows(named=True)):
        title = _text(contract.get("Kontraktens titel"))
        items.append(
            ContractItem(f"strom-{index}", "Strøm og Materiel", title, contract)
        )
    for index, contract in enumerate(forsk.iter_rows(named=True)):
        title = _text(contract.get("Kontraktens titel"))
        items.append(
            ContractItem(
                f"fors-{index}", "Fors, afvanding geoteknik, bro", title, contract
            )
        )
    for index, contract in enumerate(sikring.iter_rows(named=True)):
        title = _text(contract.get("Kontraktens titel"))
        items.append(ContractItem(f"sikring-{index}", "Sikring", title, contract))
    for index, contract in enumerate(beredskab.iter_rows(named=True)):
        department = _title_text(contract.get("Afdeling "))
        region = _title_text(contract.get("Region"))
        title = f"{department} · {region}"
        items.append(
            ContractItem(
                f"beredskab-{index}", "Beredskab (interne krav)", title, contract
            )
        )
    return items


def _render_strom(contract: dict[str, Any]) -> None:
    overview, response, penalties = st.tabs(
        ["Overblik", "Beredskab og fejlretning", "Boder"]
    )
    with overview:
        left, right = st.columns(2)
        with left:
            _field("Leverandør", contract.get("Leverandørnavn"))
        with right:
            _field("SAP-nummer", contract.get("SAP nummer"))
        _field("Responstid", contract.get("Responstid"))
        st.divider()
        manager = _text(contract.get("Vedligeholdelsesforvalter"))
        initials = _text(contract.get("Vedligeholdelsesforvalter - Initialer"))
        if initials != "Ikke angivet":
            manager = f"{manager} ({initials})"
        left, right = st.columns(2)
        with left:
            _field("Vedligeholdelsesforvalter", manager)
            _field("GFS", contract.get("GFS"))
        with right:
            _field("Kontraktansvarlig", contract.get("Kontraktansvarlig (leder)"))
    with response:
        _field(
            "Beskrivelse af beredskabet",
            contract.get("Beskrivelse af beredskabet"),
        )
        _field("Størrelse på beredskabet", contract.get("Størrelse på beredskabet"))
        _field(
            "Fremgangsmåde omkring fejlretning",
            contract.get("Beskrevet fremgangsmåde omkring fejlretning"),
        )
    with penalties:
        _field("Beskrivelse af boderne", contract.get("Beskrivelse af boderne"))


def _render_navigation_items(
    items: list[ContractItem], selected_key: str, color: str
) -> str:
    item_container = st.container(key=f"nav_{color}")
    with item_container:
        for item in items:
            row_key = (
                "selected_contract_item"
                if item.key == selected_key
                else f"contract_item_{item.key}"
            )
            with st.container(key=row_key):
                if st.button(
                    item.title,
                    key=f"contract-nav-{item.key}",
                    type="tertiary",
                    width="stretch",
                ):
                    selected_key = item.key
                    st.session_state["selected_contract"] = selected_key
    return selected_key


def _render_sikring(contract: dict[str, Any]) -> None:
    overview, response, penalties, contact = st.tabs(
        ["Overblik", "Beredskab og fejlretning", "Boder", "Kontakt"]
    )
    with overview:
        _field("Leverandør", contract.get("Leverandørnavn"))
        _field(
            "Geografisk område og responstid",
            contract.get(SIKRING_AREA_COLUMN),
        )
        _field("Ikrafttrædelse", contract.get("Ikraft-trædelse"))
        _field(
            "Varighed i år",
            contract.get(
                "Varighed _x000D_\ni år (inkl mobilisering + option på forlængelse)"
            ),
        )
        _field("Responstid", contract.get("Responstid"))
    with response:
        _field(
            "Beskrivelse af beredskabet",
            contract.get("Beskrivelse af beredskabet"),
        )
        _field("Størrelse på beredskabet", contract.get("Størrelse på beredskabet"))
        _field(
            "Fremgangsmåde omkring fejlretning",
            contract.get("Beskrevet fremgangsmåde omkring fejlretning"),
        )
    with penalties:
        _field("Beskrivelse af boderne", contract.get("Beskrivelse af boderne"))
    with contact:
        _field(
            "Vedligeholdelsesforvalter",
            contract.get("Vedligeholdelsesforvalter"),
        )
        _field("GFS", contract.get("GFS"))
        _field("Kontraktansvarlig", contract.get("Kontraktansvarlig (leder)"))
        _field("SAP-nummer", contract.get("SAP nummer"))


def _render_beredskab(contract: dict[str, Any]) -> None:
    overview, response, data = st.tabs(
        ["Overblik", "Beredskab og fejlretning", "Data og definitioner"]
    )
    with overview:
        _field(
            "Maks. responstid i rådighedsvagten (minutter)",
            contract.get("Maks. Responstid i rådighedsvagten (minutter)"),
        )
        _field(
            "Maks. responstid i tjenestetiden (minutter)",
            contract.get("Maks. Responstid i tjenestetiden (minutter"),
        )
        _field("KPI-mål", contract.get("KPI-mål"))
    with response:
        _field(
            "Beskrivelse af beredskabet",
            contract.get("Beskrivelse af beredskabet"),
        )
        _field(
            "Antal fejl som skal kunne håndteres på én gang",
            contract.get("Antal fejl som skal kunne håndteres på én gang "),
        )
        _field(
            "Arbejdshold og personer pr. hold",
            contract.get(
                "Antal arbejdshold og personer pr. hold, som der kan stilles med."
            ),
        )
    with data:
        _field("Krav til dataregistrering", contract.get("Krav til dataregistrering"))
        _field("Definitioner", contract.get("Definitioner"))


def render_contract_browser(
    container: Any,
    strom: pl.DataFrame,
    sikring: pl.DataFrame,
    beredskab: pl.DataFrame,
    forsk: pl.DataFrame,
) -> None:
    items = _items(strom, sikring, beredskab, forsk)
    if not items:
        container.info("Der blev ikke fundet kontrakter for dette valg.")
        return

    item_by_key = {item.key: item for item in items}
    selected_key = st.session_state.get("selected_contract")
    if selected_key not in item_by_key:
        selected_key = items[0].key
        st.session_state["selected_contract"] = selected_key

    navigation, details = container.columns([0.34, 0.66], gap="medium")
    navigation_panel = navigation.container(
        height=550, border=False, key="contract_navigation"
    )
    with navigation_panel:
        strom_items = [item for item in items if item.category == "Strøm og Materiel"]
        if strom_items:
            with (
                st.container(key="category_strom"),
                st.expander("STRØM OG MATERIEL", expanded=True),
            ):
                selected_key = _render_navigation_items(
                    strom_items, selected_key, "strom"
                )

        fors_items = [
            item for item in items if item.category == "Fors, afvanding geoteknik, bro"
        ]
        if fors_items:
            with (
                st.container(key="category_fors"),
                st.expander("FORS, AFVANDING GEOTEKNIK, BRO"),
            ):
                selected_key = _render_navigation_items(
                    fors_items, selected_key, "fors"
                )

        sikring_items = [item for item in items if item.category == "Sikring"]
        if sikring_items:
            with (
                st.container(key="category_sikring"),
                st.expander("SIKRING"),
            ):
                selected_key = _render_navigation_items(
                    sikring_items, selected_key, "sikring"
                )

        beredskab_items = [
            item for item in items if item.category == "Beredskab (interne krav)"
        ]
        if beredskab_items:
            with (
                st.container(key="category_beredskab"),
                st.expander("BEREDSKAB"),
            ):
                selected_key = _render_navigation_items(
                    beredskab_items, selected_key, "beredskab"
                )

    selected = item_by_key[selected_key]
    details_panel = details.container(height=550, border=False, key="contract_content")
    with details_panel:
        color_class = {
            "Strøm og Materiel": "strom",
            "Fors, afvanding geoteknik, bro": "fors",
            "Sikring": "sikring",
            "Beredskab (interne krav)": "beredskab",
        }[selected.category]
        category_label = (
            "Beredskab"
            if selected.category == "Beredskab (interne krav)"
            else selected.category
        )
        st.markdown(
            f'<div class="contract-eyebrow {color_class}">'
            f"{escape(category_label)}</div>",
            unsafe_allow_html=True,
        )
        st.subheader(selected.title)
        if selected.category == "Beredskab (interne krav)":
            st.caption(_text(selected.data.get("Afdeling ")))
            _render_beredskab(selected.data)
        elif selected.category == "Sikring":
            st.caption(_text(selected.data.get("Leverandørnavn")))
            _render_sikring(selected.data)
        else:
            reference_type = selected.data.get("Referencetype")
            reference_value = _text(selected.data.get("Referenceværdi"))
            reference_label = (
                f"Banenummer {reference_value}"
                if reference_type == "BANENR"
                else f"TIB {reference_value}"
            )
            subtitle = " · ".join(
                (
                    reference_label,
                    _text(selected.data.get("Strækningsbeskrivelse")),
                    _text(selected.data.get("Geografisk område")),
                )
            )
            st.caption(subtitle)
            _render_strom(selected.data)
