import io
import os
import zipfile
import secrets
import pymupdf
import streamlit as st
import bcrypt
import resend
from supabase import create_client, Client

# Optional imports for OCR & Canvas drawing
try:
    import pytesseract
    from PIL import Image as PILImage
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from streamlit_drawable_canvas import st_canvas
    import numpy as np
    CANVAS_AVAILABLE = True
except ImportError:
    CANVAS_AVAILABLE = False

st.set_page_config(page_title="PDF Advanced Editor & Redactor", page_icon="📄", layout="wide")

# ==========================================
# 🔌 DATABASE & EMAIL INITIALIZATION
# ==========================================
def get_secret(section, key, fallback=None):
    if section in st.secrets and key in st.secrets[section]:
        return st.secrets[section][key]
    upper_key = f"{section.upper()}_{key.upper()}"
    if upper_key in st.secrets:
        return st.secrets[upper_key]
    if key in st.secrets:
        return st.secrets[key]
    return fallback

SUPABASE_URL = get_secret("supabase", "url")
SUPABASE_KEY = get_secret("supabase", "key")
RESEND_API_KEY = get_secret("resend", "api_key")
ADMIN_EMAIL = get_secret("resend", "admin_email", "tn1721c@gmail.com")
ADMIN_PASSWORD = get_secret("resend", "admin_password", "Tejas1721")
APP_URL = get_secret("resend", "app_url", "https://pdf-organizer-mpjrzbydznasweblbkeebh.streamlit.app/")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

def send_approval_request_email(username, email, approval_token):
    approve_link = f"{APP_URL}/?action=approve&token={approval_token}"
    reject_link = f"{APP_URL}/?action=reject&token={approval_token}"

    content = f"""
    <h3>🔒 New Access Request for PDF Editor</h3>
    <p><strong>Username:</strong> {username}</p>
    <p><strong>Email:</strong> {email}</p>
    <br/>
    <p>Select an action below to update user permissions:</p>
    <a href="{approve_link}" style="background-color: #28a745; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">Approve User</a>
    &nbsp;&nbsp;
    <a href="{reject_link}" style="background-color: #dc3545; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">Reject Request</a>
    """
    try:
        resend.Emails.send({
            "from": "PDF App Auth <onboarding@resend.dev>",
            "to": ADMIN_EMAIL,
            "subject": f"Access Request from {username}",
            "html": content
        })
    except Exception:
        pass

# ==========================================
# 🔐 AUTHENTICATION & APPROVAL SYSTEM
# ==========================================
def auth_system():
    query_params = st.query_params
    if "action" in query_params and "token" in query_params:
        token = query_params["token"]
        action = query_params["action"]
        status_value = "approved" if action == "approve" else "rejected"
        
        if supabase:
            response = supabase.table("users").update({"status": status_value}).eq("approval_token", token).execute()
            if response.data:
                st.success(f"User request has been successfully **{status_value}**!")
            else:
                st.error("Invalid or expired token.")
        else:
            st.error("Supabase client is not initialized.")
        st.query_params.clear()

    if st.session_state.get("authenticated", False):
        return True

    st.title("🔒 Restricted Access - PDF Editor Tool")
    tab1, tab2 = st.tabs(["🔑 Log In", "📝 Request Access"])

    with tab1:
        with st.form("login_form_unique"):
            login_user = st.text_input("Username or Email", key="login_user_input")
            login_pass = st.text_input("Password", type="password", key="login_pass_input")
            submit_login = st.form_submit_button("Log In")

            if submit_login:
                if not login_user or not login_pass:
                    st.warning("Please fill in both fields.")
                elif not supabase:
                    st.error("Database connection missing.")
                else:
                    res = supabase.table("users").select("*").or_(f"username.eq.{login_user},email.eq.{login_user}").execute()
                    if res.data:
                        user_record = res.data[0]
                        if user_record["status"] == "pending":
                            st.warning("⏳ Your access request is pending admin approval.")
                        elif user_record["status"] == "rejected":
                            st.error("❌ Your request for access was declined.")
                        elif user_record["status"] == "approved":
                            try:
                                stored_hash = user_record["password_hash"].encode("utf-8")
                                if bcrypt.checkpw(login_pass.encode("utf-8"), stored_hash):
                                    st.session_state["authenticated"] = True
                                    st.session_state["user"] = user_record["username"]
                                    st.session_state["user_email"] = user_record["email"]
                                    st.rerun()
                                else:
                                    st.error("Incorrect password.")
                            except Exception:
                                st.error("Password verification error.")
                    else:
                        st.error("User not found.")

    with tab2:
        with st.form("request_form_unique"):
            req_username = st.text_input("Preferred Username", key="req_user_input")
            req_email = st.text_input("Email Address", key="req_email_input")
            req_password = st.text_input("Set Password", type="password", key="req_pass_input")
            submit_request = st.form_submit_button("Submit Access Request")

            if submit_request:
                if req_username and req_email and req_password:
                    if not supabase:
                        st.error("Database connection missing.")
                    else:
                        hashed_pw = bcrypt.hashpw(req_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                        token = secrets.token_urlsafe(32)
                        try:
                            supabase.table("users").insert({
                                "username": req_username,
                                "email": req_email,
                                "password_hash": hashed_pw,
                                "status": "pending",
                                "approval_token": token
                            }).execute()
                            st.success("✅ Access request submitted successfully! Pending admin approval.")
                            if RESEND_API_KEY:
                                send_approval_request_email(req_username, req_email, token)
                        except Exception:
                            st.error("User or Email already exists.")
                else:
                    st.warning("Please fill out all fields.")
    return False

if not auth_system():
    st.stop()

# ==========================================
# 📄 MAIN APP & NAVIGATION
# ==========================================
current_user_email = st.session_state.get("user_email", "").lower().strip()
is_primary_admin = (current_user_email == ADMIN_EMAIL.lower().strip())

st.title("📄 Advanced PDF Editor, Redactor & Suite")

with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.get('user', 'Member')}**")
    if is_primary_admin:
        st.caption("👑 **Role:** Administrator")
    else:
        st.caption("👤 **Role:** Standard User")

    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.session_state.pop("processed_pdf", None)
        st.session_state.pop("admin_unlocked", None)
        st.rerun()
    st.divider()

app_tabs = st.tabs(["📄 PDF Operations", "🔀 Merge / Split", "🖼️ Image & Form Tools", "🛡️ Admin Access"])
tab_pdf, tab_merge_split, tab_assets, tab_admin = app_tabs[0], app_tabs[1], app_tabs[2], app_tabs[3]

# ==========================================
# TAB 1: PDF OPERATIONS (Editor, Redact, Sign, Replace, Security)
# ==========================================
with tab_pdf:
    uploaded_file = st.file_uploader("Upload a PDF file to edit", type=["pdf"], key="primary_pdf_upload")

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        st.info(f"Loaded source PDF with **{total_pages}** page(s). Configure options in the sidebar and click **Save & Apply Changes**.")

        with st.sidebar:
            st.subheader("1. Page Operations & Rotation")
            rotate_angle = st.selectbox("Rotate Pages", [0, 90, 180, 270])
            pages_to_delete = st.multiselect("Remove Pages", options=list(range(1, total_pages + 1)))

            st.subheader("2. Text Redaction & Replacement")
            text_to_remove = st.text_input("Text Phrase to Erase/Replace", placeholder="e.g., Confidential")
            action_mode = st.radio("Text Action", ["Blackout / Erase", "Dynamic Text Replacement"], horizontal=True)
            replacement_text = ""
            if action_mode == "Dynamic Text Replacement":
                replacement_text = st.text_input("Replacement Phrase", placeholder="e.g., [REDACTED]")
            
            fill_color_choice = st.selectbox("Redaction Fill Color", ["White (Clean Erase)", "Black (Redact)"])
            fill_rgb = (1, 1, 1) if fill_color_choice.startswith("White") else (0, 0, 0)

            st.subheader("3. Coordinate-Based Erase")
            enable_area_erase = st.checkbox("Erase Custom Area Coordinates")
            if enable_area_erase:
                c1, c2 = st.columns(2)
                with c1:
                    x1 = st.number_input("Top-Left X", value=50, step=10)
                    y1 = st.number_input("Top-Left Y", value=50, step=10)
                with c2:
                    x2 = st.number_input("Bottom-Right X", value=200, step=10)
                    y2 = st.number_input("Bottom-Right Y", value=100, step=10)

            st.subheader("4. Digital Signature Insertion")
            enable_signature = st.checkbox("Add Signature Stamp")
            sig_page = 1
            sig_bytes = None
            
            if enable_signature:
                sig_method = st.radio("Signature Input Method", ["Draw with Mouse / Touch", "Upload PNG Image"])
                sig_page = st.number_input("Page Number for Signature", min_value=1, max_value=total_pages, value=1)
                sig_x = st.number_input("Signature X Position", value=100)
                sig_y = st.number_input("Signature Y Position", value=700)
                sig_w = st.number_input("Signature Width", value=200)
                sig_h = st.number_input("Signature Height", value=80)

                if sig_method == "Draw with Mouse / Touch":
                    st.write("Draw your signature below:")
                    if CANVAS_AVAILABLE:
                        canvas_result = st_canvas(
                            fill_color="rgba(255, 255, 255, 0)",
                            stroke_width=2,
                            stroke_color="#000000",
                            background_color="#FFFFFF",
                            height=150,
                            width=300,
                            drawing_mode="freedraw",
                            key="canvas_signature",
                        )
                        if canvas_result.image_data is not None:
                            img_array = canvas_result.image_data.astype(np.uint8)
                            sig_img = PILImage.fromarray(img_array)
                            sig_img = sig_img.convert("RGBA")
                            data = sig_img.getdata()
                            new_data = []
                            for item in data:
                                # Strip white background to make signature transparent
                                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                                    new_data.append((255, 255, 255, 0))
                                else:
                                    new_data.append(item)
                            sig_img.putdata(new_data)
                            
                            buf = io.BytesIO()
                            sig_img.save(buf, format="PNG")
                            sig_bytes = buf.getvalue()
                    else:
                        st.error("Package `streamlit-drawable-canvas` is missing. Install via pip.")
                else:
                    sig_file = st.file_uploader("Upload Transparent Signature PNG", type=["png", "jpg"])
                    if sig_file is not None:
                        sig_bytes = sig_file.getvalue()

            st.subheader("5. Watermark & Borders")
            enable_watermark = st.checkbox("Add Watermark")
            wm_text = st.text_input("Watermark Text", value="CONFIDENTIAL") if enable_watermark else ""
            
            enable_border = st.checkbox("Add Page Border")
            border_inset = st.slider("Border Inset", 5, 40, 15) if enable_border else 15

            st.subheader("6. Scanned PDF OCR Search")
            enable_ocr = st.checkbox("Perform OCR on Scanned Pages", help="Uses Tesseract OCR if text search returns empty")

            st.subheader("7. Security & Privacy")
            strip_metadata = st.checkbox("Scrub Hidden Metadata (Author/Dates)", value=True)
            encrypt_pdf = st.checkbox("Password Protect Output PDF")
            output_password = st.text_input("Set Download Password", type="password") if encrypt_pdf else ""

            st.divider()
            save_clicked = st.button("💾 Save & Apply Changes", type="primary", use_container_width=True)

        if save_clicked:
            new_doc = pymupdf.open()
            for i in range(total_pages):
                page_num = i + 1
                if page_num in pages_to_delete:
                    continue
                page = doc[i]
                if rotate_angle > 0:
                    page.set_rotation((page.rotation + rotate_angle) % 360)
                new_doc.insert_pdf(doc, from_page=i, to_page=i)

            processed_total = len(new_doc)
            if processed_total > 0:
                for idx in range(processed_total):
                    page = new_doc[idx]
                    rect = page.rect

                    # OCR Check if enabled
                    if enable_ocr and OCR_AVAILABLE and not page.get_text().strip():
                        pix = page.get_pixmap(dpi=150)
                        img = PILImage.open(io.BytesIO(pix.tobytes("png")))
                        _ = pytesseract.image_to_string(img)
                    
                    # Text removal or replacement
                    if text_to_remove:
                        text_instances = page.search_for(text_to_remove)
                        for inst in text_instances:
                            if action_mode == "Blackout / Erase":
                                page.add_redact_annot(inst, fill=fill_rgb)
                            else:
                                page.add_redact_annot(inst, text=replacement_text)
                        page.apply_redactions()

                    if enable_area_erase:
                        page.add_redact_annot(pymupdf.Rect(x1, y1, x2, y2), fill=fill_rgb)
                        page.apply_redactions()

                    if enable_border:
                        b_rect = pymupdf.Rect(border_inset, border_inset, rect.width - border_inset, rect.height - border_inset)
                        shape = page.new_shape()
                        shape.draw_rect(b_rect)
                        shape.finish(color=(0,0,0), width=1.5)
                        shape.commit()

                    if enable_watermark and wm_text:
                        center_point = pymupdf.Point(rect.width / 2, rect.height / 2)
                        page.insert_text(center_point, wm_text, fontsize=45, color=(0.7, 0.7, 0.7), fill_opacity=0.3, morph=(center_point, pymupdf.Matrix(45)))

                    # Signature stamping on target page
                    if enable_signature and sig_bytes is not None and (idx + 1) == sig_page:
                        sig_rect = pymupdf.Rect(sig_x, sig_y, sig_x + sig_w, sig_y + sig_h)
                        page.insert_image(sig_rect, stream=sig_bytes, overlay=True)

            # Metadata Strip
            if strip_metadata:
                new_doc.set_metadata({})

            out_buffer = io.BytesIO()
            if encrypt_pdf and output_password:
                new_doc.save(out_buffer, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=output_password, owner_pw=output_password)
            else:
                new_doc.save(out_buffer, deflate=True, garbage=4)
            
            st.session_state["processed_pdf"] = out_buffer.getvalue()
            st.toast("✅ Changes saved securely!", icon="🎉")

        if "processed_pdf" in st.session_state:
            st.success("✅ Output ready for preview & download.")
            
            saved_doc = pymupdf.open(stream=st.session_state["processed_pdf"], filetype="pdf")
            if encrypt_pdf and output_password:
                saved_doc.authenticate(output_password)
                
            saved_total = len(saved_doc)

            tab_preview, tab_export, tab_text = st.tabs(["👁️ Preview", "💾 Download", "📝 Extracted Text"])
            with tab_preview:
                cols = st.columns(2)
                for idx in range(saved_total):
                    pix = saved_doc[idx].get_pixmap(dpi=100)
                    with cols[idx % 2]:
                        st.image(pix.tobytes("png"), caption=f"Page {idx + 1}", use_container_width=True)
            with tab_export:
                st.download_button("📥 Download Modified PDF", data=st.session_state["processed_pdf"], file_name="secured_document.pdf", mime="application/pdf")
            with tab_text:
                full_text = "".join([f"--- Page {i+1} ---\n{saved_doc[i].get_text()}\n" for i in range(saved_total)])
                st.text_area("Text Content", full_text, height=300)

# ==========================================
# TAB 2: MERGE / SPLIT (Extract Pages)
# ==========================================
with tab_merge_split:
    st.header("🔀 Multi-File Merge & Page Splitting")
    sub_tab1, sub_tab2 = st.tabs(["Merge Multiple PDFs", "Extract / Split Pages"])

    with sub_tab1:
        st.subheader("Combine Several PDFs into One")
        merge_files = st.file_uploader("Upload PDFs to Merge", type=["pdf"], accept_multiple_files=True, key="merge_uploader")
        if merge_files and st.button("Merge Files"):
            merged_doc = pymupdf.open()
            for f in merge_files:
                src_doc = pymupdf.open(stream=f.read(), filetype="pdf")
                merged_doc.insert_pdf(src_doc)
            merge_buffer = io.BytesIO()
            merged_doc.save(merge_buffer)
            st.download_button("📥 Download Merged PDF", data=merge_buffer.getvalue(), file_name="merged_document.pdf", mime="application/pdf")

    with sub_tab2:
        st.subheader("Extract Specific Pages into Standalone PDF")
        split_file = st.file_uploader("Upload PDF to Split", type=["pdf"], key="split_uploader")
        if split_file:
            s_doc = pymupdf.open(stream=split_file.read(), filetype="pdf")
            s_total = len(s_doc)
            selected_pages = st.multiselect("Select pages to export", options=list(range(1, s_total + 1)), default=[1])
            if selected_pages and st.button("Extract Selected Pages"):
                extracted_doc = pymupdf.open()
                for p in selected_pages:
                    extracted_doc.insert_pdf(s_doc, from_page=p-1, to_page=p-1)
                split_buffer = io.BytesIO()
                extracted_doc.save(split_buffer)
                st.download_button("📥 Download Extracted PDF", data=split_buffer.getvalue(), file_name="extracted_pages.pdf", mime="application/pdf")

# ==========================================
# TAB 3: IMAGE & FORM EXTRACTION
# ==========================================
with tab_assets:
    st.header("🖼️ Extract Embedded Images & Forms")
    asset_file = st.file_uploader("Upload PDF to extract images", type=["pdf"], key="asset_uploader")
    if asset_file:
        a_doc = pymupdf.open(stream=asset_file.read(), filetype="pdf")
        if st.button("Extract All Images"):
            img_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(img_zip_buffer, "w") as zf:
                img_count = 0
                for i, page in enumerate(a_doc):
                    for img_info in page.get_images(full=True):
                        xref = img_info[0]
                        base_image = a_doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        zf.writestr(f"page_{i+1}_img_{img_count}.{image_ext}", image_bytes)
                        img_count += 1
            st.success(f"Extracted {img_count} images successfully!")
            st.download_button("📥 Download Images ZIP", data=img_zip_buffer.getvalue(), file_name="extracted_images.zip", mime="application/zip")

# ==========================================
# TAB 4: ADMIN ACCESS MANAGEMENT
# ==========================================
with tab_admin:
    st.header("🛡️ Admin Control Panel")
    if is_primary_admin or st.session_state.get("admin_unlocked", False):
        st.success("🔓 Admin Access Granted")
        if not supabase:
            st.error("Database connection missing.")
        else:
            pending_res = supabase.table("users").select("*").eq("status", "pending").execute()
            if pending_res.data:
                st.subheader(f"⏳ Pending Requests ({len(pending_res.data)})")
                for u in pending_res.data:
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.write(f"**{u.get('username')}** ({u.get('email')})")
                    if c2.button("Approve", key=f"app_{u['id']}"):
                        supabase.table("users").update({"status": "approved"}).eq("id", u["id"]).execute()
                        st.rerun()
                    if c3.button("Reject", key=f"rej_{u['id']}"):
                        supabase.table("users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                        st.rerun()
            else:
                st.info("No pending access requests.")
    else:
        with st.form("admin_unlock"):
            pwd = st.text_input("Enter Admin Password", type="password")
            if st.form_submit_button("Unlock") and pwd == ADMIN_PASSWORD:
                st.session_state["admin_unlocked"] = True
                st.rerun()
