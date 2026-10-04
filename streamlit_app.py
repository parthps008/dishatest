import os
import time
import json
from datetime import datetime
import streamlit as st

from app.test_manager import TestManager
from app.pdf_parser import parse_pdf_test
from app.auth import ADMIN_USERNAME, ADMIN_PASSWORD
from app.models import TestSubmissionRequest

# Configure Streamlit Page
st.set_page_config(
    page_title="Disha Academy - Online Test Portal",
    page_icon="static/images/logo.png" if os.path.exists("static/images/logo.png") else "🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for Disha Academy Branding
st.markdown("""
<style>
    /* Primary Colors & Typography */
    :root {
        --primary-navy: #0d2240;
        --accent-maroon: #8b1e2d;
        --accent-gold: #f59e0b;
    }
    
    .main-header {
        display: flex;
        align-items: center;
        gap: 1.25rem;
        background: #ffffff;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        border-bottom: 3px solid #8b1e2d;
        box-shadow: 0 4px 12px rgba(13, 34, 64, 0.08);
        margin-bottom: 1.5rem;
    }
    
    .brand-title {
        color: #8b1e2d;
        font-family: 'Outfit', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.1;
    }
    
    .brand-sub {
        color: #0d2240;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 1px;
        margin: 0;
    }
    
    /* CBT Question Card */
    .cbt-q-box {
        background: #ffffff;
        border-radius: 12px;
        border: 1.5px solid #e2e8f0;
        padding: 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    
    .q-meta-tag {
        background: #0d2240;
        color: #ffffff;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    
    /* Palette Grid */
    .palette-container {
        background: #ffffff;
        border: 1.5px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Session State Initialization -----------------
if "page" not in st.session_state:
    st.session_state.page = "home"
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "student_name" not in st.session_state:
    st.session_state.student_name = ""
if "student_roll" not in st.session_state:
    st.session_state.student_roll = ""
if "current_q_idx" not in st.session_state:
    st.session_state.current_q_idx = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "q_statuses" not in st.session_state:
    st.session_state.q_statuses = {}
if "exam_start_time" not in st.session_state:
    st.session_state.exam_start_time = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# Helper Navigation Function
def navigate_to(page_name):
    st.session_state.page = page_name
    st.rerun()

# ----------------- Top Header Banner -----------------
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if os.path.exists("static/images/logo.png"):
        st.image("static/images/logo.png", width=75)
    else:
        st.markdown("## 🎓")
with col_title:
    st.markdown("""
        <h2 style='color: #8b1e2d; margin-bottom: 2px; font-weight: 800;'>DISHA ACADEMY</h2>
        <p style='color: #0d2240; font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; margin: 0;'>
            EXCELLENCE IN JEE, NEET & FOUNDATION &bull; ONLINE CBT PORTAL
        </p>
    """, unsafe_allow_html=True)

st.divider()

# ----------------- Sidebar Navigation -----------------
with st.sidebar:
    st.markdown("### 🧭 Portal Navigation")
    
    if st.session_state.admin_logged_in:
        st.success(f"🛡️ Logged in as: **{ADMIN_USERNAME}**")
        col_ad1, col_ad2 = st.columns(2)
        with col_ad1:
            if st.button("⬅️ Admin Portal", use_container_width=True):
                navigate_to("admin")
        with col_ad2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.admin_logged_in = False
                st.info("Logged out safely.")
                navigate_to("home")
    else:
        if st.session_state.page != "admin_login":
            if st.button("🔐 Faculty / Admin Login", use_container_width=True):
                navigate_to("admin_login")

    st.markdown("---")
    if st.button("🏠 Student Home", use_container_width=True):
        navigate_to("home")

    active_test = TestManager.get_active_test_for_student()
    if active_test and st.session_state.page != "test":
        st.info(f"📝 **Active Test:** {active_test.get('title')}\n\n⏱️ Duration: {active_test.get('duration_minutes')} Mins")

# ==============================================================================
# PAGE 1: ADMIN LOGIN
# ==============================================================================
if st.session_state.page == "admin_login":
    st.subheader("🔐 Faculty & Admin Portal Authentication")
    st.caption("Authorized personnel only. Please sign in with your credentials to manage examinations.")
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("admin_login_form"):
            user_input = st.text_input("Admin User ID", placeholder="Enter Admin User ID")
            pass_input = st.text_input("Password", type="password", placeholder="Enter Password")
            submit_login = st.form_submit_button("Sign In to Admin Portal", use_container_width=True, type="primary")
            
            if submit_login:
                if user_input.strip() == ADMIN_USERNAME and pass_input.strip() == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("Authentication successful! Redirecting to Admin Dashboard...")
                    time.sleep(0.5)
                    navigate_to("admin")
                else:
                    st.error("Invalid Admin User ID or Password. Please check your credentials.")
        
        if st.button("⬅️ Return to Student Portal", use_container_width=True):
            navigate_to("home")

# ==============================================================================
# PAGE 2: ADMIN MANAGEMENT DASHBOARD
# ==============================================================================
elif st.session_state.page == "admin":
    if not st.session_state.admin_logged_in:
        st.warning("Admin access restricted. Please log in first.")
        navigate_to("admin_login")

    st.subheader("🛠️ Admin & Test Management Console")
    
    # Return button for Admin navigation anywhere
    col_b1, col_b2 = st.columns([3, 1])
    with col_b2:
        if st.button("🎓 Student View (Test Mode)", use_container_width=True):
            navigate_to("home")

    # Overview Stats
    active_test = TestManager.get_active_test()
    submissions = TestManager.get_active_test_submissions()
    topper = submissions[0] if submissions else None
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Test Status", "ACTIVE" if active_test else "NONE")
    m2.metric("Total Questions", active_test.get("total_questions", 0) if active_test else 0)
    m3.metric("Submissions", len(submissions))
    m4.metric("Topper Score", f"{topper.get('score')}/{topper.get('max_score')}" if topper else "No Submissions")

    st.divider()

    # Active Test Column (Single Test Policy)
    st.markdown("### 📋 Active Test Column")
    if active_test:
        st.success(f"**Live Test:** {active_test.get('title')} | Duration: {active_test.get('duration_minutes')} Minutes | Questions: {active_test.get('total_questions')} MCQs")
        st.write(f"**Subjects:** {', '.join(active_test.get('subjects', ['General']))}")
        
        col_act1, col_act2, col_act3 = st.columns(3)
        with col_act1:
            with st.expander("👁️ Inspect Questions"):
                for q in active_test.get("questions", []):
                    st.markdown(f"**Q{q.get('q_no')}.** {q.get('text')}")
                    for opt in q.get("options", []):
                        is_corr = opt.get('key') == q.get('correct_answer')
                        st.write(f"- {'✅' if is_corr else '⚪'} **({opt.get('key')})** {opt.get('text')}")
                    st.caption(f"Subject: {q.get('subject')} | Correct: ({q.get('correct_answer')})")
                    st.write("---")
        with col_act2:
            if st.button("▶️ Test Exam As Student", use_container_width=True):
                st.session_state.student_name = "Faculty Tester"
                st.session_state.student_roll = "FAC-001"
                st.session_state.current_q_idx = 0
                st.session_state.user_answers = {}
                st.session_state.q_statuses = {}
                st.session_state.exam_start_time = time.time()
                navigate_to("test")
        with col_act3:
            if st.button("🗑️ Delete Test & Reset Submissions", type="primary", use_container_width=True):
                TestManager.delete_active_test()
                st.success("Active test and all student logs deleted successfully.")
                st.rerun()
    else:
        st.info("No active test currently published. Upload a question paper PDF below to generate a new test.")

    st.divider()

    # Upload PDF Section
    st.markdown("### 📤 Upload Question Paper PDF & Generate Test")
    if active_test:
        st.warning("⚠️ An active test is already live. The portal enforces **1 active test at a time**. Please delete the current test above before uploading another.")
    else:
        uploaded_pdf = st.file_uploader("Upload Question Paper PDF (supports MCQs with A, B, C, D options)", type=["pdf"])
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            duration_choice = st.selectbox(
                "Test Duration (Minutes)",
                [15, 30, 45, 60, 90, 120, 180],
                index=1
            )
        with col_u2:
            title_override = st.text_input("Test Title (Optional Override)", placeholder="Auto-detect from PDF if empty")

        if uploaded_pdf and st.button("⚡ Generate & Publish Test", type="primary"):
            temp_path = os.path.join("data", "uploads", uploaded_pdf.name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(uploaded_pdf.getbuffer())
            
            with st.spinner("Extracting questions and building MHT-CET test..."):
                try:
                    parsed = parse_pdf_test(temp_path, override_duration=duration_choice)
                    if title_override.strip():
                        parsed["title"] = title_override.strip()
                    TestManager.set_active_test(parsed)
                    st.success(f"Successfully generated test with {parsed['total_questions']} questions!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate test: {e}")

    st.divider()

    # Leaderboard & Student Submissions (Test-wise only)
    st.markdown("### 🏆 Active Test Leaderboard & Submissions")
    if submissions:
        data_rows = []
        for s in submissions:
            data_rows.append({
                "Rank": f"🥇 1st (Topper)" if s.get("rank") == 1 else f"#{s.get('rank')}",
                "Student Name": s.get("student_name"),
                "Roll No": s.get("roll_no"),
                "Score": f"{s.get('score')} / {s.get('max_score')}",
                "Percentage": f"{s.get('percentage')}%",
                "Correct": s.get("correct_count"),
                "Wrong": s.get("wrong_count"),
                "Submitted At": s.get("submitted_at")
            })
        st.dataframe(data_rows, use_container_width=True)
    else:
        st.caption("No student submissions recorded for this test yet.")

# ==============================================================================
# PAGE 3: STUDENT HOME / REGISTRATION
# ==============================================================================
elif st.session_state.page == "home":
    # If admin is browsing, show persistent Back to Admin Portal notice
    if st.session_state.admin_logged_in:
        col_n1, col_n2 = st.columns([3, 1])
        with col_n1:
            st.info("🛡️ You are currently viewing the **Student Portal as Administrator**.")
        with col_n2:
            if st.button("⬅️ Back to Admin Portal", type="primary", use_container_width=True):
                navigate_to("admin")

    st.markdown("""
        ### Welcome to Disha Academy Online Test Portal
        Computer Based Testing (CBT) portal for NEET, JEE & Foundation Examinations.
    """)

    active_test = TestManager.get_active_test_for_student()
    if active_test:
        with st.container():
            st.success(f"### 🟢 Assessment Ready: {active_test.get('title')}")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.markdown(f"⏱️ **Duration:** {active_test.get('duration_minutes')} Minutes")
            col_m2.markdown(f"🔢 **Total Questions:** {active_test.get('total_questions')} MCQs")
            col_m3.markdown(f"💻 **Mode:** MHT-CET Single Question CBT")

            st.markdown("#### 📜 Instructions:")
            st.markdown("""
            - **One Question at a Time:** Navigate using **Previous** and **Next** buttons.
            - **Question Palette:** View question status boxes below.
              - 🟩 **Green:** Answered
              - 🟥 **Red:** Skipped / Not Answered
              - ⬜ **Gray:** Not Visited
              - 🟪 **Purple:** Marked for Review
            - **Timer:** The test auto-submits when the timer reaches 00:00.
            """)

            with st.form("student_entry_form"):
                st.markdown("#### 👤 Candidate Details:")
                s_name = st.text_input("Student Full Name *", placeholder="e.g. Rahul Sharma")
                s_roll = st.text_input("Roll Number / Candidate ID", placeholder="e.g. DA-2026-101")
                consent = st.checkbox("I have read and understood all MHT-CET test instructions.", value=True)
                start_btn = st.form_submit_button("🚀 Begin Assessment Now", type="primary", use_container_width=True)

                if start_btn:
                    if not s_name.strip():
                        st.error("Please enter your full name to start the test.")
                    elif not consent:
                        st.error("Please agree to the instructions to proceed.")
                    else:
                        st.session_state.student_name = s_name.strip()
                        st.session_state.student_roll = s_roll.strip() if s_roll.strip() else "N/A"
                        st.session_state.current_q_idx = 0
                        st.session_state.user_answers = {}
                        st.session_state.q_statuses = {}
                        st.session_state.exam_start_time = time.time()
                        navigate_to("test")
    else:
        st.warning("⚠️ There is currently no active test published. Please check back later or contact your instructor.")

# ==============================================================================
# PAGE 4: MHT-CET CBT EXAMINATION INTERFACE
# ==============================================================================
elif st.session_state.page == "test":
    active_test = TestManager.get_active_test_for_student()
    if not active_test or not active_test.get("questions"):
        st.error("No active test questions found.")
        navigate_to("home")

    questions = active_test.get("questions", [])
    total_q = len(questions)
    current_idx = st.session_state.current_q_idx
    current_q = questions[current_idx]

    # Calculate Remaining Time
    duration_secs = active_test.get("duration_minutes", 30) * 60
    elapsed_secs = time.time() - st.session_state.exam_start_time if st.session_state.exam_start_time else 0
    remaining_secs = max(0, int(duration_secs - elapsed_secs))
    rem_mins = remaining_secs // 60
    rem_s = remaining_secs % 60

    # Auto-submit if time expired
    if remaining_secs <= 0 and st.session_state.exam_start_time:
        st.warning("⏰ Time expired! Submitting your test automatically...")
        # Auto submit logic
        sub_req = TestSubmissionRequest(
            test_id=active_test["id"],
            student_name=st.session_state.student_name or "Candidate",
            roll_no=st.session_state.student_roll or "N/A",
            answers=st.session_state.user_answers,
            time_taken_seconds=int(elapsed_secs),
            auto_submitted=True
        )
        res = TestManager.submit_test(sub_req)
        st.session_state.last_result = res
        navigate_to("result")

    # Top CBT Bar
    col_cand, col_title, col_timer = st.columns([2, 3, 2])
    with col_cand:
        st.markdown(f"👤 **{st.session_state.student_name}** (`{st.session_state.student_roll}`)")
    with col_title:
        st.markdown(f"📝 **{active_test.get('title')}**")
    with col_timer:
        timer_color = "red" if remaining_secs < 300 else "green"
        st.markdown(f"<h3 style='text-align: right; color: {timer_color}; margin: 0;'>⏱️ {rem_mins:02d}:{rem_s:02d}</h3>", unsafe_allow_html=True)
        if st.session_state.admin_logged_in:
            if st.button("⬅️ Admin Portal", key="btn_exam_back"):
                navigate_to("admin")

    st.divider()

    # Question Statement & Options (1 Question at a time)
    col_qmeta1, col_qmeta2 = st.columns([3, 1])
    with col_qmeta1:
        st.markdown(f"### Question {current_q.get('q_no')} of {total_q}")
    with col_qmeta2:
        st.markdown(f"<span class='q-meta-tag'>{current_q.get('subject', 'General')} &bull; +1.0 / -0.0</span>", unsafe_allow_html=True)

    st.markdown(f"<div style='font-size: 1.15rem; font-weight: 600; padding: 1rem; background: #f8fafc; border-radius: 8px; border-left: 4px solid #8b1e2d; margin-bottom: 1.5rem;'>{current_q.get('text')}</div>", unsafe_allow_html=True)

    # MCQ Radio Options
    curr_saved_ans = st.session_state.user_answers.get(str(current_q.get("id")), None)
    opt_labels = [f"({opt['key']}) {opt['text']}" for opt in current_q.get("options", [])]
    opt_keys = [opt['key'] for opt in current_q.get("options", [])]

    default_idx = None
    if curr_saved_ans in opt_keys:
        default_idx = opt_keys.index(curr_saved_ans)

    selected_option = st.radio(
        "Select your answer:",
        options=range(len(opt_labels)),
        format_func=lambda i: opt_labels[i],
        index=default_idx,
        key=f"radio_q_{current_idx}"
    )

    # Examination Action Buttons
    col_act1, col_act2, col_act3, col_act4, col_act5 = st.columns(5)
    
    with col_act1:
        if st.button("⬅️ Previous", disabled=(current_idx == 0), use_container_width=True):
            st.session_state.current_q_idx = max(0, current_idx - 1)
            st.rerun()

    with col_act2:
        if st.button("🧹 Clear", use_container_width=True):
            q_id_str = str(current_q.get("id"))
            if q_id_str in st.session_state.user_answers:
                del st.session_state.user_answers[q_id_str]
            st.session_state.q_statuses[current_idx] = "not_answered"
            st.rerun()

    with col_act3:
        if st.button("🟣 Mark Review", use_container_width=True):
            if selected_option is not None:
                st.session_state.user_answers[str(current_q.get("id"))] = opt_keys[selected_option]
            st.session_state.q_statuses[current_idx] = "review"
            if current_idx < total_q - 1:
                st.session_state.current_q_idx += 1
            st.rerun()

    with col_act4:
        if st.button("💾 Save & Next ➡️", type="primary", use_container_width=True):
            if selected_option is not None:
                st.session_state.user_answers[str(current_q.get("id"))] = opt_keys[selected_option]
                st.session_state.q_statuses[current_idx] = "answered"
            else:
                st.session_state.q_statuses[current_idx] = "not_answered"
            
            if current_idx < total_q - 1:
                st.session_state.current_q_idx += 1
            st.rerun()

    with col_act5:
        if st.button("🏁 Submit Test", type="secondary", use_container_width=True):
            sub_req = TestSubmissionRequest(
                test_id=active_test["id"],
                student_name=st.session_state.student_name or "Candidate",
                roll_no=st.session_state.student_roll or "N/A",
                answers=st.session_state.user_answers,
                time_taken_seconds=int(elapsed_secs),
                auto_submitted=False
            )
            res = TestManager.submit_test(sub_req)
            st.session_state.last_result = res
            navigate_to("result")

    st.divider()

    # MHT-CET Question Reference Palette (Below Question)
    st.markdown("#### 🧭 Question Reference Palette (Click any square to navigate):")
    st.caption("🟩 Green = Answered | 🟥 Red = Skipped / Not Answered | ⬜ Gray = Not Visited | 🟪 Purple = Marked for Review")

    # Render Palette in rows of 10
    cols_per_row = 10
    for row_start in range(0, total_q, cols_per_row):
        row_cols = st.columns(cols_per_row)
        for col_idx, q_num in enumerate(range(row_start, min(row_start + cols_per_row, total_q))):
            status = st.session_state.q_statuses.get(q_num, "not_visited")
            has_ans = str(questions[q_num].get("id")) in st.session_state.user_answers
            
            if has_ans and status != "review":
                prefix = "🟩"
            elif status == "review":
                prefix = "🟪"
            elif status == "not_answered":
                prefix = "🟥"
            else:
                prefix = "⬜"

            is_curr = (q_num == current_idx)
            btn_label = f"{prefix} {q_num + 1}{'📍' if is_curr else ''}"
            
            if row_cols[col_idx].button(btn_label, key=f"pal_btn_{q_num}", use_container_width=True):
                st.session_state.current_q_idx = q_num
                st.rerun()

# ==============================================================================
# PAGE 5: SCORECARD & RESULTS
# ==============================================================================
elif st.session_state.page == "result":
    res = st.session_state.last_result
    if not res:
        st.info("No recent test submission found.")
        navigate_to("home")

    # Top return buttons
    col_ret1, col_ret2 = st.columns([3, 1])
    with col_ret1:
        st.markdown("## 🎓 Disha Academy Examination Scorecard")
    with col_ret2:
        if st.session_state.admin_logged_in:
            if st.button("⬅️ Back to Admin Portal", type="primary", use_container_width=True):
                navigate_to("admin")
        else:
            if st.button("🏠 Home Page", use_container_width=True):
                navigate_to("home")

    st.success(f"Candidate: **{res.student_name}** | Roll No: `{res.roll_no}` | Submitted: {res.submitted_at}")

    # Score Highlights
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Final Score", f"{res.total_score} / {res.max_score}")
    sc2.metric("Percentage", f"{res.percentage}%")
    sc3.metric("Correct Answers", f"✅ {res.correct_count}")
    sc4.metric("Wrong Answers", f"❌ {res.wrong_count}")

    st.divider()

    # Detailed Review by Subject
    st.markdown("### 🔍 Detailed Question Review")
    for q_detail in res.questions:
        q_no = q_detail.get("q_no")
        text = q_detail.get("text")
        user_ans = q_detail.get("user_answer", "--")
        corr_ans = q_detail.get("correct_answer")
        is_corr = q_detail.get("is_correct")
        subj = q_detail.get("subject", "General")

        with st.expander(f"{'✅' if is_corr else ('⚪' if not user_ans or user_ans == '--' else '❌')} Q{q_no}. {text[:75]}... ({subj})"):
            st.markdown(f"**Question:** {text}")
            for opt in q_detail.get("options", []):
                key = opt.get("key")
                txt = opt.get("text")
                mark = ""
                if key == corr_ans:
                    mark = "✅ **(Correct Answer)**"
                if key == user_ans:
                    mark += " 👈 **(Your Choice)**"
                st.write(f"- **({key})** {txt} {mark}")
            
            st.caption(f"Your Response: **{user_ans or 'Unattempted'}** | Correct Answer: **{corr_ans}**")
