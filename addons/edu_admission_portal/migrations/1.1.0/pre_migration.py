def migrate(cr, version):
    """Add field_mapping column if it doesn't exist."""
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'admission_form_template' 
                AND column_name = 'field_mapping'
            ) THEN
                ALTER TABLE admission_form_template 
                ADD COLUMN field_mapping text;
            END IF;
        END
        $$;
    """) 