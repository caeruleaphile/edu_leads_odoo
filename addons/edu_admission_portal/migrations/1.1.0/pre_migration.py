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

    """Supprime les tables des modèles non utilisés."""
    # Suppression de la table admission_custom_field
    cr.execute("""
        DROP TABLE IF EXISTS admission_custom_field CASCADE;
    """)
    
    # Suppression de la table admission_form_field
    cr.execute("""
        DROP TABLE IF EXISTS admission_form_field CASCADE;
    """)
    
    # Suppression des entrées dans ir_model_fields
    cr.execute("""
        DELETE FROM ir_model_fields 
        WHERE model IN ('admission.custom.field', 'admission.form.field');
    """)
    
    # Suppression des entrées dans ir_model
    cr.execute("""
        DELETE FROM ir_model 
        WHERE model IN ('admission.custom.field', 'admission.form.field');
    """)
    
    # Log de la migration
    cr.execute("""
        INSERT INTO ir_logging (create_date, create_uid, name, type, dbname, level, message, path, func, line)
        VALUES (NOW(), 1, 'edu_admission_portal', 'server', current_database(), 'info', 
                'Migration 1.1.0 : Suppression des modèles non utilisés', 
                'migrations/1.1.0/pre_migration.py', 'migrate', 1);
    """) 