import io
import pymupdf
import streamlit as st

st.set_page_config(page_title="PDF Editor & Previewer", page_icon="📄", layout="wide")
st.title("📄 PDF Auto-Align, Border & Footer Editor")

# 1. Upload File
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file is not None:
    # Read bytes into session memory so we can re-process easily
    pdf_bytes = uploaded_file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.info(f"Loaded PDF with **{total_pages}** pages.")
    st.divider()

    col1, col2 = st.columns(2)

    # 2. Alignment & Rotation Options
    with col1:
        st.subheader("1. Alignment & Rotation")
        align_mode = st.radio(
            "Page Orientation Adjustment:",
            ["Auto-Align (Detect text orientation)", "Manual Rotation"]
        )
        
        manual_angle = 0
        if align_mode == "Manual Rotation":
            manual_angle = st.selectbox("Select rotation angle for all pages:", [0, 90, 180, 270])

    # 3. Border Options
    with col2:
        st.subheader("2. Border Settings")
        border_type = st.selectbox(
            "Select Border Style:",
            ["None", "Solid Line", "Dashed Line", "Double Line"]
        )
        
        border_color = (0, 0, 0)
        border_margin = 15
        if border_type != "None":
            color_hex = st.color_picker("Border Color", "#000000")
            border_color = tuple(int(color_hex.lstrip('#')[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            border_margin = st.slider("Border Margin (points)", 5, 50, 15)

    st.divider()
    col3, col4 = st.columns(2)

    # 4. Footer Options
    with col3:
        st.subheader("3. Footer Settings")
        footer_type = st.radio("Footer Content:", ["None", "Page Numbering (Page X of Y)", "Custom Text"])
        
        custom_footer_text = ""
        if footer_type == "Custom Text":
            custom_footer_text = st.text_input("Enter Custom Footer Text:", "Confidential Document")
            
        footer_position = st.selectbox("Footer Alignment:", ["Center", "Left", "Right"])

    # 5. Target Pages Options
    with col4:
        st.subheader("4. Target Pages")
        apply_pages = st.radio("Apply Border & Footer to:", ["All Pages", "Specific Pages"])
        
        selected_pages = list(range(1, total_pages + 1))
        if apply_pages == "Specific Pages":
            page_input = st.text_input(
                "Enter page numbers/ranges (e.g., 1, 3-5, 8):", 
                value=f"1-{total_pages}"
            )
            parsed_pages = set()
            try:
                for part in page_input.split(","):
                    part = part.strip()
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        parsed_pages.update(range(start, end + 1))
                    elif part.isdigit():
                        parsed_pages.add(int(part))
                selected_pages = sorted([p for p in parsed_pages if 1 <= p <= total_pages])
            except Exception:
                st.warning("Invalid page selection format. Falling back to all pages.")

    st.divider()

    # --- Processing Function ---
    def process_pdf():
        # Re-open fresh document stream
        processed_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        for idx, page in enumerate(processed_doc):
            page_num = idx + 1
            
            # Rotation Logic
            if align_mode == "Auto-Align (Detect text orientation)":
                try:
                    text_page = page.get_textpage()
                    dict_data = text_page.extractBLOCKS()
                    if page.rotation != 0:
                        page.set_rotation(0)
                except Exception:
                    pass
            else:
                page.set_rotation(manual_angle)

            # Targeted Pages Modifications
            if page_num in selected_pages:
                rect = page.rect
                width, height = rect.width, rect.height

                # Border Logic
                if border_type != "None":
                    border_rect = pymupdf.Rect(
                        border_margin, 
                        border_margin, 
                        width - border_margin, 
                        height - border_margin
                    )
                    
                    shape = page.new_shape()
                    if border_type == "Solid Line":
                        shape.draw_rect(border_rect)
                        shape.finish(color=border_color, width=2)
                    elif border_type == "Dashed Line":
                        shape.draw_rect(border_rect)
                        shape.finish(color=border_color, width=2, dashes="[3 3] 0")
                    elif border_type == "Double Line":
                        shape.draw_rect(border_rect)
                        shape.finish(color=border_color, width=1)
                        inner_rect = pymupdf.Rect(
                            border_margin + 4, 
                            border_margin + 4, 
                            width - border_margin - 4, 
                            height - border_margin - 4
                        )
                        shape.draw_rect(inner_rect)
                        shape.finish(color=border_color, width=1)
                    shape.commit()

                # Footer Logic
                if footer_type != "None":
                    if footer_type == "Page Numbering (Page X of Y)":
                        footer_text = f"Page {page_num} of {total_pages}"
                    else:
                        footer_text = custom_footer_text

                    footer_rect = pymupdf.Rect(30, height - 35, width - 30, height - 10)

                    align_mapping = {
                        "Left": pymupdf.TEXT_ALIGN_LEFT,
                        "Center": pymupdf.TEXT_ALIGN_CENTER,
                        "Right": pymupdf.TEXT_ALIGN_RIGHT
                    }

                    page.insert_textbox(
                        footer_rect,
                        footer_text,
                        fontsize=10,
                        color=(0.2, 0.2, 0.2),
                        align=align_mapping[footer_position]
                    )
        return processed_doc

    # Process document in memory for preview and download
    modified_doc = process_pdf()

    # 6. Live Preview Section
    st.subheader("👁️ Live Document Preview")
    
    preview_col1, preview_col2 = st.columns([1, 3])
    
    with preview_col1:
        preview_page_num = st.number_input(
            "Select Page to Preview:", 
            min_value=1, 
            max_value=total_pages, 
            value=1, 
            step=1
        )
        st.caption(f"Showing page {preview_page_num} of {total_pages}")
        
        # Output Bytes for download button
        output_buffer = io.BytesIO()
        modified_doc.save(output_buffer)
        output_bytes = output_buffer.getvalue()

        st.download_button(
            label="📥 Download Modified PDF",
            data=output_bytes,
            file_name="modified_document.pdf",
            mime="application/pdf",
            type="primary"
        )

    with preview_col2:
        # Render selected page to image
        page_to_preview = modified_doc[preview_page_num - 1]
        pix = page_to_preview.get_pixmap(dpi=150)  # Render page to Pixmap image
        img_bytes = pix.tobytes("png")
        
        st.image(img_bytes, caption=f"Page {preview_page_num} Preview", use_container_width=True)

    modified_doc.close()
    doc.close()
