# Visual PDF Extractor Web

Streamlit web conversion of the original Tkinter Visual PDF Extractor.

## Features

- Upload one or more PDF files
- Render visual page previews in the browser
- Select individual pages from each source PDF
- Combine selected pages from multiple PDFs
- Reorder selected output pages
- Remove selected pages before export
- Preview the final output order
- Download one combined PDF
- Dark Streamlit interface

## Important fix from the desktop version

The original desktop program appended the final temporary page twice when saving the combined PDF. The web version builds the output directly from the selected source pages and does not duplicate the last page.

## Privacy / storage

The app is intentionally download-based. Uploaded PDFs and selected pages are held only in the active Streamlit session and are not deliberately persisted by the application. The final PDF is generated in memory and downloaded to the user's computer.

Because this is a web-hosted Streamlit application, uploaded PDFs are transmitted to the Streamlit-hosted process for temporary processing. Do not use the public deployment for documents that are required to never leave the local computer; run the app locally for that requirement.

## Deploy on Streamlit Community Cloud

- Repository: `GaryPalfreman/Visual-PDF-Extractor-web`
- Branch: `main`
- Main file path: `app.py`

