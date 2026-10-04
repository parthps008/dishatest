import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_java_test_pdf(output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor('#1e293b')
    )
    
    q_style = ParagraphStyle(
        'QStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=10,
        spaceAfter=6
    )

    opt_style = ParagraphStyle(
        'OptStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        leftIndent=15,
        spaceBefore=2
    )

    story = [
        Paragraph("Java Programming Assessment - Part 2", title_style),
        Spacer(1, 15)
    ]

    questions = [
        ("1. Which of the following is considered a marker interface in Java?",
         "a. java.io.Serializable", "b. java.lang.Runnable", "c. java.lang.Comparable", "d. java.util.concurrent.Callable"),
        ("2. What is the size of the char data type in Java?",
         "a. 8 bits", "b. 16 bits", "c. 32 bits", "d. 64 bits"),
        ("3. Which method is used to begin the execution of a thread?",
         "a. run()", "b. start()", "c. init()", "d. execute()"),
        ("4. Which block is always executed regardless of whether an exception is thrown or caught?",
         "a. try", "b. catch", "c. finally", "d. throw"),
        ("5. Which of the following is NOT a valid identifier (variable name) in Java?",
         "a. _myVariable", "b. $myVariable", "c. 123myVariable", "d. myVariable123"),
        ("6. Which class from the Java Collections Framework provides a resizable array implementation?",
         "a. ArrayList", "b. LinkedList", "c. HashSet", "d. TreeSet"),
        ("7. If no access modifier is specified for a class member, what is its default visibility?",
         "a. public", "b. private", "c. protected", "d. package-private"),
        ("8. Which of the following is NOT an Object-Oriented Programming (OOP) principle?",
         "a. Polymorphism", "b. Inheritance", "c. Compilation", "d. Encapsulation"),
        ("9. Which design pattern restricts the instantiation of a class to exactly one object?",
         "a. Factory", "b. Singleton", "c. Builder", "d. Observer"),
        ("10. Which keyword is used to allocate memory for a new object in Java?",
         "a. new", "b. malloc", "c. alloc", "d. create")
    ]

    for i, (q, a, b, c, d) in enumerate(questions):
        story.append(Paragraph(q, q_style))
        story.append(Paragraph(a, opt_style))
        story.append(Paragraph(b, opt_style))
        story.append(Paragraph(c, opt_style))
        story.append(Paragraph(d, opt_style))
        story.append(Spacer(1, 8))
        if i == 3 or i == 7:
            story.append(PageBreak())

    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>Answer Key</b>", ParagraphStyle('AKTitle', parent=styles['Heading2'], alignment=1)))
    story.append(Spacer(1, 8))

    table_data = [
        ["Q1", "Q2", "Q3", "Q4", "Q5"],
        ["a", "b", "b", "c", "c"],
        ["Q6", "Q7", "Q8", "Q9", "Q10"],
        ["a", "d", "c", "b", "a"]
    ]
    t = Table(table_data, colWidths=[60]*5)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0d2240')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#0d2240')),
        ('TEXTCOLOR', (0,2), (-1,2), colors.white),
    ]))
    story.append(t)

    doc.build(story)
    print(f"Created {output_path}")

if __name__ == "__main__":
    out_dir = "sample_tests"
    os.makedirs(out_dir, exist_ok=True)
    create_java_test_pdf(os.path.join(out_dir, "java_assessment_part2.pdf"))
