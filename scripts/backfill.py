#!/usr/bin/env python3
"""
Backfill script for ReqAgent database migration and cleanup.
This script handles post-migration data backfill and normalization.
"""

import os
import sys
import logging
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db import get_db, engine
from models import Base, FundingOpportunity, ProposalTemplate, Document, Source, IngestionRun
from sqlalchemy.orm import Session
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BackfillService:
    """Service for handling post-migration data backfill"""
    
    def __init__(self):
        self.db = next(get_db())
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
    
    def backfill_proposal_template_hashes(self) -> Dict[str, Any]:
        """Backfill hash values for existing proposal templates"""
        logger.info("🔄 Backfilling proposal template hashes...")
        
        try:
            # Get all proposal templates without hashes
            templates = self.db.query(ProposalTemplate).filter(
                ProposalTemplate.hash.is_(None)
            ).all()
            
            updated_count = 0
            for template in templates:
                # Generate hash based on funding opportunity data
                opportunity = self.db.query(FundingOpportunity).filter(
                    FundingOpportunity.id == template.funding_opportunity_id
                ).first()
                
                if opportunity:
                    # Create hash from opportunity data + template metadata
                    hash_data = {
                        'opportunity_id': template.funding_opportunity_id,
                        'docx_path': template.docx_path,
                        'pdf_path': template.pdf_path,
                        'status': template.status.value if template.status else 'pending',
                        'created_at': template.created_at.isoformat() if template.created_at else ''
                    }
                    
                    hash_string = json.dumps(hash_data, sort_keys=True)
                    template.hash = hashlib.sha256(hash_string.encode()).hexdigest()
                    updated_count += 1
            
            self.db.commit()
            logger.info(f"✅ Updated {updated_count} proposal template hashes")
            
            return {
                "success": True,
                "updated_count": updated_count,
                "message": f"Successfully updated {updated_count} proposal template hashes"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error backfilling proposal template hashes: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to backfill proposal template hashes"
            }
    
    def normalize_variants_data(self) -> Dict[str, Any]:
        """Normalize any legacy variants data structure"""
        logger.info("🔄 Normalizing variants data...")
        
        try:
            # Get all funding opportunities with variants
            opportunities = self.db.query(FundingOpportunity).filter(
                FundingOpportunity.variants.isnot(None)
            ).all()
            
            normalized_count = 0
            for opportunity in opportunities:
                variants = opportunity.variants
                
                # Ensure variants is a list
                if not isinstance(variants, list):
                    opportunity.variants = []
                    normalized_count += 1
                    continue
                
                # Normalize each variant
                normalized_variants = []
                for variant in variants:
                    if isinstance(variant, dict):
                        # Ensure required fields exist
                        normalized_variant = {
                            'variant_title': variant.get('variant_title', 'Default Variant'),
                            'grant_min': variant.get('grant_min'),
                            'grant_max': variant.get('grant_max'),
                            'currency': variant.get('currency', 'GBP'),
                            'funding_type': variant.get('funding_type', 'grant'),
                            'is_primary': variant.get('is_primary', False)
                        }
                        normalized_variants.append(normalized_variant)
                    else:
                        # Skip invalid variants
                        logger.warning(f"⚠️ Skipping invalid variant in opportunity {opportunity.id}: {variant}")
                
                if opportunity.variants != normalized_variants:
                    opportunity.variants = normalized_variants
                    normalized_count += 1
            
            self.db.commit()
            logger.info(f"✅ Normalized {normalized_count} opportunities with variants")
            
            return {
                "success": True,
                "normalized_count": normalized_count,
                "message": f"Successfully normalized {normalized_count} opportunities with variants"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error normalizing variants data: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to normalize variants data"
            }
    
    def seed_default_sources(self) -> Dict[str, Any]:
        """Ensure default sources exist"""
        logger.info("🔄 Seeding default sources...")
        
        try:
            # Check if sources already exist
            existing_sources = self.db.query(Source).count()
            
            if existing_sources == 0:
                # Create default sources
                default_sources = [
                    {
                        'provider': 'grants.gov',
                        'type': 'api',
                        'domain': 'grants.gov',
                        'config': {'filters': {'status': 'open'}, 'rate_limit': 100},
                        'enabled': True
                    },
                    {
                        'provider': 'UK Government',
                        'type': 'crawler',
                        'domain': 'gov.uk',
                        'config': {},
                        'enabled': True
                    },
                    {
                        'provider': 'European Commission',
                        'type': 'crawler',
                        'domain': 'ec.europa.eu',
                        'config': {},
                        'enabled': True
                    }
                ]
                
                for source_data in default_sources:
                    source = Source(**source_data)
                    self.db.add(source)
                
                self.db.commit()
                logger.info(f"✅ Created {len(default_sources)} default sources")
                
                return {
                    "success": True,
                    "created_count": len(default_sources),
                    "message": f"Successfully created {len(default_sources)} default sources"
                }
            else:
                logger.info(f"✅ Sources already exist ({existing_sources} found)")
                return {
                    "success": True,
                    "created_count": 0,
                    "message": "Sources already exist, no action needed"
                }
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error seeding default sources: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to seed default sources"
            }
    
    def cleanup_orphaned_records(self) -> Dict[str, Any]:
        """Clean up orphaned records and fix referential integrity"""
        logger.info("🔄 Cleaning up orphaned records...")
        
        try:
            # Find orphaned proposal templates
            orphaned_templates = self.db.query(ProposalTemplate).outerjoin(
                FundingOpportunity, ProposalTemplate.funding_opportunity_id == FundingOpportunity.id
            ).filter(FundingOpportunity.id.is_(None)).all()
            
            # Find orphaned documents
            orphaned_documents = self.db.query(Document).outerjoin(
                FundingOpportunity, Document.funding_opportunity_id == FundingOpportunity.id
            ).filter(FundingOpportunity.id.is_(None)).all()
            
            # Find orphaned ingestion runs
            orphaned_runs = self.db.query(IngestionRun).outerjoin(
                Source, IngestionRun.source_id == Source.id
            ).filter(Source.id.is_(None)).all()
            
            # Delete orphaned records
            deleted_counts = {
                'templates': len(orphaned_templates),
                'documents': len(orphaned_documents),
                'runs': len(orphaned_runs)
            }
            
            for template in orphaned_templates:
                self.db.delete(template)
            
            for document in orphaned_documents:
                self.db.delete(document)
            
            for run in orphaned_runs:
                self.db.delete(run)
            
            self.db.commit()
            
            total_deleted = sum(deleted_counts.values())
            if total_deleted > 0:
                logger.info(f"✅ Cleaned up {total_deleted} orphaned records: {deleted_counts}")
            else:
                logger.info("✅ No orphaned records found")
            
            return {
                "success": True,
                "deleted_counts": deleted_counts,
                "total_deleted": total_deleted,
                "message": f"Successfully cleaned up {total_deleted} orphaned records"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error cleaning up orphaned records: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to cleanup orphaned records"
            }
    
    def run_full_backfill(self) -> Dict[str, Any]:
        """Run all backfill operations"""
        logger.info("🚀 Starting full backfill process...")
        
        results = {}
        
        # Run each backfill operation
        operations = [
            ('proposal_template_hashes', self.backfill_proposal_template_hashes),
            ('normalize_variants', self.normalize_variants_data),
            ('seed_sources', self.seed_default_sources),
            ('cleanup_orphaned', self.cleanup_orphaned_records)
        ]
        
        for name, operation in operations:
            logger.info(f"🔄 Running {name}...")
            try:
                result = operation()
                results[name] = result
                
                if result['success']:
                    logger.info(f"✅ {name} completed successfully")
                else:
                    logger.error(f"❌ {name} failed: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"❌ {name} failed with exception: {str(e)}")
                results[name] = {
                    "success": False,
                    "error": str(e),
                    "message": f"Operation failed with exception: {str(e)}"
                }
        
        # Summary
        successful_ops = sum(1 for r in results.values() if r.get('success', False))
        total_ops = len(operations)
        
        logger.info(f"🎯 Backfill complete: {successful_ops}/{total_ops} operations successful")
        
        return {
            "success": successful_ops == total_ops,
            "results": results,
            "summary": {
                "total_operations": total_ops,
                "successful_operations": successful_ops,
                "failed_operations": total_ops - successful_ops
            }
        }

def main():
    """Main entry point for the backfill script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ReqAgent Database Backfill Script')
    parser.add_argument('--operation', choices=['all', 'hashes', 'variants', 'sources', 'cleanup'], 
                       default='all', help='Specific operation to run')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
    
    try:
        with BackfillService() as service:
            if args.operation == 'all':
                result = service.run_full_backfill()
            elif args.operation == 'hashes':
                result = service.backfill_proposal_template_hashes()
            elif args.operation == 'variants':
                result = service.normalize_variants_data()
            elif args.operation == 'sources':
                result = service.seed_default_sources()
            elif args.operation == 'cleanup':
                result = service.cleanup_orphaned_records()
            else:
                logger.error(f"❌ Unknown operation: {args.operation}")
                sys.exit(1)
            
            if result['success']:
                logger.info("✅ Backfill completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ Backfill failed")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"❌ Fatal error during backfill: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

