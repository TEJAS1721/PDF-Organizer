import streamlit as st
import fitz  # PyMuPDF
import io

try:
    from streamlit_sortables import sort_items
    SORTABLES_AVAILABLE = True
except ImportError:
    SORTABLES_AVAILABLE = False

st.set_page_config(page_title="PDF Page Manager", layout="wide")

st.title("📄 PDF Page Manager & Editor")
st.caption("Upload a PDF to reorder, rotate, duplicate, delete, and export pages easily.")

uploaded_file = st.file_uploader("Upload your PDF file", type=["pdf"])

if uploaded_file is not None:
    # Read PDF into PyMuPDF document
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.success(f"Successfully loaded PDF with **{total_pages}** pages.")

    # Initialize session state for page ordering
    if "page_order" not in st.session_state or len(st.session_state.get("page_order", [])) != total_pages:
        st.session_state["page_order"] = list(range(total_pages))

    # ==========================================
    # INTERACTIVE THUMBNAIL PAGE MANAGER
    # ==========================================
    st.subheader("🖼️ Interactive Page Thumbnail Manager")
    st.caption("Drag and drop pages to rearrange them, or configure rotation, duplication, and deletion below.")

    if SORTABLES_AVAILABLE:
        # Create a label mapping for the sortable items
        items_list = [f"Page {i + 1} (Original Index: {i})" for i in st.session_state["page_order"]]
        sorted_items = sort_items(items_list, header="Drag items to reorder pages:")
        
        # Parse back the original indices from the sorted labels
        if sorted_items:
            new_order = []
            for item in sorted_items:
                try:
                    orig_idx = int(item.split("Original Index: ")[1].rstrip(")"))
                    new_order.append(orig_idx)
                except (IndexError, ValueError):
                    pass
            if len(new_order) == total_pages:
                st.session_state["page_order"] = new_order
    else:
        st.warning("`streamlit-sortables` is not installed. Falling back to default order. Run `pip install streamlit-sortables` to enable drag-and-drop.")

    # Display thumbnails grid and individual page options (Rotation, Duplicate, Delete)
    cols_per_row = 3
    grid_cols = st.columns(cols_per_row)

    ui_page_configs = []
    for idx, orig_page_idx in enumerate(st.session_state["page_order"]):
        col_idx = idx % cols_per_row
        with grid_cols[col_idx]:
            page_obj = doc[orig_page_idx]
            pix = page_obj.get_pixmap(dpi=70)
            st.image(pix.tobytes("png"), caption=f"New Pos: {idx + 1} (Orig P{orig_page_idx + 1})", use_container_width=True)
            
            rot_choice = st.selectbox(f"Rotate P{orig_page_idx+1} (Pos {idx+1})", [0, 90, 180, 270], index=0, key=f"rot_{orig_page_idx}_{idx}")
            
            c_dup, c_del = st.columns(2)
            is_dup = c_dup.checkbox("Duplicate", key=f"dup_{orig_page_idx}_{idx}")
            is_del = c_del.checkbox("Delete", key=f"del_{orig_page_idx}_{idx}")
            st.divider()
            
            if not is_del:
                ui_page_configs.append((idx, orig_page_idx, rot_choice, is_dup))

    # Sort configurations based on the new visual layout order
    ui_page_configs.sort(key=lambda x: x[0])

    # ==========================================
    # SAVE & EXPORT SECTION
    # ==========================================
    if st.button("💾 Save & Generate Modified PDF", type="primary"):
        new_doc = fitz.open()
        
        for _, orig_page_idx, rot_choice, is_dup in ui_page_configs:
            # Handle duplicates
            duplicates_count = 2 if is_dup else 1
            for _ in range(duplicates_count):
                new_doc.insert_pdf(doc, from_page=orig_page_idx, to_page=orig_page_idx)
                # Apply rotation to the newly inserted page
                if rot_choice != 0:
                    last_page = new_doc[-1]
                    current_rot = last_page.rotation
                    last_page.set_rotation((current_rot + rot_choice) % 360)

        # Save to bytes buffer
        output_buffer = io.BytesIO()
        new_doc.save(output_buffer)
        output_buffer.seek(0)
        
        st.success("PDF processed successfully!")
        st.download_button(
            label="⬇️ Download Modified PDF",
            data=output_buffer,
            file_name="modified_document.pdf",
            mime="application/pdf"
        )
