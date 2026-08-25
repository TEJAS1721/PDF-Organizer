import io
import secrets
import pymupdf
import streamlit as st
import bcrypt
import resend
from supabase import create_client, Client

st.set_page_config(page_title="PDF Advanced Editor", page_icon="📄", layout="wide")

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
st.title("📄 Advanced PDF Editor & Organizer")

with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.get('user', 'Member')}**")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Editor Control Panel")

uploaded_file = st.file_uploader("Upload a PDF file to edit", type=["pdf"])

if uploaded_file is not None:
    # Read original bytes
    pdf_bytes = uploaded_file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    
    st.success(f"Successfully loaded PDF with **{total_pages}** pages.")

    # --- SIDEBAR CONTROLS ---
    with st.sidebar:
        st.subheader("1. Page Management")
        
        # Rotation
        rotate_angle = st.selectbox("Rotate All Pages", [0, 90, 180, 270], help="Select degrees to rotate all pages clockwise.")
        
        # Delete Pages
        pages_to_delete = st.multiselect(
            "Select Pages to Remove",
            options=list(range(1, total_pages + 1)),
            help="Choose page numbers to delete from the output."
        )

        st.subheader("2. Headers & Footers")
        footer_text = st.text_input("Custom Footer Text", placeholder="e.g., Confidential - Company Use Only")
        add_page_numbers = st.checkbox("Add Page Numbers (Page X of Y)", value=True)

        st.subheader("3. Compression & Optimization")
        compress_pdf = st.checkbox("Optimize & Compress Output", value=True)

    # --- EDITOR LOGIC ---
    # Create working copy of PDF
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

    # Apply Footers and Page Numbers
    if processed_total > 0:
        for idx in range(processed_total):
            page = new_doc[idx]
            rect = page.rect
            
            # Footer text placement
            if footer_text:
                page.insert_text(
                    pymupdf.Point(36, rect.height - 20),
                    footer_text,
                    fontsize=9,
                    color=(0.3, 0.3, 0.3)
                )
                
            # Page Number placement (bottom right)
            if add_page_numbers:
                pg_str = f"Page {idx + 1} of {processed_total}"
                page.insert_text(
                    pymupdf.Point(rect.width - 100, rect.height - 20),
                    pg_str,
                    fontsize=9,
                    color=(0.3, 0.3, 0.3)
                )

    # --- MAIN INTERFACE TABS ---
    tab_preview, tab_export, tab_text = st.tabs(["👁️ Live Preview", "💾 Export File", "📝 Extract Text"])

    # TAB 1: LIVE PREVIEW
    with tab_preview:
        if processed_total == 0:
            st.warning("All pages have been deleted. Please unselect pages to remove.")
        else:
            st.write(f"Displaying preview of **{processed_total}** page(s):")
            cols = st.columns(2)
            for idx in range(processed_total):
                page = new_doc[idx]
                pix = page.get_pixmap(dpi=100)
                img_bytes = pix.tobytes("png")
                
                with cols[idx % 2]:
                    st.image(img_bytes, caption=f"Page {idx + 1}", use_container_width=True)

    # TAB 2: EXPORT OPTIONS
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

            st.divider()
            st.subheader("Export Pages as PNG Images")
            selected_page_to_export = st.number_input("Select Page Number to Export as PNG", min_value=1, max_value=processed_total, value=1)
            
            if st.button("Generate Page Image"):
                export_page = new_doc[selected_page_to_export - 1]
                pix = export_page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                
                st.download_button(
                    label=f"📥 Download Page {selected_page_to_export} as PNG",
                    data=img_data,
                    file_name=f"page_{selected_page_to_export}.png",
                    mime="image/png"
                )

    # TAB 3: TEXT EXTRACTION
    with tab_text:
        st.subheader("Extract Raw Text Content")
        if processed_total > 0:
            full_text = ""
            for idx in range(processed_total):
                full_text += f"--- Page {idx + 1} ---\n" + new_doc[idx].get_text() + "\n\n"
                
            st.text_area("Extracted Document Text", full_text, height=350)
            
            st.download_button(
                label="📥 Download Text File (.txt)",
                data=full_text,
                file_name="extracted_text.txt",
                mime="text/plain"
            )
