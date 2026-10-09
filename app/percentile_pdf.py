import io
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page numbers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer line
        width, height = self._pagesize
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(36, 28, width - 36, 28)

        # Footer text
        left_text = "DISHA ACADEMY EVALUATION DIVISION • Official CBT Merit List & Percentile Record"
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 18, left_text)
        self.drawRightString(width - 36, 18, page_text)
        self.restoreState()


def generate_percentile_merit_list_pdf(
    test_data: Dict[str, Any],
    submissions: List[Dict[str, Any]]
) -> bytes:
    """
    Generates a professional, NTA/JEE-CET style Percentile Merit List PDF report
    for the active test and all student submissions.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0D2240'),
        alignment=1  # Center
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#9A3412'),
        alignment=1
    )

    meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1
    )

    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        alignment=1
    )

    td_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0D2240'),
        alignment=1
    )

    td_percentile = ParagraphStyle(
        'TableCellPercentile',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#047857'),
        alignment=1
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("DISHA ACADEMY", title_style))
    story.append(Paragraph("CANDIDATE PERCENTILE MERIT LIST & CBT ASSESSMENT REPORT", subtitle_style))
    story.append(Spacer(1, 6))

    # 2. Test & Meta Summary Block
    test_title = test_data.get("title", "Disha Academy Assessment")
    duration = test_data.get("duration_minutes", 30)
    total_q = test_data.get("total_questions", 0)
    total_candidates = len(submissions)

    # Topper & Stats calculation
    topper = submissions[0] if submissions else None
    topper_name = topper.get("student_name", "N/A") if topper else "N/A"
    topper_score = topper.get("score", 0) if topper else 0
    max_score = submissions[0].get("max_score", total_q) if submissions else total_q

    avg_score = round(sum(float(s.get("score", 0)) for s in submissions) / total_candidates, 2) if total_candidates > 0 else 0.0

    meta_data = [
        [
            Paragraph("<b>Test Name:</b>", meta_label), Paragraph(test_title, meta_val),
            Paragraph("<b>Total Candidates Appeared:</b>", meta_label), Paragraph(f"<b>{total_candidates}</b> Candidates", meta_val),
        ],
        [
            Paragraph("<b>Duration:</b>", meta_label), Paragraph(f"{duration} Minutes ({total_q} MCQs)", meta_val),
            Paragraph("<b>Batch Topper (100.00%ile):</b>", meta_label), Paragraph(f"{topper_name} ({topper_score}/{max_score} Marks)", meta_val),
        ],
        [
            Paragraph("<b>Report Generated:</b>", meta_label), Paragraph(datetime.now().strftime("%d %b %Y, %I:%M %p"), meta_val),
            Paragraph("<b>Batch Average Score:</b>", meta_label), Paragraph(f"{avg_score} / {max_score} Marks", meta_val),
        ]
    ]

    meta_table = Table(meta_data, colWidths=[110, 260, 150, 250])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Candidate Table
    headers = [
        Paragraph("Rank", th_style),
        Paragraph("Roll No", th_style),
        Paragraph("Candidate Name", th_style),
        Paragraph("Raw Score", th_style),
        Paragraph("Max", th_style),
        Paragraph("Percentage", th_style),
        Paragraph("Percentile Score (%ile)", th_style),
        Paragraph("Correct / Wrong / Blank", th_style),
        Paragraph("Time Taken", th_style),
        Paragraph("Submitted At", th_style),
    ]

    table_data = [headers]

    for s in submissions:
        rank_val = s.get("rank", "-")
        rank_str = f"#{rank_val}"
        if rank_val == 1:
            rank_str = "1st (Topper)"
        elif rank_val == 2:
            rank_str = "2nd"
        elif rank_val == 3:
            rank_str = "3rd"

        roll = s.get("roll_no") or "N/A"
        name = s.get("student_name") or "Candidate"
        score = f"{s.get('score', 0)}"
        max_s = f"{s.get('max_score', max_score)}"
        pct = f"{s.get('percentage', 0)}%"
        percentile_str = f"{s.get('percentile', 0.0):.2f}%ile"
        cwb = f"{s.get('correct_count', 0)} / {s.get('wrong_count', 0)} / {s.get('unattempted_count', 0)}"

        sec = s.get("time_taken_seconds")
        if sec is not None:
            time_str = f"{int(sec) // 60}m {int(sec) % 60}s"
        else:
            time_str = "--"

        sub_at = s.get("submitted_at") or "--"
        # Trim time if string has YYYY-MM-DD HH:MM:SS
        if len(sub_at) >= 16:
            sub_at = sub_at[:16]

        row = [
            Paragraph(rank_str, td_bold if rank_val == 1 else td_style),
            Paragraph(roll, td_style),
            Paragraph(f"<b>{name}</b>" if rank_val == 1 else name, td_bold if rank_val == 1 else td_style),
            Paragraph(score, td_bold),
            Paragraph(max_s, td_style),
            Paragraph(pct, td_style),
            Paragraph(f"<b>{percentile_str}</b>", td_percentile),
            Paragraph(cwb, td_style),
            Paragraph(time_str, td_style),
            Paragraph(sub_at, td_style),
        ]
        table_data.append(row)

    # Column widths (Total width ~ 770 pt)
    col_widths = [65, 65, 150, 50, 40, 60, 95, 100, 65, 75]
    res_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0D2240')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    # Alternating row colors + topper row highlight
    for i in range(1, len(table_data)):
        if i == 1 and topper:
            table_style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FEF3C7')))
        elif i % 2 == 0:
            table_style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8FAFC')))
        else:
            table_style_commands.append(('BACKGROUND', (0, i), (-1, i), colors.white))

    res_table.setStyle(TableStyle(table_style_commands))
    story.append(res_table)
    story.append(Spacer(1, 12))

    # 4. NTA/CET Percentile Methodology Formula Note
    formula_note = Paragraph(
        "<b>Note on NTA / MHT-CET Percentile Calculation:</b> Percentile Score = (100 &times; Number of candidates appeared in the session with raw score &le; Candidate's score) / (Total number of candidates appeared). The highest scorer receives 100.00 percentile. Ties are resolved and awarded equivalent percentile scores.",
        ParagraphStyle(
            'FormulaNote',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#64748B')
        )
    )
    story.append(formula_note)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
