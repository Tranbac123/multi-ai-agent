"""Threat detection and security monitoring."""

import re
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
import structlog

logger = structlog.get_logger(__name__)


class ThreatDetector:
    """Threat detection system."""
    
    def __init__(self):
        self.sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
            r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
            r'(\bUNION\s+SELECT\b)',
            r'(\bDROP\s+TABLE\b)',
            r'(\bDELETE\s+FROM\b)',
        ]
        
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
        ]
        
        self.failed_attempts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))
        self.suspicious_ips: Dict[str, int] = defaultdict(int)
    
    def detect_sql_injection(self, input_data: str) -> bool:
        """Detect SQL injection attempts."""
        input_lower = input_data.lower()
        for pattern in self.sql_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                logger.warning("SQL injection detected", input=input_data[:100])
                return True
        return False
    
    def detect_xss_attack(self, input_data: str) -> bool:
        """Detect XSS attack attempts."""
        for pattern in self.xss_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                logger.warning("XSS attack detected", input=input_data[:100])
                return True
        return False
    
    def detect_brute_force(self, ip_address: str, success: bool = False) -> bool:
        """Detect brute force attacks."""
        now = time.time()
        
        if success:
            # Reset failed attempts on success
            self.failed_attempts[ip_address].clear()
            return False
        
        # Record failed attempt
        self.failed_attempts[ip_address].append(now)
        
        # Check if too many recent failures
        recent_failures = [
            attempt for attempt in self.failed_attempts[ip_address]
            if now - attempt < 300  # 5 minutes
        ]
        
        if len(recent_failures) >= 5:
            logger.warning("Brute force attack detected", ip=ip_address)
            self.suspicious_ips[ip_address] += 1
            return True
        
        return False
    
    def detect_privilege_escalation(self, user_actions: List[Dict[str, Any]]) -> bool:
        """Detect privilege escalation attempts."""
        admin_actions = [
            action for action in user_actions
            if action.get("permission", "").startswith("admin:")
        ]
        
        if len(admin_actions) > 3:
            logger.warning("Potential privilege escalation", actions=len(admin_actions))
            return True
        
        return False
    
    def analyze_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze request for threats."""
        threats = []
        
        # Check input data
        for key, value in request_data.items():
            if isinstance(value, str):
                if self.detect_sql_injection(value):
                    threats.append("sql_injection")
                if self.detect_xss_attack(value):
                    threats.append("xss_attack")
        
        return {
            "threats_detected": threats,
            "risk_level": "high" if threats else "low",
            "timestamp": time.time()
        }


# Global threat detector
threat_detector = ThreatDetector()


# Convenience functions
def detect_sql_injection(input_data: str) -> bool:
    """Detect SQL injection."""
    return threat_detector.detect_sql_injection(input_data)


def detect_xss_attack(input_data: str) -> bool:
    """Detect XSS attack."""
    return threat_detector.detect_xss_attack(input_data)


def detect_brute_force(ip_address: str, success: bool = False) -> bool:
    """Detect brute force."""
    return threat_detector.detect_brute_force(ip_address, success)


def detect_privilege_escalation(user_actions: List[Dict[str, Any]]) -> bool:
    """Detect privilege escalation."""
    return threat_detector.detect_privilege_escalation(user_actions)
