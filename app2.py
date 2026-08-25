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
SUPABASE_URL = st.secrets.get("supabase", {}).get("url")
SUPABASE_KEY = st.secrets.get("supabase", {}).get("key")
RESEND_API_KEY = st.secrets.get("resend", {}).get("api_key")

# Admin target email updated to your email: tn1721c@gmail.com
ADMIN_EMAIL = st.secrets.get("resend", {}).get("admin_email", "tn1721c@gmail.com")
APP_URL = st.secrets.get("resend", {}).get("app_url", "http://localhost:8501")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


# Helper: Send Email Notification to Admin for Verification
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
    # Handle Admin Email Action Links (Approve / Reject via Token)
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
        with st.form("login_form"):
            login_user = st.text_input("Username or Email")
            login_pass = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Log In")

            if submit_login:
                if not supabase:
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
                            if bcrypt.checkpw(login_pass.encode("utf-8"), user_record["password_hash"].encode("utf-8")):
                                st.session_state["authenticated"] = True
                                st.session_state["user"] = user_record["username"]
                                st.rerun()
                            else:
                                st.error("Incorrect password.")
                    else:
                        st.error("User not found.")

    # --- TAB 2: REQUEST ACCESS ---
    with tab2:
        with st.form("request_form"):
            req_username = st.text_input("Preferred Username")
            req_email = st.text_input("Email Address")
            req_password = st.text_input("Set Password", type="password")
            submit_request = st.form_submit_button("Submit Access Request")

            if submit_request:
                if req_username and req_email and req_password:
                    if not supabase:
                        st.error("Database connection missing.")
                    else:
                        # Hash password & generate unique approval token securely
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

                            # Send Email Verification Alert to Admin (tn1721c@gmail.com)
                            if RESEND_API_KEY:
                                send_approval_request_email(req_username, req_email, token)
                                st.success("✅ Access request submitted! Verification email sent to the administrator.")
                            else:
                                st.warning("✅ Access request submitted, but Resend API Key is missing so no verification email was dispatched.")

                        except Exception as e:
                            st.error("User or Email already exists.")
                else:
                    st.warning("Please fill out all fields.")

    return False


if not auth_system():
    st.stop()

# ==========================================
# 📄 MAIN APP (Protected Content)
# ==========================================
st.title("📄 PDF Auto-Align, Border & Footer Editor")

with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.get('user', 'Member')}**")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.rerun()

# --- PDF Editor Logic Continues ---
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    st.info(f"Loaded PDF with **{total_pages}** pages.")
