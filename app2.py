import io
import os
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# Page Configuration
st.set_page_config(
    page_title="PDF Organizer & Studio",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 6px; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("📄 Advanced PDF Organizer & Suite")
    st.markdown("Upload, inspect, reorder, rotate, and modify your PDF files effortlessly.")

    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

    if uploaded_file is not None:
        bytes_data = uploaded_file.read()
        doc = fitz.open(stream=bytes_data, filetype="pdf")

        st.sidebar.header("Document Info")
        st.sidebar.text(f"Filename: {uploaded_file.name}")
        st.sidebar.text(f"Total Pages: {len(doc)}")

        st.markdown("---")
        st.subheader("Interactive Page Management")
        st.markdown("Review thumbnails below, adjust their target positions, apply rotations, or delete unwanted pages.")

        # Display pages in a grid layout
        cols_per_row = 3
        grid_cols = st.columns(cols_per_row)

        new_order = []
        
        for orig_page_idx in range(len(doc)):
            col_idx = orig_page_idx % cols_per_row
            with grid_cols[col_idx]:
                page_obj = doc[orig_page_idx]
                pix = page_obj.get_pixmap(dpi=70)
                st.image(pix.tobytes("png"), caption=f"Page {orig_page_idx+1}", use_container_width=True)

                new_pos = st.number_input(
                    f"Target Position P{orig_page_idx+1}", 
                    min_value=1, 
                    max_value=len(doc), 
                    value=orig_page_idx+1, 
                    key=f"pos_{orig_page_idx}"
                )
                rot_choice = st.selectbox(
                    f"Rotate P{orig_page_idx+1}", 
                    [0, 90, 180, 270], 
                    key=f"rot_{orig_page_idx}"
                )
                
                delete_page = st.checkbox(f"Delete Page {orig_page_idx+1}", key=f"del_{orig_page_idx}")
                
                st.markdown("---")

        st.info("Modify your configuration above and apply changes to generate the updated PDF document.")

    else:
        st.info("Please upload a PDF file from your device to get started.")

if __name__ == "__main__":
    main()
