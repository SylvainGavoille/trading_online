import unittest
from unittest.mock import MagicMock
from src.trading.agents.response_parser import ResponseParser

class TestResponseParser(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.parser = ResponseParser()

    def test_parse_dict_response(self):
        """Test parsing dictionary response"""
        # Create mock response with dictionary content
        response = MagicMock()
        response.messages = [{"content": {"signal": "buy", "confidence": 0.8}}]
        
        result = self.parser.parse_response(response)
        
        self.assertEqual(result["signal"], "buy")
        self.assertEqual(result["confidence"], 0.8)

    def test_parse_json_string_response(self):
        """Test parsing JSON string response"""
        # Create mock response with JSON string content
        response = MagicMock()
        response.messages = [{"content": '{"signal": "sell", "confidence": 0.7}'}]
        
        result = self.parser.parse_response(response)
        
        self.assertEqual(result["signal"], "sell")
        self.assertEqual(result["confidence"], 0.7)

    def test_parse_markdown_json_response(self):
        """Test parsing JSON in markdown code block"""
        # Create mock response with markdown content
        response = MagicMock()
        response.messages = [{"content": '''Here's the analysis:
```json
{
    "signal": "hold",
    "confidence": 0.5
}
```
'''}]
        
        result = self.parser.parse_response(response)
        
        self.assertEqual(result["signal"], "hold")
        self.assertEqual(result["confidence"], 0.5)

    def test_parse_text_response(self):
        """Test parsing text-based response"""
        # Create mock response with text content containing risk parameters
        response = MagicMock()
        response.messages = [{"content": """
        Risk Analysis:
        approved: true
        position size: valid
        portfolio exposure: valid
        stop loss: valid
        risk/reward ratio: valid
        """}]
        
        result = self.parser.parse_response(response)
        
        self.assertTrue(result["approved"])
        self.assertEqual(result["risk_parameters"]["position_size_check"], "Valid")
        self.assertEqual(result["risk_parameters"]["portfolio_exposure_check"], "Valid")

    def test_parse_invalid_response(self):
        """Test parsing invalid response"""
        # Test None response
        result = self.parser.parse_response(None)
        self.assertEqual(result, {})
        
        # Test empty response
        response = MagicMock()
        response.messages = []
        result = self.parser.parse_response(response)
        self.assertEqual(result, {})
        
        # Test invalid JSON string
        response = MagicMock()
        response.messages = [{"content": "{invalid json}"}]
        result = self.parser.parse_response(response)
        self.assertIn("status", result)
        self.assertIn("message", result)

    def test_check_risk_approval_direct(self):
        """Test risk approval check with direct approval field"""
        risk_data = {
            "approved": True,
            "risk_parameters": {
                "position_size_check": "Valid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Approved"
            }
        }
        
        result = self.parser.check_risk_approval(risk_data)
        self.assertTrue(result)

    def test_check_risk_approval_nested(self):
        """Test risk approval check with nested content"""
        risk_data = {
            "content": {
                "approved": True,
                "risk_parameters": {
                    "position_size_check": "Valid",
                    "portfolio_exposure_check": "Valid",
                    "stop_loss_level_check": "Valid",
                    "risk_reward_ratio_check": "Valid",
                    "compliance": "Approved"
                }
            }
        }
        
        result = self.parser.check_risk_approval(risk_data)
        self.assertTrue(result)

    def test_check_risk_approval_invalid_parameters(self):
        """Test risk approval check with invalid parameters"""
        # Test with invalid check
        risk_data = {
            "approved": True,
            "risk_parameters": {
                "position_size_check": "Invalid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Approved"
            }
        }
        result = self.parser.check_risk_approval(risk_data)
        self.assertFalse(result)
        
        # Test with rejected compliance
        risk_data["risk_parameters"]["position_size_check"] = "Valid"
        risk_data["risk_parameters"]["compliance"] = "Rejected"
        result = self.parser.check_risk_approval(risk_data)
        self.assertFalse(result)

    def test_extract_parameter_status(self):
        """Test parameter status extraction from text"""
        content = """
        Analysis Results:
        Position size is valid
        Portfolio exposure is invalid
        Stop loss looks good
        Risk/reward ratio is problematic and invalid
        """
        
        # Test valid parameter
        result = self.parser._extract_parameter_status(content, "position size")
        self.assertEqual(result, "Valid")
        
        # Test invalid parameter
        result = self.parser._extract_parameter_status(content, "portfolio exposure")
        self.assertEqual(result, "Invalid")
        
        # Test parameter with no explicit invalid mention
        result = self.parser._extract_parameter_status(content, "stop loss")
        self.assertEqual(result, "Valid")
        
        # Test parameter with invalid mention
        result = self.parser._extract_parameter_status(content, "risk.?reward")
        self.assertEqual(result, "Invalid")

if __name__ == '__main__':
    unittest.main()
