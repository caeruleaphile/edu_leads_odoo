{
    'name': 'Portail d\'Admission',
    'version': '1.1.0',
    'category': 'Website',
    'summary': 'Portail d\'admission avec intégration LimeSurvey',
    'sequence': 1,
    'author': 'caeruleaphile',
    'website': 'https://github.com/caeruleaphile',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'description': """
        Module de gestion des admissions avec intégration LimeSurvey
    """,
    'data': [
        # Sécurité
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Données
        'data/cron.xml',
        'data/mail_template_data.xml',
        
        # Vues principales
        'views/candidate_views.xml',
        'views/form_template_views.xml',
        'views/limesurvey_server_views.xml',
        'views/dashboard_views.xml',
        
        # Menus (toujours en dernier car dépend des autres vues)
        'views/menus.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
} 