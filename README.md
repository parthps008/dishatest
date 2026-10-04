# Disha Academy - Online CBT Test Portal 🎓

A modern, scalable computer-based testing (CBT) portal built with **FastAPI (Python)**, **HTML5/CSS3/JavaScript**, and PDF parsing capabilities (`pdfplumber` & `pypdf`), designed with the official **Disha Academy** branding and visual identity.

---

## ✨ Key Features

### 🛡️ 1. Admin Management Dashboard (`/admin`)
- **PDF Question Paper Upload**: Upload any MCQ question paper PDF with questions, options `(A), (B), (C), (D)`, and optional answer keys.
- **Dynamic Time Limit Selector**: Set the exam duration dynamically using preset dropdown options (15, 30, 45, 60, 90, 120, 180 minutes) or input custom minutes.
- **Automatic Test Generation**:
  - Automatically extracts question text, options, and subject sections (e.g. Physics, Chemistry, Mathematics, Biology).
  - Automatically maps answer keys from inline answers or the answer sheet at the end.
- **Strict Single Active Test Policy**:
  - Exactly one test can be active at a time.
  - Active test is highlighted in the **Active Test Column** with title, subjects, duration, question count, and creation date.
  - One-click **Delete Test** button to remove the current test and immediately unlock uploading a new PDF.
- **Question Inspection Modal**: Inspect all parsed questions, options, and mapped correct answers before or during the exam.
- **Student Submissions Log**: Real-time table tracking candidate names, roll numbers, scores, percentages, attempt breakdown, and scorecard links.

### 📝 2. Student Examination Interface (`/test`)
- **Forward-Only Pagination (10 Questions Per Page)**:
  - Questions are organized 10 per page (e.g. Page 1: Q1–Q10, Page 2: Q11–Q20, Page 3: Q21–Q25).
  - **No Back Option**: In accordance with the exam policy, once a student clicks "Next Page", they cannot return to previous questions.
  - Browser back button prevention (`popstate` interception) and tab close warning (`beforeunload`).
  - Next Page confirmation modal warns candidates of unattempted questions before locking the page.
- **Dynamic Real-Time Countdown Timer**:
  - Synchronized with the admin's configured duration.
  - Turns amber at 5 minutes remaining and red with pulse animation at 1 minute remaining.
  - **Auto-Submission on Timeout**: If the countdown hits `00:00`, the test automatically submits student answers and redirects to their results.
- **Anti-Cheating Sanitization**: Correct answers and explanations are stripped from client-side APIs during the examination.

### 📊 3. Official Result & Scorecard (`/result/{submission_id}`)
- Official Disha Academy institutional report card with logo and security watermark.
- **Candidate Profile**: Student name, roll number, test title, submission timestamp, and submission mode (Manual vs. Auto-submitted Timeout).
- **Performance Summary**: Total score, maximum marks, percentage, and performance grade badge.
- **Diagnostic Metrics**: Total questions, attempted, correct, incorrect, unattempted, and accuracy rate.
- **Subject-Wise Analysis**: Breakdown for Physics, Chemistry, Mathematics, etc.
- **Question-by-Question Review**:
  - Interactive filters: All, Correct, Incorrect, Unattempted.
  - Displays student's choice (green if correct, red if incorrect).
  - Highlights correct answer and displays solution explanations if present.
- **Print / PDF Export**: Formatted with print CSS for clean 1-click printing or PDF saving.

---

## 🚀 How to Run

1. **Start the Portal**:
   ```bash
   python run.py
   ```
2. **Access URLs**:
   - **Student Portal**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **Admin Dashboard**: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)

3. **Sample Test Included**:
   - A ready-to-test PDF is generated at `sample_tests/disha_academy_mock_test.pdf` (25 questions spanning Physics, Chemistry, and Mathematics).
   - In the Admin Dashboard, click **"Load Sample Test"** for 1-click instant demo.
