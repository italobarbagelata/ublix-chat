"""
Formatter Node - Response Formatting for Enhanced LangGraph Chat

The FormatterNode handles response formatting and optimization for different channels:
1. Platform-specific formatting (WhatsApp, Instagram, etc.)
2. Content optimization and validation
3. Link formatting and URL handling
4. Emoji and markdown processing
5. Length optimization for different platforms
6. Accessibility improvements

This node ensures responses are optimized for the target platform.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from langchain_core.messages import AIMessage

from ..state import (
    EnhancedState,
    add_error,
    ErrorSeverity
)


class FormatterNode:
    """
    Response formatting node that optimizes content for different platforms.
    
    Features:
    - Platform-specific formatting rules
    - Content length optimization
    - Link and URL formatting
    - Emoji and special character handling
    - Accessibility improvements
    - Content validation and sanitization
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Platform-specific limits and rules
        self.platform_config = {
            "whatsapp": {
                "max_message_length": 4096,
                "supports_markdown": True,
                "supports_emojis": True,
                "line_break": "\n",
                "bold_format": "*{}*",
                "italic_format": "_{}_",
                "link_format": "[{}]({})"
            },
            "instagram": {
                "max_message_length": 1000,
                "supports_markdown": False,
                "supports_emojis": True,
                "line_break": "\n",
                "bold_format": "**{}**",
                "italic_format": "*{}*",
                "link_format": "{} ({})"
            },
            "facebook": {
                "max_message_length": 2000,
                "supports_markdown": False,
                "supports_emojis": True,
                "line_break": "\n",
                "bold_format": "**{}**",
                "italic_format": "*{}*",
                "link_format": "{} - {}"
            },
            "default": {
                "max_message_length": 4000,
                "supports_markdown": True,
                "supports_emojis": True,
                "line_break": "\n",
                "bold_format": "**{}**",
                "italic_format": "*{}*",
                "link_format": "[{}]({})"
            }
        }
    
    def __call__(self, state: EnhancedState) -> EnhancedState:
        """
        Main formatting logic that processes the response for the target platform.
        
        Args:
            state: Current enhanced state
            
        Returns:
            EnhancedState: Updated state with formatted response
        """
        try:
            self.logger.info(f"{state['unique_id']} FormatterNode: Starting response formatting")
            
            # Get the last AI message
            messages = state["conversation"]["messages"]
            if not messages:
                self.logger.info("No messages to format")
                return state
            
            last_message = None
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    last_message = msg
                    break
            
            if not last_message or not hasattr(last_message, 'content'):
                self.logger.info("No AI message found to format")
                return state
            
            # Get platform configuration
            source = state["user"]["source"].lower()
            platform_config = self.platform_config.get(source, self.platform_config["default"])
            
            # Format the content
            original_content = last_message.content
            formatted_content = self._format_content(original_content, platform_config, state)
            
            # Update the message content
            last_message.content = formatted_content
            
            # Add formatting metadata
            if not hasattr(last_message, 'additional_kwargs'):
                last_message.additional_kwargs = {}
            
            last_message.additional_kwargs.update({
                "formatted_for": source,
                "original_length": len(original_content),
                "formatted_length": len(formatted_content),
                "formatting_applied": True,
                "formatter_version": "enhanced_v1"
            })
            
            self.logger.info(
                f"{state['unique_id']} FormatterNode: Formatted content for {source} "
                f"({len(original_content)} -> {len(formatted_content)} chars)"
            )
            
            return state
            
        except Exception as e:
            self.logger.error(f"{state['unique_id']} FormatterNode error: {str(e)}", exc_info=True)
            return add_error(state, e, "Response formatting", ErrorSeverity.LOW)
    
    def _format_content(self, content: str, config: Dict[str, Any], state: EnhancedState) -> str:
        """
        Format content according to platform-specific rules.
        
        Args:
            content: Original content to format
            config: Platform configuration
            state: Current state for context
            
        Returns:
            Formatted content
        """
        
        if not content:
            return content
        
        formatted = content
        
        # 1. Handle markdown formatting
        if config["supports_markdown"]:
            formatted = self._process_markdown(formatted, config)
        else:
            formatted = self._remove_markdown(formatted)
        
        # 2. Process links
        formatted = self._format_links(formatted, config)
        
        # 3. Handle emojis
        if not config["supports_emojis"]:
            formatted = self._remove_emojis(formatted)
        
        # 4. Optimize length
        max_length = config["max_message_length"]
        if len(formatted) > max_length:
            formatted = self._truncate_content(formatted, max_length)
        
        # 5. Clean up formatting
        formatted = self._clean_formatting(formatted, config)
        
        return formatted
    
    def _process_markdown(self, content: str, config: Dict[str, Any]) -> str:
        """Process markdown formatting according to platform rules."""
        
        # Convert standard markdown to platform-specific format
        bold_format = config.get("bold_format", "**{}**")
        italic_format = config.get("italic_format", "*{}*")
        
        # Handle bold text
        content = re.sub(r'\*\*(.*?)\*\*', bold_format.format(r'\1'), content)
        
        # Handle italic text (but avoid conflicts with bold)
        content = re.sub(r'(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)', italic_format.format(r'\1'), content)
        
        return content
    
    def _remove_markdown(self, content: str) -> str:
        """Remove markdown formatting for platforms that don't support it."""
        
        # Remove bold formatting
        content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
        
        # Remove italic formatting
        content = re.sub(r'\*(.*?)\*', r'\1', content)
        
        # Remove code blocks
        content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        content = re.sub(r'`(.*?)`', r'\1', content)
        
        # Remove headers
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        
        return content
    
    def _format_links(self, content: str, config: Dict[str, Any]) -> str:
        """Format links according to platform rules."""
        
        link_format = config.get("link_format", "[{}]({})")
        
        # Find markdown links
        def replace_link(match):
            text = match.group(1)
            url = match.group(2)
            
            if "{}" in link_format:
                if link_format.count("{}") == 2:
                    return link_format.format(text, url)
                else:
                    return link_format.format(text)
            else:
                return f"{text} ({url})"
        
        # Replace markdown links
        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, content)
        
        return content
    
    def _remove_emojis(self, content: str) -> str:
        """Remove emojis for platforms that don't support them well."""
        
        # Basic emoji removal (simplified)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        
        return emoji_pattern.sub('', content)
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content intelligently while preserving formatting."""
        
        if len(content) <= max_length:
            return content
        
        # Try to truncate at sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', content)
        
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence) <= max_length - 20:  # Leave space for truncation indicator
                truncated += sentence + " "
            else:
                break
        
        if truncated:
            return truncated.strip() + "..."
        
        # If no good truncation point, just cut at character limit
        return content[:max_length - 3] + "..."
    
    def _clean_formatting(self, content: str, config: Dict[str, Any]) -> str:
        """Clean up any formatting issues."""
        
        # Remove excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        # Ensure proper line breaks for platform
        line_break = config.get("line_break", "\n")
        if line_break != "\n":
            content = content.replace("\n", line_break)
        
        # Remove leading/trailing whitespace
        content = content.strip()
        
        return content
    
    def get_formatting_stats(self) -> Dict[str, Any]:
        """Get formatting statistics for monitoring."""
        
        return {
            "supported_platforms": list(self.platform_config.keys()),
            "features": [
                "markdown_processing",
                "link_formatting", 
                "emoji_handling",
                "length_optimization",
                "platform_adaptation"
            ]
        }


def create_formatter_node() -> FormatterNode:
    """
    Factory function to create a FormatterNode instance.
    
    Returns:
        FormatterNode: Configured formatter node
    """
    return FormatterNode()