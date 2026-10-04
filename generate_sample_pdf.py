import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_sample_pdf(output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1, # Center
        textColor=colors.HexColor('#0d2240')
    )
    
    sub_title_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor('#d99b26')
    )
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor('#444444')
    )

    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0d2240'),
        spaceBefore=12,
        spaceAfter=6
    )

    q_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=8,
        spaceAfter=4
    )

    opt_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#374151'),
        leftIndent=15,
        spaceAfter=3
    )

    story = []

    # Header
    story.append(Paragraph("DISHA ACADEMY - ALL INDIA ENTRANCE TEST", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("JEE / NEET FOUNDATION PRACTICE PAPER", sub_title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Time Allowed: 30 Minutes | Total Questions: 25 | Maximum Marks: 25", info_style))
    story.append(Spacer(1, 10))

    questions_data = [
        # SECTION 1: PHYSICS (1 to 8)
        ("PHYSICS", [
            ("1. The dimensional formula for Planck's constant is identical to that of:",
             "(A) Linear momentum", "(B) Angular momentum", "(C) Energy", "(D) Power"),
            ("2. A body falls freely from rest under gravity. The ratio of distances travelled in 1st, 2nd and 3rd second is:",
             "(A) 1 : 2 : 3", "(B) 1 : 3 : 5", "(C) 1 : 4 : 9", "(D) 1 : 1 : 1"),
            ("3. Which of the following is a scalar quantity?",
             "(A) Electric field", "(B) Magnetic flux", "(C) Acceleration", "(D) Torque"),
            ("4. A particle moves in a circle of radius 20 cm with constant angular velocity 10 rad/s. Its linear speed is:",
             "(A) 1 m/s", "(B) 2 m/s", "(C) 20 m/s", "(D) 0.5 m/s"),
            ("5. The escape velocity from the surface of Earth does not depend on:",
             "(A) Mass of the earth", "(B) Radius of the earth", "(C) Mass of the projectile", "(D) Gravitational constant"),
            ("6. In simple harmonic motion, the acceleration of the particle is zero when:",
             "(A) Velocity is zero", "(B) Displacement is maximum", "(C) Particle is at mean position", "(D) Potential energy is maximum"),
            ("7. Two wires of same material have lengths in ratio 1:2 and diameters in ratio 2:1. The ratio of their resistances is:",
             "(A) 1 : 8", "(B) 8 : 1", "(C) 1 : 4", "(D) 4 : 1"),
            ("8. SI unit of magnetic flux is:",
             "(A) Tesla", "(B) Weber", "(C) Henry", "(D) Gauss")
        ]),

        # SECTION 2: CHEMISTRY (9 to 16)
        ("CHEMISTRY", [
            ("9. The number of moles of solute present in 1 kg of solvent is called:",
             "(A) Molarity", "(B) Molality", "(C) Normality", "(D) Mole fraction"),
            ("10. Which of the following quantum numbers determines the shape of an orbital?",
             "(A) Principal", "(B) Azimuthal", "(C) Magnetic", "(D) Spin"),
            ("11. Which among the following elements has highest electron affinity?",
             "(A) Fluorine", "(B) Chlorine", "(C) Bromine", "(D) Iodine"),
            ("12. The hybridization of central carbon atom in methane (CH4) is:",
             "(A) sp", "(B) sp2", "(C) sp3", "(D) sp3d"),
            ("13. Which of the following is an amphoteric oxide?",
             "(A) Na2O", "(B) SO2", "(C) Al2O3", "(D) CaO"),
            ("14. Oxidation state of Manganese in KMnO4 is:",
             "(A) +2", "(B) +4", "(C) +6", "(D) +7"),
            ("15. The gas responsible for greenhouse effect in largest proportion is:",
             "(A) Methane", "(B) Carbon dioxide", "(C) Ozone", "(D) Nitrous oxide"),
            ("16. PH of a neutral aqueous solution at 25 degrees Celsius is:",
             "(A) 0", "(B) 7", "(C) 14", "(D) 1")
        ]),

        # SECTION 3: MATHEMATICS (17 to 25)
        ("MATHEMATICS", [
            ("17. If matrix A is orthogonal, then determinant of A is equal to:",
             "(A) 0", "(B) +1 or -1", "(C) 2", "(D) Any real number"),
            ("18. The value of limit x->0 of (sin x / x) is equal to:",
             "(A) 0", "(B) 1", "(C) Infinity", "(D) Does not exist"),
            ("19. Derivative of e^(2x) with respect to x is:",
             "(A) e^(2x)", "(B) 2 * e^(2x)", "(C) 2x * e^(2x)", "(D) e^(2x) / 2"),
            ("20. The roots of equation x^2 - 5x + 6 = 0 are:",
             "(A) 2 and 3", "(B) -2 and -3", "(C) 1 and 6", "(D) -1 and -6"),
            ("21. The value of sin(90 - theta) is equal to:",
             "(A) sin theta", "(B) cos theta", "(C) -cos theta", "(D) tan theta"),
            ("22. The sum of the first 10 natural numbers (1 + 2 + ... + 10) is:",
             "(A) 45", "(B) 50", "(C) 55", "(D) 60"),
            ("23. The distance between points (0,0) and (3,4) is:",
             "(A) 3", "(B) 4", "(C) 5", "(D) 7"),
            ("24. The area of a circle with radius 7 cm (take pi = 22/7) is:",
             "(A) 154 cm^2", "(B) 44 cm^2", "(C) 88 cm^2", "(D) 308 cm^2"),
            ("25. If log10(x) = 2, then x is equal to:",
             "(A) 20", "(B) 100", "(C) 2", "(D) 1000")
        ])
    ]

    for section_name, q_list in questions_data:
        story.append(Paragraph(f"SECTION: {section_name}", section_style))
        for q_text, opt_a, opt_b, opt_c, opt_d in q_list:
            story.append(Paragraph(q_text, q_style))
            # Options in 2x2 grid or inline
            story.append(Paragraph(f"{opt_a} &nbsp;&nbsp;&nbsp;&nbsp; {opt_b}", opt_style))
            story.append(Paragraph(f"{opt_c} &nbsp;&nbsp;&nbsp;&nbsp; {opt_d}", opt_style))
            story.append(Spacer(1, 4))

    # Answer Key section
    story.append(Spacer(1, 14))
    story.append(Paragraph("ANSWER KEY", section_style))
    story.append(Paragraph("1. B &nbsp;&nbsp; 2. B &nbsp;&nbsp; 3. B &nbsp;&nbsp; 4. B &nbsp;&nbsp; 5. C &nbsp;&nbsp; 6. C &nbsp;&nbsp; 7. A &nbsp;&nbsp; 8. B", opt_style))
    story.append(Paragraph("9. B &nbsp;&nbsp; 10. B &nbsp;&nbsp; 11. B &nbsp;&nbsp; 12. C &nbsp;&nbsp; 13. C &nbsp;&nbsp; 14. D &nbsp;&nbsp; 15. B &nbsp;&nbsp; 16. B", opt_style))
    story.append(Paragraph("17. B &nbsp;&nbsp; 18. B &nbsp;&nbsp; 19. B &nbsp;&nbsp; 20. A &nbsp;&nbsp; 21. B &nbsp;&nbsp; 22. C &nbsp;&nbsp; 23. C &nbsp;&nbsp; 24. A &nbsp;&nbsp; 25. B", opt_style))

    doc.build(story)
    print(f"Sample PDF created at: {output_path}")

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "sample_tests")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "disha_academy_mock_test.pdf")
    generate_sample_pdf(out_file)
