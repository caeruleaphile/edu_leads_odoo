from . import models
from . import controllers

import os
import logging
from odoo import api, SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)

def pre_init_hook(env_or_cr, registry=None):
    """
    Pre-install script.
    Note: Can be called with either env or (cr, registry).
    """
    _logger.info('Running pre-init hook for edu_admission_portal')

def post_init_hook(env_or_cr, registry=None):
    """
    Post-install script.
    Note: Can be called with either env or (cr, registry).
    """
    # Handle both env and cr cases
    if isinstance(env_or_cr, Environment):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    
    # Ensure filestore directories exist
    filestore_path = env['ir.attachment']._filestore()
    session_path = os.path.join(os.path.dirname(filestore_path), 'sessions')
    
    try:
        # Create directories if they don't exist
        os.makedirs(filestore_path, exist_ok=True)
        os.makedirs(session_path, exist_ok=True)
        
        # Set proper permissions (only on Unix-like systems)
        if os.name == 'posix':
            os.system(f'chmod -R 777 {os.path.dirname(filestore_path)}')
        
        _logger.info('Filestore directories created and permissions set')
    except Exception as e:
        _logger.warning('Could not create filestore directories: %s', str(e))

def uninstall_hook(env_or_cr, registry=None):
    """Hook de désinstallation pour nettoyer la base de données."""
    # Détermine si on a reçu env ou cr
    if registry is None:
        # On a reçu env
        cr = env_or_cr.cr
    else:
        # On a reçu (cr, registry)
        cr = env_or_cr

    # Supprime toutes les données des tables personnalisées
    cr.execute("""
        DELETE FROM admission_form_template;
        DELETE FROM limesurvey_server_config;
        DELETE FROM admission_mapping_line;
        DELETE FROM admission_form_mapping;
        DELETE FROM admission_candidate;
        DELETE FROM admission_import_batch;
    """)
    cr.commit()

def post_update_hook(env_or_cr, registry=None):
    """
    Post-update script.
    Note: Can be called with either env or (cr, registry).
    """
    _logger.info('Running post-update hook for edu_admission_portal')

def pre_update_hook(env_or_cr, registry=None):
    """
    Pre-update script.
    Note: Can be called with either env or (cr, registry).
    """
    _logger.info('Running pre-update hook for edu_admission_portal')

def post_migration_hook(env_or_cr, registry=None):
    """
    Post-migration script.
    Note: Can be called with either env or (cr, registry).
    """
    _logger.info('Running post-migration hook for edu_admission_portal')

def pre_migration_hook(env_or_cr, registry=None):
    """
    Pre-migration script.
    Note: Can be called with either env or (cr, registry).
    """
    _logger.info('Running pre-migration hook for edu_admission_portal') 