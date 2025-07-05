import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migrate template_id to form_id and remove template_id column.
    """
    if not version:
        return

    _logger.info("Starting migration of admission_candidate template_id to form_id")

    # Check if template_id column exists
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name='admission_candidate' 
            AND column_name='template_id'
        );
    """)
    has_template_id = cr.fetchone()[0]

    if has_template_id:
        # Copy data from template_id to form_id
        cr.execute("""
            UPDATE admission_candidate 
            SET form_id = template_id 
            WHERE template_id IS NOT NULL;
        """)
        
        # Drop NOT NULL constraint from template_id
        cr.execute("""
            ALTER TABLE admission_candidate 
            ALTER COLUMN template_id DROP NOT NULL;
        """)
        
        # Drop the template_id column
        cr.execute("""
            ALTER TABLE admission_candidate 
            DROP COLUMN template_id;
        """)
        
        _logger.info("Successfully migrated template_id to form_id and removed template_id column")

    # Ajout de la colonne default_token si elle n'existe pas
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'admission_form_template' 
                AND column_name = 'default_token'
            ) THEN
                ALTER TABLE admission_form_template 
                ADD COLUMN default_token varchar;
            END IF;
        END
        $$;
    """)

    # Ajout de la colonne is_default à la table admission_mapping_line
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'admission_mapping_line' 
                AND column_name = 'is_default'
            ) THEN
                ALTER TABLE admission_mapping_line 
                ADD COLUMN is_default boolean DEFAULT false;
            END IF;
        END
        $$;
    """) 