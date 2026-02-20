import json
import re
from typing import Dict, Any, Optional

class ResponseParser:
    """Handles parsing and validation of agent responses"""
    
    @staticmethod
    def parse_response(response: Any) -> Dict[str, Any]:
        """
        Parse agent response and convert to dictionary
        
        Args:
            response: Raw response from agent
            
        Returns:
            Parsed response as dictionary
        """
        if not response or not hasattr(response, 'messages') or not response.messages:
            return {}
            
        content = response.messages[0].get("content", "")
        
        # Handle different response types
        if isinstance(content, dict):
            return content
            
        if isinstance(content, str):
            return ResponseParser._parse_string_content(content)
            
        return {}
    
    @staticmethod
    def _parse_string_content(content: str) -> Dict[str, Any]:
        """Parse string content into dictionary"""
        # Try parsing as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
        # Try extracting JSON from markdown code block
        json_data = ResponseParser._extract_json_from_markdown(content)
        if json_data:
            return json_data
            
        # Try parsing as text-based response
        return ResponseParser._parse_text_response(content)
    
    @staticmethod
    def _extract_json_from_markdown(content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from markdown code blocks"""
        if '```' in content:
            json_match = re.search(r'```(?:json)?\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1).strip())
                except json.JSONDecodeError:
                    pass
        return None
    
    @staticmethod
    def _parse_text_response(content: str) -> Dict[str, Any]:
        """Parse text-based response into structured format"""
        # Extract approval status
        approved_match = re.search(r'approved:\s*(true|false)', content, re.IGNORECASE)
        if not approved_match:
            return {"status": "processed", "message": str(content)}
            
        approved_value = approved_match.group(1).lower() == 'true'
        
        # Extract risk parameters
        risk_params = {
            "position_size_check": ResponseParser._extract_parameter_status(content, "position size"),
            "portfolio_exposure_check": ResponseParser._extract_parameter_status(content, "portfolio exposure"),
            "stop_loss_level_check": ResponseParser._extract_parameter_status(content, "stop loss"),
            "risk_reward_ratio_check": ResponseParser._extract_parameter_status(content, "risk.?reward"),
            "compliance": "Approved" if not re.search(r'rejected|not approved|cannot be approved', content, re.IGNORECASE) else "Rejected"
        }
        
        return {
            "approved": approved_value and all(v == "Valid" for k, v in risk_params.items() if k != "compliance") and risk_params["compliance"] == "Approved",
            "risk_parameters": risk_params,
            "reason": content
        }
    
    @staticmethod
    def _extract_parameter_status(content: str, param_name: str) -> str:
        """Extract status (Valid/Invalid) for a specific parameter"""
        return "Valid" if not re.search(
            f'{param_name}.*?invalid|invalid.*?{param_name}',
            content,
            re.IGNORECASE
        ) else "Invalid"
    
    @staticmethod
    def check_risk_approval(risk_data: Dict[str, Any]) -> bool:
        """
        Check if risk assessment was approved
        
        Args:
            risk_data: Parsed risk assessment data
            
        Returns:
            True if approved, False otherwise
        """
        if not isinstance(risk_data, dict):
            return False
            
        # Check in nested content structure
        if "content" in risk_data and isinstance(risk_data["content"], dict):
            risk_data = risk_data["content"]
            
        # Check approval status
        if "approved" not in risk_data:
            return False
            
        # Verify risk parameters if present
        if "risk_parameters" in risk_data:
            risk_params = risk_data["risk_parameters"]
            if isinstance(risk_params, dict):
                # Check for Invalid parameters
                has_invalid = any(
                    value == "Invalid"
                    for key, value in risk_params.items()
                    if isinstance(value, str) and key.endswith("_check")
                )
                # Check compliance status
                not_approved = risk_params.get("compliance") != "Approved"
                
                if has_invalid or not_approved:
                    return False
                    
        return bool(risk_data["approved"])
