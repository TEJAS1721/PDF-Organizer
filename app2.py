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

    resend.Emails.send({
        "from": "PDF App Auth <onboarding@resend.dev>",
        "to": ADMIN_EMAIL,
        "subject": f"Access Request from {username}",
        "html": content
    })


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
# 📄 MAIN APP (Protected PDF Editor Toolkit)
# ==========================================
st.title("📄 Advanced PDF Editor & Redactor")

with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.get('user', 'Member')}**")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Editor Controls")

uploaded_file = st.file_uploader("Upload a PDF file to edit", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.success(f"Loaded PDF with **{total_pages}** pages.")

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
        remove_existing_border = st.checkbox("Erase Existing Outer Borders", help="Scubs vector drawings along outer page edges")

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

        st.subheader("5. Headers & Footers")
        footer_text = st.text_input("Custom Footer Text", placeholder="Confidential Document")
        add_page_numbers = st.checkbox("Add Page Numbers", value=True)

        st.subheader("6. Optimization")
        compress_pdf = st.checkbox("Compress Output File", value=True)

    # --- EDITOR LOGIC ---
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

    # Apply operations
    if processed_total > 0:
        for idx in range(processed_total):
            page = new_doc[idx]
            rect = page.rect
            
            # --- REMOVE EXISTING OUTSIDE BORDERS ---
            if remove_existing_border:
                # Blank out outer edges (top, bottom, left, right margins)
                margin_px = 25
                outer_strips = [
                    pymupdf.Rect(0, 0, rect.width, margin_px),                        # Top edge
                    pymupdf.Rect(0, rect.height - margin_px, rect.width, rect.height),# Bottom edge
                    pymupdf.Rect(0, 0, margin_px, rect.height),                       # Left edge
                    pymupdf.Rect(rect.width - margin_px, 0, rect.width, rect.height) # Right edge
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
            
            # --- NEW PAGE BORDER SELECTOR ---
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

    # --- TABS INTERFACE ---
    tab_preview, tab_export, tab_text = st.tabs(["👁️ Live Preview", "💾 Export File", "📝 Extract Text"])

    with tab_preview:
        if processed_total == 0:
            st.warning("All pages deleted.")
        else:
            st.write(f"Previewing **{processed_total}** page(s):")
            cols = st.columns(2)
            for idx in range(processed_total):
                page = new_doc[idx]
                pix = page.get_pixmap(dpi=100)
                img_bytes = pix.tobytes("png")
                with cols[idx % 2]:
                    st.image(img_bytes, caption=f"Page {idx + 1}", use_container_width=True)

    with tab_export:
        st.subheader("Download Modified PDF")
        if processed_total > 0:
            out_buffer = io.BytesIO()
            if compress_pdf:
                new_doc.save(out_buffer, deflate=True, garbage=4)
            else:
                new_doc.save(out_buffer)
            
            st.download_button(
                label="📥 Download Processed PDF",
                data=out_buffer.getvalue(),
                file_name="modified_document.pdf",
                mime="application/pdf"
            )

    with tab_text:
        st.subheader("Extract Raw Text")
        if processed_total > 0:
            full_text = ""
            for idx in range(processed_total):
                full_text += f"--- Page {idx + 1} ---\n" + new_doc[idx].get_text() + "\n\n"
            st.text_area("Extracted Text", full_text, height=350)
