{
    'name': "Portail d'Admission",
    'version': '1.1.0',
    'category': 'Education',
    'summary': 'Portail d\'admission avec intégration LimeSurvey',
    'sequence': 1,
    'author': "Imane",
    'website': 'https://github.com/caeruleaphile',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'description': """
        Portail d'admission intégré avec LimeSurvey
    """,
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/limesurvey_server_views.xml',
        'views/form_template_views.xml',
        'views/admission_candidate_views.xml',
        'views/admission_mapping_line_views.xml',
        'views/admission_import_batch_views.xml',
        'views/dashboard_views.xml',
        'views/attachment_preview_template.xml',
        'views/menus.xml',
        'data/cron.xml',
        'data/mail_template_data.xml',
        'data/default_mappings.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'external_dependencies': {
        'python': ['requests'],
    },
    'assets': {
        'web.assets_backend': [
            'edu_admission_portal/static/src/js/attachment_preview.js',
            'edu_admission_portal/static/src/xml/attachment_preview.xml',
        ],
    },
    'images': [
        'static/description/banner.png',
    ],
    'post_update_hook': 'post_update_hook',
    'pre_update_hook': 'pre_update_hook',
    'post_migration_hook': 'post_migration_hook',
    'pre_migration_hook': 'pre_migration_hook',
    'migration_scripts': [
        'migrations/1.1.0/pre_migration.py',
        'migrations/1.1.0/post_migration.py',
    ],
} 