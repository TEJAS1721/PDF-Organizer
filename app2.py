import io
import pymupdf
import streamlit as st

st.set_page_config(page_title="PDF Advanced Editor & Cleaner", page_icon="📄", layout="wide")

# ==========================================
# 🔐 AUTHENTICATION FUNCTIONALITY
# ==========================================
def check_password():
    """Returns `True` if the user enters the correct username & password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        user = st.session_state.get("username", "TEJAS N")
        pwd = st.session_state.get("password", "TEJAS1721")

        # Fallback default credentials if st.secrets is not set up
        correct_user = st.secrets.get("credentials", {}).get("username", "admin")
        correct_pwd = st.secrets.get("credentials", {}).get("password", "pdfsecret123")

        if user == correct_user and pwd == correct_pwd:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password in session
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Render login form
    st.title("🔒 Restricted Access")
    st.write("Please log in with the authorized credentials to use the PDF Editor.")

    with st.form("login_form"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.form_submit_button("Log In", on_click=password_entered)

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Username or password incorrect.")

    return False

# Stop execution if authentication fails
if not check_password():
    st.stop()

# ==========================================
# 📄 MAIN APP (Protected Content)
# ==========================================
st.title("📄 PDF Auto-Align, Border & Footer Editor")

# Add a Logout button in the sidebar
with st.sidebar:
    st.write("Logged in as Authorized Member")
    if st.button("Log Out"):
        st.session_state["password_correct"] = False
        st.rerun()

# 1. Upload File
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.info(f"Loaded PDF with **{total_pages}** pages.")
    st.divider()

    col1, col2 = st.columns(2)

    # 2. Existing Elements Removal (Crop Margins)
    with col1:
        st.subheader("1. Remove Existing Borders/Header/Footer")
        st.caption("Crop outer edges to remove pre-existing headers, footers, or borders.")
        
        strip_margins = st.checkbox("Enable Margin Trimming (Crop Out Existing Borders/Footers)")
        crop_top, crop_bottom, crop_left, crop_right = 0, 0, 0, 0
        
        if strip_margins:
            c1, c2 = st.columns(2)
            with c1:
                crop_top = st.slider("Crop Top (Header area)", 0, 100, 30)
                crop_bottom = st.slider("Crop Bottom (Footer area)", 0, 100, 30)
            with c2:
                crop_left = st.slider("Crop Left Margin", 0, 100, 20)
                crop_right = st.slider("Crop Right Margin", 0, 100, 20)

    # 3. Heading Contrast & Scaling Options
    with col2:
        st.subheader("2. Heading Contrast & Text Rescaling")
        st.caption("Scale headings and titles based on text contrast/size.")
        
        enable_scaling = st.checkbox("Enable Heading Rescaling")
        heading_scale_factor = 1.0
        min_heading_size = 14.0
        
        if enable_scaling:
            min_heading_size = st.slider("Minimum font size to consider as Heading (pt):", 10.0, 36.0, 14.0)
            heading_scale_factor = st.slider("Heading Scaling Factor:", 0.5, 2.0, 1.25, step=0.05)

    st.divider()
    col3, col4 = st.columns(2)

    # 4. New Border & Alignment Options
    with col3:
        st.subheader("3. New Border & Alignment Settings")
        align_mode = st.radio(
            "Page Orientation Adjustment:",
            ["Keep Original", "Manual Rotation"]
        )
        manual_angle = 0
        if align_mode == "Manual Rotation":
            manual_angle = st.selectbox("Select rotation angle for all pages:", [0, 90, 180, 270])

        border_type = st.selectbox(
            "Select New Border Style:",
            ["None", "Solid Line", "Dashed Line", "Double Line"]
        )
        
        border_color = (0, 0, 0)
        border_margin = 15
        if border_type != "None":
            color_hex = st.color_picker("Border Color", "#000000")
            border_color = tuple(int(color_hex.lstrip('#')[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            border_margin = st.slider("Border Margin (points)", 5, 50, 15)

    # 5. New Footer & Target Pages Options
    with col4:
        st.subheader("4. New Footer & Target Pages")
        footer_type = st.radio("New Footer Content:", ["None", "Page Numbering (Page X of Y)", "Custom Text"])
        custom_footer_text = ""
        if footer_type == "Custom Text":
            custom_footer_text = st.text_input("Enter Custom Footer Text:", "Confidential Document")
            
        footer_position = st.selectbox("Footer Alignment:", ["Center", "Left", "Right"])

        apply_pages = st.radio("Apply Modifications to:", ["All Pages", "Specific Pages"])
        selected_pages = list(range(1, total_pages + 1))
        if apply_pages == "Specific Pages":
            page_input = st.text_input("Enter page numbers/ranges (e.g., 1, 3-5, 8):", value=f"1-{total_pages}")
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

    # --- PDF Processing Engine ---
    def process_pdf():
        processed_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        for idx, page in enumerate(processed_doc):
            page_num = idx + 1
            
            if align_mode == "Manual Rotation":
                page.set_rotation(manual_angle)

            if page_num in selected_pages:
                if strip_margins:
                    rect = page.rect
                    new_crop = pymupdf.Rect(
                        rect.x0 + crop_left,
                        rect.y0 + crop_top,
                        rect.x1 - crop_right,
                        rect.y1 - crop_bottom
                    )
                    page.set_cropbox(new_crop)

                rect = page.rect

                if enable_scaling:
                    text_instances = page.get_text("dict")["blocks"]
                    for b in text_instances:
                        if b.get("type") == 0:
                            for l in b["lines"]:
                                for s in l["spans"]:
                                    if s["size"] >= min_heading_size:
                                        page.draw_rect(s["bbox"], color=(1, 1, 1), fill=(1, 1, 1))
                                        new_size = s["size"] * heading_scale_factor
                                        page.insert_text(
                                            pymupdf.Point(s["bbox"][0], s["bbox"][3] - 2),
                                            s["text"],
                                            fontsize=new_size,
                                            color=pymupdf.sRGB_to_pdf(s["color"])
                                        )

                if border_type != "None":
                    border_rect = pymupdf.Rect(
                        rect.x0 + border_margin, 
                        rect.y0 + border_margin, 
                        rect.x1 - border_margin, 
                        rect.y1 - border_margin
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
                            rect.x0 + border_margin + 4, 
                            rect.y0 + border_margin + 4, 
                            rect.x1 - border_margin - 4, 
                            rect.y1 - border_margin - 4
                        )
                        shape.draw_rect(inner_rect)
                        shape.finish(color=border_color, width=1)
                    shape.commit()

                if footer_type != "None":
                    if footer_type == "Page Numbering (Page X of Y)":
                        footer_text = f"Page {page_num} of {total_pages}"
                    else:
                        footer_text = custom_footer_text

                    footer_rect = pymupdf.Rect(rect.x0 + 30, rect.y1 - 35, rect.x1 - 30, rect.y1 - 10)

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
        page_to_preview = modified_doc[preview_page_num - 1]
        pix = page_to_preview.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        
        st.image(img_bytes, caption=f"Page {preview_page_num} Preview", use_container_width=True)

    modified_doc.close()
    doc.close()
