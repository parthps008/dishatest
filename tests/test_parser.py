import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from app.pdf_parser import parse_pdf_test, extract_answer_keys

class TestPdfParser(unittest.TestCase):
    def test_user_pdf_mapping(self):
        user_pdf = r"C:\Users\ytvus\.gemini\antigravity\brain\67c6cb18-1ed1-469b-889f-9c700885f622\.user_uploaded\media_1791131333512.pdf"
        if not os.path.exists(user_pdf):
            user_pdf = os.path.join("sample_tests", "java_assessment_part2.pdf")
        
        parsed = parse_pdf_test(user_pdf)
        self.assertEqual(parsed["total_questions"], 10)
        
        expected_answers = {
            1: "A",
            2: "B",
            3: "B",
            4: "C",
            5: "C",
            6: "A",
            7: "D",
            8: "C",
            9: "B",
            10: "A"
        }
        
        for q in parsed["questions"]:
            q_no = q["q_no"]
            expected = expected_answers.get(q_no)
            self.assertEqual(
                q["correct_answer"], expected,
                f"Question {q_no} answer mismatch: got {q['correct_answer']}, expected {expected}"
            )
            self.assertTrue(q.get("answer_auto_detected"), f"Question {q_no} was not auto detected")
            self.assertEqual(len(q["options"]), 4)

    def test_mock_pdf_mapping(self):
        mock_pdf = os.path.join("sample_tests", "disha_academy_mock_test.pdf")
        if os.path.exists(mock_pdf):
            parsed = parse_pdf_test(mock_pdf)
            self.assertEqual(parsed["total_questions"], 25)
            self.assertEqual(parsed["questions"][0]["correct_answer"], "B")
            self.assertEqual(parsed["questions"][1]["correct_answer"], "B")
    def test_50_question_disha_pdf(self):
        pdf_50q = os.path.join("sample_tests", "disha_physics_50q.pdf")
        if not os.path.exists(pdf_50q):
            pdf_50q = r"C:\Users\ytvus\.gemini\antigravity\brain\67c6cb18-1ed1-469b-889f-9c700885f622\.user_uploaded\media_1791197222947.pdf"
        
        parsed = parse_pdf_test(pdf_50q)
        self.assertEqual(parsed["total_questions"], 50, f"Expected 50 questions, got {parsed['total_questions']}")
        
        # Verify sequential question numbers from 1 to 50
        q_numbers = [q["q_no"] for q in parsed["questions"]]
        self.assertEqual(q_numbers, list(range(1, 51)))
        
        # Verify each question has at least 2 options
        for q in parsed["questions"]:
            self.assertGreaterEqual(len(q["options"]), 2, f"Q{q['q_no']} has fewer than 2 options")

if __name__ == "__main__":
    unittest.main()
