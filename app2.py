import io
import secrets
import pymupdf
import streamlit as st
import bcrypt
import resend
from supabase import create_client, Client

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
ADMIN_PASSWORD = get_secret("resend", "admin_password", "AdminSecret123!") # Default fallback password
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

    # --- TAB 1: LOGIN ---
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
                            except Exception as e:
                                st.error("Password verification error. Please register again.")
                    else:
                        st.error("User not found.")

    # --- TAB 2: REQUEST ACCESS ---
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

                        except Exception as e:
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

st.title("📄 Advanced PDF Editor & Redactor")

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

# Create standard tabs visible to everyone
app_tabs = st.tabs(["📄 PDF Operations", "🛡️ Admin Access Management"])
tab_pdf = app_tabs[0]
tab_admin = app_tabs[1]

# ==========================================
# TAB 1: PDF OPERATIONS
# ==========================================
with tab_pdf:
    with st.sidebar:
        st.header("⚙️ Editor Controls")

    uploaded_file = st.file_uploader("Upload a PDF file to edit", type=["pdf"])

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        st.info(f"Loaded source PDF with **{total_pages}** page(s). Configure your options on the sidebar and click **Save & Apply Changes**.")

        # --- SIDEBAR CONTROLS ---
        with st.sidebar:
            st.subheader("1. Page Operations")
            rotate_angle = st.selectbox("Rotate Pages", [0, 90, 180, 270])
            pages_to_delete = st.multiselect(
                "Remove Pages",
                options=list(range(1, total_pages + 1))
            )

            st.subheader("2. Target Text Removal")
            text_to_remove = st.text_input("Text Phrase to Erase", placeholder="e.g., Confidential")
            fill_color_choice = st.selectbox("Redaction Fill Color", ["White (Clean Erase)", "Black (Redact)"])
            fill_rgb = (1, 1, 1) if fill_color_choice.startswith("White") else (0, 0, 0)

            st.subheader("3. Coordinate-Based Area Removal")
            enable_area_erase = st.checkbox("Erase Custom Area Coordinates")
            if enable_area_erase:
                c1, c2 = st.columns(2)
                with c1:
                    x1 = st.number_input("Top-Left X", value=50, step=10)
                    y1 = st.number_input("Top-Left Y", value=50, step=10)
                with c2:
                    x2 = st.number_input("Bottom-Right X", value=200, step=10)
                    y2 = st.number_input("Bottom-Right Y", value=100, step=10)

            st.subheader("4. Border Removal & Drawing Options")
            remove_existing_border = st.checkbox("Erase Existing Outer Borders", help="Scrubs vector drawings along outer page edges")

            enable_border = st.checkbox("Add New Page Border")
            if enable_border:
                border_style = st.selectbox("Border Style", ["Solid Line", "Dashed Line", "Double Line Box"])
                border_color_name = st.selectbox("Border Color", ["Black", "Grey", "Blue", "Red", "Emerald Green"])
                border_width = st.slider("Thickness (px)", 1, 10, 2)
                border_inset = st.slider("Inset Padding (px)", 5, 50, 15)

                color_map = {
                    "Black": (0, 0, 0),
                    "Grey": (0.5, 0.5, 0.5),
                    "Blue": (0, 0.2, 0.8),
                    "Red": (0.8, 0, 0),
                    "Emerald Green": (0, 0.6, 0.3)
                }
                border_rgb = color_map[border_color_name]

            st.subheader("5. Watermark Settings")
            enable_watermark = st.checkbox("Add Watermark")
            wm_type = "Text"
            wm_text = ""
            wm_image_file = None
            wm_opacity = 0.3
            wm_angle = 45
            wm_fontsize = 40

            if enable_watermark:
                wm_type = st.radio("Watermark Type", ["Text", "Image"], horizontal=True)
                wm_opacity = st.slider("Watermark Opacity", 0.1, 1.0, 0.3, step=0.05)
                
                if wm_type == "Text":
                    wm_text = st.text_input("Watermark Text", value="CONFIDENTIAL")
                    wm_fontsize = st.slider("Font Size", 20, 100, 48)
                    wm_angle = st.selectbox("Rotation Angle", [0, 45, 90, 315], index=1)
                else:
                    wm_image_file = st.file_uploader("Upload Image Logo/Stamp", type=["png", "jpg", "jpeg"])

            st.subheader("6. Headers & Footers")
            footer_text = st.text_input("Custom Footer Text", placeholder="Confidential Document")
            add_page_numbers = st.checkbox("Add Page Numbers", value=True)

            st.subheader("7. Optimization")
            compress_pdf = st.checkbox("Compress Output File", value=True)

            st.divider()
            st.subheader("8. Save Operations")
            save_clicked = st.button("💾 Save & Apply Changes", type="primary", use_container_width=True)

        # --- SAVE PROCESSING LOGIC ---
        if save_clicked:
            new_doc = pymupdf.open()
            
            # Process page inclusions & rotations
            for i in range(total_pages):
                page_num = i + 1
                if page_num in pages_to_delete:
                    continue
                    
                page = doc[i]
                if rotate_angle > 0:
                    page.set_rotation((page.rotation + rotate_angle) % 360)
                    
                new_doc.insert_pdf(doc, from_page=i, to_page=i)

            processed_total = len(new_doc)

            # Apply modifications to pages
            if processed_total > 0:
                for idx in range(processed_total):
                    page = new_doc[idx]
                    rect = page.rect
                    
                    # --- REMOVE EXISTING OUTSIDE BORDERS ---
                    if remove_existing_border:
                        margin_px = 25
                        outer_strips = [
                            pymupdf.Rect(0, 0, rect.width, margin_px),
                            pymupdf.Rect(0, rect.height - margin_px, rect.width, rect.height),
                            pymupdf.Rect(0, 0, margin_px, rect.height),
                            pymupdf.Rect(rect.width - margin_px, 0, rect.width, rect.height)
                        ]
                        for strip in outer_strips:
                            page.add_redact_annot(strip, fill=(1, 1, 1))
                        page.apply_redactions()

                    # --- TARGET TEXT REMOVAL ---
                    if text_to_remove:
                        text_instances = page.search_for(text_to_remove)
                        for inst in text_instances:
                            page.add_redact_annot(inst, fill=fill_rgb)
                        page.apply_redactions()

                    # --- COORDINATE-BASED AREA REMOVAL ---
                    if enable_area_erase:
                        erase_rect = pymupdf.Rect(x1, y1, x2, y2)
                        page.add_redact_annot(erase_rect, fill=fill_rgb)
                        page.apply_redactions()
                    
                    # --- PAGE BORDER SELECTOR ---
                    if enable_border:
                        border_rect = pymupdf.Rect(
                            border_inset,
                            border_inset,
                            rect.width - border_inset,
                            rect.height - border_inset
                        )
                        shape = page.new_shape()
                        
                        if border_style == "Solid Line":
                            shape.draw_rect(border_rect)
                            shape.finish(color=border_rgb, width=border_width)
                        elif border_style == "Dashed Line":
                            shape.draw_rect(border_rect)
                            shape.finish(color=border_rgb, width=border_width, dashes="[4 4] 0")
                        elif border_style == "Double Line Box":
                            shape.draw_rect(border_rect)
                            shape.finish(color=border_rgb, width=border_width)
                            
                            inner_rect = pymupdf.Rect(
                                border_inset + 4,
                                border_inset + 4,
                                rect.width - border_inset - 4,
                                rect.height - border_inset - 4
                            )
                            shape.draw_rect(inner_rect)
                            shape.finish(color=border_rgb, width=1)

                        shape.commit()

                    # --- WATERMARK OVERLAY ---
                    if enable_watermark:
                        center_point = pymupdf.Point(rect.width / 2, rect.height / 2)
                        
                        if wm_type == "Text" and wm_text:
                            page.insert_text(
                                center_point,
                                wm_text,
                                fontsize=wm_fontsize,
                                color=(0.5, 0.5, 0.5),
                                fill_opacity=wm_opacity,
                                morph=(center_point, pymupdf.Matrix(wm_angle))
                            )
                        elif wm_type == "Image" and wm_image_file is not None:
                            img_bytes_wm = wm_image_file.getvalue()
                            wm_rect = pymupdf.Rect(
                                rect.width * 0.25,
                                rect.height * 0.35,
                                rect.width * 0.75,
                                rect.height * 0.65
                            )
                            page.insert_image(wm_rect, stream=img_bytes_wm, overlay=True)

                    # --- INSERT FOOTER TEXT ---
                    if footer_text:
                        page.insert_text(
                            pymupdf.Point(36, rect.height - 20),
                            footer_text,
                            fontsize=9,
                            color=(0.3, 0.3, 0.3)
                        )
                        
                    # --- INSERT PAGE NUMBER ---
                    if add_page_numbers:
                        pg_str = f"Page {idx + 1} of {processed_total}"
                        page.insert_text(
                            pymupdf.Point(rect.width - 100, rect.height - 20),
                            pg_str,
                            fontsize=9,
                            color=(0.3, 0.3, 0.3)
                        )

            # Store the resulting PDF in memory session
            out_buffer = io.BytesIO()
            if compress_pdf:
                new_doc.save(out_buffer, deflate=True, garbage=4)
            else:
                new_doc.save(out_buffer)
            
            st.session_state["processed_pdf"] = out_buffer.getvalue()
            st.session_state["processed_doc_pages"] = processed_total
            st.toast("✅ Changes saved successfully!", icon="🎉")

        # --- RENDER PREVIEW / EXPORT TABS ---
        if "processed_pdf" in st.session_state:
            st.success("✅ Showing saved output preview.")
            
            saved_doc = pymupdf.open(stream=st.session_state["processed_pdf"], filetype="pdf")
            saved_total = len(saved_doc)

            tab_preview, tab_export, tab_text = st.tabs(["👁️ Saved Preview", "💾 Download Saved File", "📝 Extract Saved Text"])

            with tab_preview:
                if saved_total == 0:
                    st.warning("All pages deleted.")
                else:
                    st.write(f"Previewing **{saved_total}** page(s):")
                    cols = st.columns(2)
                    for idx in range(saved_total):
                        page = saved_doc[idx]
                        pix = page.get_pixmap(dpi=100)
                        img_bytes = pix.tobytes("png")
                        with cols[idx % 2]:
                            st.image(img_bytes, caption=f"Page {idx + 1}", use_container_width=True)

            with tab_export:
                st.subheader("Download Modified PDF")
                if saved_total > 0:
                    st.download_button(
                        label="📥 Download Saved PDF",
                        data=st.session_state["processed_pdf"],
                        file_name="modified_document.pdf",
                        mime="application/pdf"
                    )

            with tab_text:
                st.subheader("Extract Text from Saved PDF")
                if saved_total > 0:
                    full_text = ""
                    for idx in range(saved_total):
                        full_text += f"--- Page {idx + 1} ---\n" + saved_doc[idx].get_text() + "\n\n"
                    st.text_area("Extracted Text", full_text, height=350)
        else:
            st.warning("👈 Configure settings in the sidebar and click **💾 Save & Apply Changes** to process and view your PDF.")

# ==========================================
# TAB 2: ADMIN ACCESS MANAGEMENT (PASSWORD LOCKED)
# ==========================================
with tab_admin:
    st.header("🛡️ Admin Access Control Panel")
    
    # Check if primary admin or password already unlocked in session
    if is_primary_admin or st.session_state.get("admin_unlocked", False):
        if is_primary_admin:
            st.success("👑 Logged in as Primary Administrator.")
        else:
            st.success("🔓 Admin mode unlocked via password.")
            if st.button("Lock Admin Dashboard"):
                st.session_state["admin_unlocked"] = False
                st.rerun()

        st.write("Approve pending registration requests or modify existing user access rights.")

        if not supabase:
            st.error("Database connection missing.")
        else:
            # Fetch pending requests
            pending_res = supabase.table("users").select("*").eq("status", "pending").execute()
            pending_users = pending_res.data if pending_res.data else []

            st.subheader(f"⏳ Pending Access Requests ({len(pending_users)})")
            if pending_users:
                for u in pending_users:
                    col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
                    with col1:
                        st.write(f"**Username:** {u.get('username')}")
                    with col2:
                        st.write(f"**Email:** {u.get('email')}")
                    with col3:
                        if st.button("✅ Approve", key=f"app_{u['id']}"):
                            supabase.table("users").update({"status": "approved"}).eq("id", u["id"]).execute()
                            st.success(f"Approved {u['username']}!")
                            st.rerun()
                    with col4:
                        if st.button("❌ Reject", key=f"rej_{u['id']}"):
                            supabase.table("users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                            st.warning(f"Rejected {u['username']}.")
                            st.rerun()
                    st.divider()
            else:
                st.info("No pending access requests at this moment.")

            st.divider()

            # Fetch all registered users
            all_res = supabase.table("users").select("id, username, email, status, created_at").neq("status", "pending").execute()
            all_users = all_res.data if all_res.data else []

            st.subheader(f"👥 Manage Registered Accounts ({len(all_users)})")
            if all_users:
                for u in all_users:
                    col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
                    with col1:
                        st.write(f"**{u.get('username')}**")
                    with col2:
                        st.write(f"{u.get('email')}")
                    with col3:
                        status = u.get("status")
                        st.write(f"Status: **{status.upper()}**")
                    with col4:
                        if status == "approved":
                            if st.button("Revoke Access", key=f"rev_{u['id']}"):
                                supabase.table("users").update({"status": "rejected"}).eq("id", u["id"]).execute()
                                st.rerun()
                        else:
                            if st.button("Re-Approve", key=f"reapp_{u['id']}"):
                                supabase.table("users").update({"status": "approved"}).eq("id", u["id"]).execute()
                                st.rerun()
    else:
        st.warning("🔒 This section is password protected for administrative use only.")
        with st.form("admin_unlock_form"):
            entered_password = st.text_input("Enter Admin Password", type="password")
            unlock_submitted = st.form_submit_button("Unlock Dashboard")
            
            if unlock_submitted:
                if entered_password == ADMIN_PASSWORD:
                    st.session_state["admin_unlocked"] = True
                    st.success("🔓 Access granted!")
                    st.rerun()
                else:
                    st.error("❌ Incorrect admin password.")
