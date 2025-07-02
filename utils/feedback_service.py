from sqlalchemy.orm import Session
from typing import Dict, Any, List
import logging
from datetime import datetime

from models import ParsedDataFeedback, PostEditFeedback

# Set up logging
logger = logging.getLogger(__name__)

class FeedbackService:
    """Service for capturing and managing QA feedback"""
    
    @staticmethod
    def capture_parsed_data_feedback(
        db: Session,
        record_id: int,
        original_data: Dict[str, Any],
        edited_data: Dict[str, Any],
        prompt_version: str = "v1.0"
    ) -> int:
        """
        Capture feedback on parsed funding data edits
        
        Args:
            db: Database session
            record_id: ID of the funding opportunity record
            original_data: Original parsed data (JSON)
            edited_data: Edited data from QA
            prompt_version: Version of the parsing prompt used
            
        Returns:
            int: Number of feedback records created
        """
        feedback_count = 0
        
        try:
            # Compare each field and capture changes
            all_fields = set(original_data.keys()) | set(edited_data.keys())
            
            for field_name in all_fields:
                original_value = original_data.get(field_name)
                edited_value = edited_data.get(field_name)
                
                # Only capture if values are different
                if original_value != edited_value:
                    # Convert complex values to strings for storage
                    original_str = str(original_value) if original_value is not None else None
                    edited_str = str(edited_value) if edited_value is not None else None
                    
                    # Skip if both are None or empty
                    if not original_str and not edited_str:
                        continue
                    
                    feedback = ParsedDataFeedback(
                        record_id=record_id,
                        field_name=field_name,
                        original_value=original_str,
                        edited_value=edited_str,
                        prompt_version=prompt_version
                    )
                    
                    db.add(feedback)
                    feedback_count += 1
                    
                    logger.info(f"📝 Captured feedback for field '{field_name}' on record {record_id}")
            
            db.commit()
            logger.info(f"✅ Captured {feedback_count} feedback entries for record {record_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to capture parsed data feedback: {e}")
            db.rollback()
            raise
        
        return feedback_count
    
    @staticmethod
    def capture_post_edit_feedback(
        db: Session,
        record_id: int,
        original_sections: Dict[str, str],
        edited_sections: Dict[str, str],
        prompt_version: str = "v1.0"
    ) -> int:
        """
        Capture feedback on blog post generation edits
        
        Args:
            db: Database session
            record_id: ID of the funding opportunity record
            original_sections: Original generated sections
            edited_sections: Edited sections from QA
            prompt_version: Version of the generation prompt used
            
        Returns:
            int: Number of feedback records created
        """
        feedback_count = 0
        
        try:
            # Compare each section and capture changes
            all_sections = set(original_sections.keys()) | set(edited_sections.keys())
            
            for section in all_sections:
                original_text = original_sections.get(section, "")
                edited_text = edited_sections.get(section, "")
                
                # Only capture if texts are different and not empty
                if original_text != edited_text and (original_text or edited_text):
                    feedback = PostEditFeedback(
                        record_id=record_id,
                        section=section,
                        original_text=original_text if original_text else None,
                        edited_text=edited_text if edited_text else None,
                        prompt_version=prompt_version
                    )
                    
                    db.add(feedback)
                    feedback_count += 1
                    
                    logger.info(f"📝 Captured post edit feedback for section '{section}' on record {record_id}")
            
            db.commit()
            logger.info(f"✅ Captured {feedback_count} post edit feedback entries for record {record_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to capture post edit feedback: {e}")
            db.rollback()
            raise
        
        return feedback_count
    
    @staticmethod
    def get_field_feedback_summary(
        db: Session,
        field_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get feedback summary for a specific field to analyze patterns
        
        Args:
            db: Database session
            field_name: Name of the field to analyze
            limit: Maximum number of records to return
            
        Returns:
            List of feedback records for the field
        """
        try:
            feedback_records = db.query(ParsedDataFeedback).filter(
                ParsedDataFeedback.field_name == field_name
            ).order_by(ParsedDataFeedback.created_at.desc()).limit(limit).all()
            
            summary = []
            for record in feedback_records:
                summary.append({
                    "record_id": record.record_id,
                    "original_value": record.original_value,
                    "edited_value": record.edited_value,
                    "prompt_version": record.prompt_version,
                    "created_at": record.created_at.isoformat()
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to get field feedback summary: {e}")
            return []
    
    @staticmethod
    def get_post_section_feedback_summary(
        db: Session,
        section: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get feedback summary for a specific blog post section
        
        Args:
            db: Database session
            section: Name of the section to analyze
            limit: Maximum number of records to return
            
        Returns:
            List of feedback records for the section
        """
        try:
            feedback_records = db.query(PostEditFeedback).filter(
                PostEditFeedback.section == section
            ).order_by(PostEditFeedback.created_at.desc()).limit(limit).all()
            
            summary = []
            for record in feedback_records:
                summary.append({
                    "record_id": record.record_id,
                    "original_text": record.original_text,
                    "edited_text": record.edited_text,
                    "prompt_version": record.prompt_version,
                    "created_at": record.created_at.isoformat()
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to get post section feedback summary: {e}")
            return []
    
    @staticmethod
    def get_feedback_statistics(db: Session) -> Dict[str, Any]:
        """
        Get overall feedback statistics
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with feedback statistics
        """
        try:
            # Parsed data feedback stats
            parsed_feedback_count = db.query(ParsedDataFeedback).count()
            
            # Most edited fields
            most_edited_fields = db.query(
                ParsedDataFeedback.field_name,
                db.func.count(ParsedDataFeedback.id).label('edit_count')
            ).group_by(ParsedDataFeedback.field_name).order_by(
                db.func.count(ParsedDataFeedback.id).desc()
            ).limit(10).all()
            
            # Post edit feedback stats
            post_feedback_count = db.query(PostEditFeedback).count()
            
            # Most edited sections
            most_edited_sections = db.query(
                PostEditFeedback.section,
                db.func.count(PostEditFeedback.id).label('edit_count')
            ).group_by(PostEditFeedback.section).order_by(
                db.func.count(PostEditFeedback.id).desc()
            ).limit(10).all()
            
            return {
                "parsed_data_feedback": {
                    "total_edits": parsed_feedback_count,
                    "most_edited_fields": [
                        {"field": field, "edit_count": count} 
                        for field, count in most_edited_fields
                    ]
                },
                "post_edit_feedback": {
                    "total_edits": post_feedback_count,
                    "most_edited_sections": [
                        {"section": section, "edit_count": count}
                        for section, count in most_edited_sections
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get feedback statistics: {e}")
            return {
                "parsed_data_feedback": {"total_edits": 0, "most_edited_fields": []},
                "post_edit_feedback": {"total_edits": 0, "most_edited_sections": []}
            } 