from odoo import models, fields, api, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

class AdmissionDashboard(models.Model):
    _name = 'admission.dashboard'
    _description = 'Tableau de Bord des Admissions'
    _auto = False

    name = fields.Char(string='Nom', readonly=True)
    total_candidates = fields.Integer(string='Total Candidats', readonly=True)
    accepted_candidates = fields.Integer(string='Candidats Acceptés', readonly=True)
    pending_candidates = fields.Integer(string='Candidats en Attente', readonly=True)
    refused_candidates = fields.Integer(string='Candidats Refusés', readonly=True)
    
    # Champs calculés pour les graphiques
    status_distribution = fields.Text(
        string='Distribution par Statut',
        compute='_compute_status_distribution',
        readonly=True
    )
    
    submission_timeline = fields.Text(
        string='Évolution des Candidatures',
        compute='_compute_submission_timeline',
        readonly=True
    )
    
    form_distribution = fields.Text(
        string='Candidatures par Formulaire',
        compute='_compute_form_distribution',
        readonly=True
    )
    
    academic_level_distribution = fields.Text(
        string='Distribution par Niveau',
        compute='_compute_academic_level_distribution',
        readonly=True
    )

    def _compute_status_distribution(self):
        """Calcule la distribution des candidats par statut."""
        for record in self:
            data = self.env['admission.candidate'].read_group(
                [('active', '=', True)],
                ['status'],
                ['status']
            )
            record.status_distribution = json.dumps({
                'labels': [d['status'] for d in data],
                'datasets': [{
                    'data': [d['__count'] for d in data],
                    'backgroundColor': [
                        '#28a745',  # Accepté
                        '#ffc107',  # En attente
                        '#dc3545',  # Refusé
                        '#6c757d'   # Autres
                    ]
                }]
            })

    def _compute_submission_timeline(self):
        """Calcule l'évolution des candidatures dans le temps."""
        for record in self:
            # Récupère les 12 derniers mois
            months = []
            counts = []
            for i in range(11, -1, -1):
                start_date = datetime.now() - relativedelta(months=i)
                end_date = start_date + relativedelta(months=1)
                count = self.env['admission.candidate'].search_count([
                    ('submission_date', '>=', start_date),
                    ('submission_date', '<', end_date),
                    ('active', '=', True)
                ])
                months.append(start_date.strftime('%B %Y'))
                counts.append(count)

            record.submission_timeline = json.dumps({
                'labels': months,
                'datasets': [{
                    'label': 'Candidatures',
                    'data': counts,
                    'borderColor': '#007bff',
                    'fill': False
                }]
            })

    def _compute_form_distribution(self):
        """Calcule la distribution des candidats par formulaire."""
        for record in self:
            data = self.env['admission.candidate'].read_group(
                [('active', '=', True)],
                ['form_id'],
                ['form_id']
            )
            record.form_distribution = json.dumps({
                'labels': [d['form_id'][1] if d['form_id'] else 'Sans formulaire' 
                          for d in data],
                'datasets': [{
                    'data': [d['__count'] for d in data],
                    'backgroundColor': '#17a2b8'
                }]
            })

    def _compute_academic_level_distribution(self):
        """Calcule la distribution des candidats par niveau académique."""
        for record in self:
            data = self.env['admission.candidate'].read_group(
                [('active', '=', True)],
                ['academic_level'],
                ['academic_level']
            )
            record.academic_level_distribution = json.dumps({
                'labels': [d['academic_level'] if d['academic_level'] else 'Non spécifié'
                          for d in data],
                'datasets': [{
                    'data': [d['__count'] for d in data],
                    'backgroundColor': '#6f42c1'
                }]
            })

    def init(self):
        """Initialise la vue SQL du tableau de bord."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    1 as id,
                    'Dashboard' as name,
                    COUNT(*) as total_candidates,
                    COUNT(CASE WHEN status = 'accepted' THEN 1 END) as accepted_candidates,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_candidates,
                    COUNT(CASE WHEN status = 'refused' THEN 1 END) as refused_candidates
                FROM admission_candidate
                WHERE active = true
            )
        """ % self._table) 