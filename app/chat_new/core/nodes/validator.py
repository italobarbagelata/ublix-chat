"""
Validator Node - Input Validation and Security for Enhanced LangGraph Chat

The ValidatorNode is responsible for:
1. Input validation and sanitization
2. Security checks (injection attacks, malicious content)
3. Rate limiting and abuse prevention
4. Content filtering and compliance
5. Context validation and consistency checks

This node acts as a security gateway before processing user input.
"""

import logging
import re
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from langchain_core.messages import HumanMessage, AIMessage

from ..state import (
    EnhancedState, 
    ErrorSeverity,
    add_error,
    update_conversation_state
)


class SecurityValidationError(Exception):
    """Raised when security validation fails"""
    pass


class RateLimitError(Exception):
    """Raised when rate limiting is triggered"""
    pass


class ValidatorNode:
    """
    Input validation and security node that ensures safe processing of user input.
    
    Features:
    - SQL injection detection
    - XSS attack prevention
    - Rate limiting per user
    - Content filtering
    - Input sanitization
    - Conversation consistency checks
    - Malicious pattern detection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(__name__)
        
        # Default configuration
        self.config = {
            "max_message_length": 5000,
            "max_messages_per_minute": 20,
            "max_messages_per_hour": 100,
            "enable_content_filtering": True,
            "enable_rate_limiting": True,
            "enable_security_checks": True,
            "blocked_patterns": [],
            "allowed_file_types": [".jpg", ".jpeg", ".png", ".pdf", ".txt"],
            "max_file_size_mb": 10
        }
        
        # Update with provided config
        if config:
            self.config.update(config)
        
        # Rate limiting storage (in production, use Redis or database)
        self.rate_limit_storage = defaultdict(list)
        
        # Security patterns
        self.security_patterns = {
            "sql_injection": [
                r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER)\b)",
                r"(--|\#|\/\*|\*\/)",
                r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
                r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)"
            ],
            "xss_injection": [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe[^>]*>",
                r"<object[^>]*>",
                r"<embed[^>]*>"
            ],
            "command_injection": [
                r"(\||\&\&|\|\|)",
                r"(\$\(|\`)",
                r"(curl|wget|nc|netcat)",
                r"(rm\s+-rf|del\s+/)",
                r"(cat\s+/etc/passwd|type\s+con)"
            ],
            "path_traversal": [
                r"(\.\./|\.\.\\)",
                r"(/etc/passwd|/etc/shadow)",
                r"(C:\\Windows\\System32)",
                r"(\.\./.*\.\./)"
            ]
        }
        
        # Malicious content patterns
        self.malicious_patterns = [
            r"\b(hack|exploit|payload|malware|virus)\b",
            r"\b(bypass|circumvent|override)\b.*\b(security|filter|protection)\b",
            r"\b(ddos|attack|penetration)\b.*\b(test|testing)\b"
        ]
        
        # Spam patterns
        self.spam_patterns = [
            r"(.)\1{10,}",  # Repeated characters
            r"\b(buy now|click here|limited time|act now)\b",
            r"(http://|https://){3,}",  # Multiple URLs
            r"\b\w+\b(\s+\b\w+\b){0,2}\s*[\!\?]{3,}"  # Excessive punctuation
        ]
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main validation logic that checks all aspects of user input and conversation state.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state (potentially with validation errors)
        """
        try:
            # CRÍTICO: Normalizar estado al inicio para prevenir warnings Pydantic
            from ..utils import normalize_state_messages
            state = normalize_state_messages(state)
            
            self.logger.info(f"{state['unique_id']} ValidatorNode: Starting input validation")
            
            # Get the last user message
            last_message = self._get_last_user_message(state)
            if not last_message:
                self.logger.info(f"{state['unique_id']} ValidatorNode: No user message to validate")
                return state
            
            # Step 1: Basic input validation
            state = self._validate_basic_input(state, last_message)
            
            # Step 2: Security validation
            if self.config["enable_security_checks"]:
                state = self._validate_security(state, last_message)
            
            # Step 3: Rate limiting check
            if self.config["enable_rate_limiting"]:
                state = self._check_rate_limits(state)
            
            # Step 4: Content filtering
            if self.config["enable_content_filtering"]:
                state = self._filter_content(state, last_message)
            
            # Step 5: Conversation consistency check
            state = self._validate_conversation_consistency(state)
            
            # Step 6: Context validation
            state = self._validate_context(state)
            
            self.logger.info(f"{state['unique_id']} ValidatorNode: Validation completed successfully")
            return state
            
        except SecurityValidationError as e:
            self.logger.warning(f"{state['unique_id']} Security validation failed: {str(e)}")
            return add_error(state, e, "Security validation", ErrorSeverity.HIGH)
            
        except RateLimitError as e:
            self.logger.warning(f"{state['unique_id']} Rate limit exceeded: {str(e)}")
            return add_error(state, e, "Rate limiting", ErrorSeverity.MEDIUM)
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} ValidatorNode error: {str(e)}", exc_info=True)
            return add_error(state, e, "Input validation", ErrorSeverity.MEDIUM)
    
    def _get_last_user_message(self, state: EnhancedState) -> Optional[str]:
        """Extract the last user message from the conversation."""
        messages = state["conversation"]["messages"]
        
        for message in reversed(messages):
            if isinstance(message, HumanMessage) and message.content:
                return message.content.strip()
        
        return None
    
    def _validate_basic_input(self, state: EnhancedState, message: str) -> EnhancedState:
        """
        Perform basic input validation checks.
        
        Args:
            state: Current enhanced state
            message: User message to validate
            
        Returns:
            EnhancedState: Updated state
        """
        
        # Check message length
        if len(message) > self.config["max_message_length"]:
            error = ValueError(f"Message too long: {len(message)} chars (max: {self.config['max_message_length']})")
            raise SecurityValidationError(str(error))
        
        # Check for null bytes (common in injection attacks)
        if "\x00" in message:
            raise SecurityValidationError("Null byte detected in message")
        
        # Check for excessively long words (possible buffer overflow attempts)
        words = message.split()
        max_word_length = 50
        for word in words:
            if len(word) > max_word_length:
                self.logger.warning(f"Suspiciously long word detected: {word[:20]}... ({len(word)} chars)")
        
        return state
    
    def _validate_security(self, state: EnhancedState, message: str) -> EnhancedState:
        """
        Perform security validation to detect injection attacks and malicious content.
        
        Args:
            state: Current enhanced state
            message: User message to validate
            
        Returns:
            EnhancedState: Updated state
        """
        
        message_lower = message.lower()
        
        # Check for injection patterns
        for attack_type, patterns in self.security_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE | re.MULTILINE):
                    self.logger.warning(f"Potential {attack_type} detected: {pattern}")
                    raise SecurityValidationError(f"Potential {attack_type} attack detected")
        
        # Check for malicious content patterns
        for pattern in self.malicious_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                self.logger.warning(f"Malicious content pattern detected: {pattern}")
                raise SecurityValidationError("Malicious content detected")
        
        # Check for excessive special characters (possible encoding attack)
        special_char_ratio = len(re.findall(r'[^\w\s]', message)) / len(message) if message else 0
        if special_char_ratio > 0.3:  # More than 30% special characters
            self.logger.warning(f"High special character ratio: {special_char_ratio:.2f}")
        
        return state
    
    def _check_rate_limits(self, state: EnhancedState) -> EnhancedState:
        """
        Check rate limits for the current user.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state
        """
        
        user_id = state["user"]["user_id"]
        now = datetime.now()
        
        # Clean old entries and add current timestamp
        user_timestamps = self.rate_limit_storage[user_id]
        
        # Remove timestamps older than 1 hour
        cutoff_time = now - timedelta(hours=1)
        user_timestamps[:] = [ts for ts in user_timestamps if ts > cutoff_time]
        
        # Add current timestamp
        user_timestamps.append(now)
        
        # Check hourly limit
        if len(user_timestamps) > self.config["max_messages_per_hour"]:
            raise RateLimitError(f"Hourly message limit exceeded ({self.config['max_messages_per_hour']})")
        
        # Check per-minute limit
        minute_cutoff = now - timedelta(minutes=1)
        recent_messages = [ts for ts in user_timestamps if ts > minute_cutoff]
        
        if len(recent_messages) > self.config["max_messages_per_minute"]:
            raise RateLimitError(f"Per-minute message limit exceeded ({self.config['max_messages_per_minute']})")
        
        return state
    
    def _filter_content(self, state: EnhancedState, message: str) -> EnhancedState:
        """
        Filter inappropriate content and spam.
        
        Args:
            state: Current enhanced state
            message: User message to filter
            
        Returns:
            EnhancedState: Updated state
        """
        
        message_lower = message.lower()
        
        # Check for spam patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                self.logger.warning(f"Potential spam detected: {pattern}")
                # Don't block, but flag for monitoring
                state["user"]["session_metadata"]["spam_detected"] = True
        
        # Check custom blocked patterns
        for pattern in self.config["blocked_patterns"]:
            if re.search(pattern, message_lower, re.IGNORECASE):
                raise SecurityValidationError(f"Blocked content pattern detected")
        
        return state
    
    def _validate_conversation_consistency(self, state: EnhancedState) -> EnhancedState:
        """
        Validate conversation flow consistency.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state
        """
        
        messages = state["conversation"]["messages"]
        
        # Check for conversation hijacking (sudden topic changes that might indicate attack)
        if len(messages) >= 4:
            # Simple heuristic: check if recent messages are dramatically different
            recent_user_messages = [
                msg.content for msg in messages[-4:] 
                if isinstance(msg, HumanMessage) and msg.content
            ]
            
            if len(recent_user_messages) >= 2:
                # Calculate similarity (very basic approach)
                similarity_score = self._calculate_message_similarity(
                    recent_user_messages[-2], 
                    recent_user_messages[-1]
                )
                
                if similarity_score < 0.1:  # Very different messages
                    self.logger.info(f"Potential topic change detected (similarity: {similarity_score:.2f})")
                    state["routing"]["context_needed"].append("topic_change_validation")
        
        return state
    
    def _validate_context(self, state: EnhancedState) -> EnhancedState:
        """
        Validate that the conversation context makes sense.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state
        """
        
        # Check for context manipulation attempts
        user_context = state["user"]
        
        # Validate user_id consistency
        previous_user_id = state["user"]["session_metadata"].get("previous_user_id")
        if previous_user_id and previous_user_id != user_context["user_id"]:
            self.logger.warning("User ID changed during conversation")
            raise SecurityValidationError("User context manipulation detected")
        
        # Store for next validation in user context metadata
        state["user"]["session_metadata"]["previous_user_id"] = user_context["user_id"]
        
        return state
    
    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """
        Calculate basic similarity between two messages.
        
        Args:
            msg1: First message
            msg2: Second message
            
        Returns:
            float: Similarity score (0.0 to 1.0)
        """
        
        # Simple word overlap calculation
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def get_validation_summary(self, state: EnhancedState) -> Dict[str, Any]:
        """
        Get a summary of validation status for monitoring.
        
        Args:
            state: Current enhanced state
            
        Returns:
            Dict with validation summary
        """
        
        user_id = state["user"]["user_id"]
        user_timestamps = self.rate_limit_storage.get(user_id, [])
        
        return {
            "user_id": user_id,
            "messages_last_hour": len(user_timestamps),
            "rate_limit_remaining": max(0, self.config["max_messages_per_hour"] - len(user_timestamps)),
            "security_flags": state["user"]["session_metadata"].get("spam_detected", False),
            "validation_errors": state["errors"]["error_count"],
            "last_validation": datetime.now().isoformat()
        }


def create_validator_node(config: Optional[Dict[str, Any]] = None) -> ValidatorNode:
    """
    Factory function to create a ValidatorNode instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        ValidatorNode: Configured validator node
    """
    return ValidatorNode(config)