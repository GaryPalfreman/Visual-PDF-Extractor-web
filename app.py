import hashlib
import io
import re

import fitz  # PyMuPDF
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from streamlit_sortables import sort_items

st.set_page_config(page_title="Visual PDF Extractor", page_icon="📄", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.1rem;}
    .page-card {border: 1px solid rgba(128,128,128,.35); border-radius: 12px; padding: .7rem; margin-bottom: .5rem;}
    .selected-badge {font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_page(pdf_bytes: bytes, page_index: int) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return len(doc)
    finally:
        doc.close()


def build_combined_pdf(selections: list[dict]) -> bytes:
    writer = PdfWriter()
    readers: dict[str, PdfReader] = {}
    for item in selections:
        source_id = item["source_id"]
        if source_id not in readers:
            readers[source_id] = PdfReader(io.BytesIO(item["pdf_bytes"]))
        writer.add_page(readers[source_id].pages[item["page_index"]])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def reset_all():
    st.session_state.sources = []
    st.session_state.selections = []


def selected_key(source_id: str, page_index: int) -> tuple[str, int]:
    return source_id, page_index


def selection_keys() -> set[tuple[str, int]]:
    return {selected_key(item["source_id"], item["page_index"]) for item in st.session_state.selections}


def add_page(source: dict, page_index: int):
    key = selected_key(source["source_id"], page_index)
    if key in selection_keys():
        return
    st.session_state.selections.append({
        "source_id": source["source_id"],
        "source_name": source["name"],
        "page_index": page_index,
        "pdf_bytes": source["pdf_bytes"],
    })


def remove_page(source_id: str, page_index: int):
    st.session_state.selections = [
        item for item in st.session_state.selections
        if selected_key(item["source_id"], item["page_index"]) != selected_key(source_id, page_index)
    ]


def add_all_pages(source: dict):
    for i in range(page_count(source["pdf_bytes"])):
        add_page(source, i)


def remove_all_pages(source: dict):
    st.session_state.selections = [
        item for item in st.session_state.selections if item["source_id"] != source["source_id"]
    ]


def parse_page_range(text: str, max_page: int) -> list[int]:
    text = text.strip()
    if not text:
        return []
    pages: set[int] = set()
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if re.fullmatch(r"\d+", part):
            value = int(part)
            if value < 1 or value > max_page:
                raise ValueError(f"Page {value} is outside 1-{max_page}.")
            pages.add(value - 1)
        elif re.fullmatch(r"\d+\s*-\s*\d+", part):
            start, end = [int(v.strip()) for v in part.split("-")]
            if start > end:
                start, end = end, start
            if start < 1 or end > max_page:
                raise ValueError(f"Range {part} is outside 1-{max_page}.")
            pages.update(range(start - 1, end))
        else:
            raise ValueError(f"Could not understand '{part}'. Use formats like 1,3,5-8.")
    return sorted(pages)


def duplicate_rows(selections: list[dict]) -> list[str]:
    seen: set[tuple[str, int]] = set()
    duplicates: list[str] = []
    for item in selections:
        key = selected_key(item["source_id"], item["page_index"])
        if key in seen:
            duplicates.append(f"{item['source_name']} - Page {item['page_index'] + 1}")
        seen.add(key)
    return duplicates


if "sources" not in st.session_state:
    st.session_state.sources = []
if "selections" not in st.session_state:
    st.session_state.selections = []

st.title("Visual PDF Extractor")
st.caption("Upload PDFs, visually select pages, choose ranges, combine multiple documents, reorder the result, preview it, and download one new PDF.")

with st.sidebar:
    st.header("Session")
    st.metric("PDFs loaded", len(st.session_state.sources))
    st.metric("Pages selected", len(st.session_state.selections))
    if st.button("Clear everything", use_container_width=True):
        reset_all()
        st.rerun()
    st.caption("Uploaded files and selections are kept only for the current app session. Nothing is deliberately persisted by this app.")

upload = st.file_uploader("Upload one or more PDFs", type=["pdf"], accept_multiple_files=True)
if upload:
    known = {item["source_id"] for item in st.session_state.sources}
    added = False
    for file in upload:
        raw = file.getvalue()
        source_id = hashlib.sha256(raw).hexdigest()
        if source_id not in known:
            st.session_state.sources.append({"source_id": source_id, "name": file.name, "pdf_bytes": raw})
            known.add(source_id)
            added = True
    if added:
        st.rerun()

if not st.session_state.sources:
    st.info("Upload a PDF to begin.")
else:
    tabs = st.tabs([item["name"] for item in st.session_state.sources])
    for tab, source in zip(tabs, st.session_state.sources):
        with tab:
            count = page_count(source["pdf_bytes"])
            source_selected = [
                item for item in st.session_state.selections if item["source_id"] == source["source_id"]
            ]
            st.caption(f"{count} page(s) · {len(source_selected)} selected from this PDF")

            b1, b2, b3 = st.columns([1, 1, 2])
            if b1.button("Select all", key=f"all::{source['source_id']}", use_container_width=True):
                add_all_pages(source)
                st.rerun()
            if b2.button("Select none", key=f"none::{source['source_id']}", use_container_width=True):
                remove_all_pages(source)
                st.rerun()

            with b3:
                range_text = st.text_input(
                    "Page range",
                    placeholder="Example: 1,3,5-8",
                    key=f"range::{source['source_id']}",
                    label_visibility="collapsed",
                )
            r1, r2 = st.columns(2)
            if r1.button("Add range", key=f"add-range::{source['source_id']}", use_container_width=True):
                try:
                    for page_index in parse_page_range(range_text, count):
                        add_page(source, page_index)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if r2.button("Remove range", key=f"remove-range::{source['source_id']}", use_container_width=True):
                try:
                    for page_index in parse_page_range(range_text, count):
                        remove_page(source["source_id"], page_index)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

            st.divider()
            cols = st.columns(2)
            current_keys = selection_keys()
            for page_index in range(count):
                with cols[page_index % 2]:
                    st.markdown('<div class="page-card">', unsafe_allow_html=True)
                    selected = selected_key(source["source_id"], page_index) in current_keys
                    heading = f"**Page {page_index + 1}**"
                    if selected:
                        heading += "  ✅ Selected"
                    st.markdown(heading)
                    st.image(render_page(source["pdf_bytes"], page_index), use_container_width=True)
                    if selected:
                        if st.button("Remove page", key=f"remove::{source['source_id']}::{page_index}", use_container_width=True):
                            remove_page(source["source_id"], page_index)
                            st.rerun()
                    else:
                        if st.button("Add page", key=f"add::{source['source_id']}::{page_index}", use_container_width=True):
                            add_page(source, page_index)
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Selected pages")

    if not st.session_state.selections:
        st.info("Select at least one page above.")
    else:
        duplicates = duplicate_rows(st.session_state.selections)
        if duplicates:
            st.warning("Duplicate source pages detected: " + ", ".join(duplicates))
        else:
            st.success("No duplicate source pages detected.")

        st.markdown("### Drag to set the final output order")
        sort_labels = [
            f"{i + 1:02d} · {item['source_name']} · Page {item['page_index'] + 1}"
            for i, item in enumerate(st.session_state.selections)
        ]
        mapping = {label: item for label, item in zip(sort_labels, st.session_state.selections)}
        reordered_labels = sort_items(sort_labels, direction="vertical")
        reordered = [mapping[label] for label in reordered_labels]
        if [selected_key(i["source_id"], i["page_index"]) for i in reordered] != [
            selected_key(i["source_id"], i["page_index"]) for i in st.session_state.selections
        ]:
            st.session_state.selections = reordered
            st.rerun()

        labels = [
            f"{i + 1}. {item['source_name']} - Page {item['page_index'] + 1}"
            for i, item in enumerate(st.session_state.selections)
        ]
        selected_position = st.selectbox(
            "Selected output page",
            range(len(labels)),
            format_func=lambda i: labels[i],
        )
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Move up", use_container_width=True, disabled=selected_position == 0):
            i = selected_position
            st.session_state.selections[i - 1], st.session_state.selections[i] = st.session_state.selections[i], st.session_state.selections[i - 1]
            st.rerun()
        if c2.button("Move down", use_container_width=True, disabled=selected_position == len(labels) - 1):
            i = selected_position
            st.session_state.selections[i + 1], st.session_state.selections[i] = st.session_state.selections[i], st.session_state.selections[i + 1]
            st.rerun()
        if c3.button("Duplicate output page", use_container_width=True):
            item = dict(st.session_state.selections[selected_position])
            st.session_state.selections.insert(selected_position + 1, item)
            st.rerun()
        if c4.button("Remove output page", use_container_width=True):
            st.session_state.selections.pop(selected_position)
            st.rerun()

        combined = build_combined_pdf(st.session_state.selections)

        st.markdown("## Final combined-PDF preview")
        st.caption("This is the exact page sequence that will be written to the downloaded PDF.")
        preview_cols = st.columns(3)
        for i, item in enumerate(st.session_state.selections):
            with preview_cols[i % 3]:
                st.markdown(f"**Output {i + 1}**")
                st.caption(f"{item['source_name']} · source page {item['page_index'] + 1}")
                st.image(render_page(item["pdf_bytes"], item["page_index"]), use_container_width=True)

        output_name = st.text_input("Output filename", value="combined_extracted_pages.pdf")
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"

        st.download_button(
            "Download Combined PDF",
            data=combined,
            file_name=output_name,
            mime="application/pdf",
            use_container_width=True,
        )
