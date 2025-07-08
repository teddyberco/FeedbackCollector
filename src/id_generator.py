"""
Deterministic ID generation for feedback items
Ensures same content always gets same ID across sessions
"""

import hashlib
import re
from datetime import datetime

class FeedbackIDGenerator:
    """Generates consistent IDs based on feedback content"""
    
    @staticmethod
    def normalize_content(content):
        """Normalize content for consistent hashing"""
        if not content:
            return ""
        
        # Convert to lowercase
        content = content.lower()
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content.strip())
        
        # Remove common punctuation that might vary
        content = re.sub(r'[^\w\s]', '', content)
        
        return content
    
    @staticmethod
    def generate_feedback_id(title, content, source, author=None, created_date=None):
        """Generate deterministic feedback ID based on STABLE content only
        
        IMPORTANT: This function should only use stable, immutable content that won't change
        when we improve algorithms or processing. Do NOT use generated fields like:
        - Feedback_Gist (can change with algorithm improvements)
        - Processed/cleaned content that might change
        - Derived fields that might be recalculated
        
        Args:
            title: Original title or first part of feedback content (NOT generated gist)
            content: Raw feedback content
            source: Source platform/system
            author: Author/customer name
            created_date: Creation date
            
        Returns:
            Deterministic UUID-like string for the feedback
        """
        
        # Normalize all inputs
        norm_title = FeedbackIDGenerator.normalize_content(title or "")
        norm_content = FeedbackIDGenerator.normalize_content(content or "")
        norm_source = (source or "").lower()
        norm_author = (author or "").lower()
        
        # Create content hash components
        hash_components = [
            norm_title,
            norm_content[:500],  # First 500 chars to avoid huge content
            norm_source,
            norm_author
        ]
        
        # If we have a created date, use just the date part (not time)
        if created_date:
            if isinstance(created_date, str):
                try:
                    # Try to parse ISO format
                    date_obj = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    hash_components.append(date_obj.strftime('%Y-%m-%d'))
                except:
                    # If parsing fails, use first 10 chars (likely date)
                    hash_components.append(created_date[:10])
            elif hasattr(created_date, 'strftime'):
                hash_components.append(created_date.strftime('%Y-%m-%d'))
        
        # Combine all components
        combined = "|".join(filter(None, hash_components))
        
        # Generate SHA-256 hash
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()
        
        # Format as UUID-like string for compatibility
        formatted_id = f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
        
        return formatted_id
    
    @staticmethod
    def generate_id_from_feedback_dict(feedback):
        """Generate ID from feedback dictionary with proper field mapping
        
        IMPORTANT: Uses only stable, immutable content for ID generation.
        Do NOT use generated fields like Feedback_Gist as they can change with algorithm improvements.
        """
        # Map collector field names to ID generator field names
        # CRITICAL: Do NOT use Feedback_Gist for ID generation as it can change with algorithm improvements
        # Use original Title field if available, otherwise use first 100 chars of actual feedback content
        title = feedback.get('Title') or feedback.get('Feedback', '')[:100]  # Removed Feedback_Gist dependency
        
        # Use the actual feedback content, not processed versions
        content = feedback.get('Content') or feedback.get('Feedback') or ''
        
        # These should be stable
        source = feedback.get('Source') or feedback.get('Sources') or ''
        author = feedback.get('Author') or feedback.get('Customer') or ''
        created_date = feedback.get('Created_Date') or feedback.get('Created') or ''
        
        return FeedbackIDGenerator.generate_feedback_id(
            title=title,
            content=content,
            source=source,
            author=author,
            created_date=created_date
        )