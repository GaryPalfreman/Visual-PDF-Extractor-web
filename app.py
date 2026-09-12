import io

import fitz  # PyMuPDF
import streamlit as st
from PyPDF2 import PdfReader, PdfWriter

st.set_page_config(page_title="Visual PDF Extractor", page_icon="📄", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.1rem;}
    .page-card {border: 1px solid rgba(128,128,128,.35); border-radius: 12px; padding: .7rem; margin-bottom: .5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def render_page(pdf_bytes: bytes, page_index: int, width: int = 700) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.45, 1.45), alpha=False)
        image = pix.tobytes("png")
    finally:
        doc.close()
    return image


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
        reader = readers[source_id]
        writer.add_page(reader.pages[item["page_index"]])

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def reset_all():
    st.session_state.sources = []
    st.session_state.selections = []


if "sources" not in st.session_state:
    st.session_state.sources = []
if "selections" not in st.session_state:
    st.session_state.selections = []

st.title("Visual PDF Extractor")
st.caption("Upload PDFs, visually choose the pages you need, combine selections from multiple PDFs, preview the result, and download one new PDF.")

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
        source_id = f"{file.name}:{len(raw)}:{hash(raw)}"
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
            st.caption(f"{count} page(s)")
            cols = st.columns(2)
            for page_index in range(count):
                with cols[page_index % 2]:
                    st.markdown('<div class="page-card">', unsafe_allow_html=True)
                    st.markdown(f"**Page {page_index + 1}**")
                    st.image(render_page(source["pdf_bytes"], page_index), use_container_width=True)
                    key = f"select::{source['source_id']}::{page_index}"
                    already = any(
                        item["source_id"] == source["source_id"] and item["page_index"] == page_index
                        for item in st.session_state.selections
                    )
                    selected = st.checkbox("Select this page", value=already, key=key)
                    if selected and not already:
                        st.session_state.selections.append({
                            "source_id": source["source_id"],
                            "source_name": source["name"],
                            "page_index": page_index,
                            "pdf_bytes": source["pdf_bytes"],
                        })
                    elif not selected and already:
                        st.session_state.selections = [
                            item for item in st.session_state.selections
                            if not (item["source_id"] == source["source_id"] and item["page_index"] == page_index)
                        ]
                    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Selected pages")

    if not st.session_state.selections:
        st.info("Select at least one page above.")
    else:
        labels = [f"{i + 1}. {item['source_name']} - Page {item['page_index'] + 1}" for i, item in enumerate(st.session_state.selections)]
        st.write("Current output order:")
        for label in labels:
            st.write(label)

        st.markdown("### Reorder or remove")
        selected_position = st.selectbox(
            "Selected page",
            range(len(labels)),
            format_func=lambda i: labels[i],
        )
        c1, c2, c3 = st.columns(3)
        if c1.button("Move up", use_container_width=True, disabled=selected_position == 0):
            i = selected_position
            st.session_state.selections[i - 1], st.session_state.selections[i] = st.session_state.selections[i], st.session_state.selections[i - 1]
            st.rerun()
        if c2.button("Move down", use_container_width=True, disabled=selected_position == len(labels) - 1):
            i = selected_position
            st.session_state.selections[i + 1], st.session_state.selections[i] = st.session_state.selections[i], st.session_state.selections[i + 1]
            st.rerun()
        if c3.button("Remove selected page", use_container_width=True):
            st.session_state.selections.pop(selected_position)
            st.rerun()

        combined = build_combined_pdf(st.session_state.selections)

        with st.expander("Preview combined PDF", expanded=False):
            st.caption("Preview is shown page-by-page in final output order.")
            for i, item in enumerate(st.session_state.selections):
                st.markdown(f"**Output page {i + 1}: {item['source_name']} - source page {item['page_index'] + 1}**")
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
