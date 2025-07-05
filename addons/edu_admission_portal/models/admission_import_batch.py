from odoo import models, fields, api, _

class AdmissionImportBatch(models.Model):
    _name = 'admission.import.batch'
    _description = "Lot d'Import de Candidats"
    _order = 'start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )

    form_template_id = fields.Many2one(
        'admission.form.template',
        string='Formulaire',
        required=True,
        ondelete='cascade',
        tracking=True,
    )

    start_date = fields.Datetime(
        string='Début Import',
        required=True,
        tracking=True,
    )

    end_date = fields.Datetime(
        string='Fin Import',
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('running', 'En Cours'),
        ('done', 'Terminé'),
        ('partial', 'Terminé avec Erreurs'),
        ('failed', 'Échoué'),
    ], string='État',
        default='draft',
        tracking=True,
    )

    total_count = fields.Integer(
        string='Total Réponses',
        default=0,
        tracking=True,
    )

    imported_count = fields.Integer(
        string='Importés',
        default=0,
        tracking=True,
    )

    skipped_count = fields.Integer(
        string='Ignorés',
        default=0,
        tracking=True,
    )

    error_count = fields.Integer(
        string='Erreurs',
        default=0,
        tracking=True,
    )

    error_details = fields.Text(
        string='Détails des Erreurs',
        tracking=True,
    )

    duration = fields.Float(
        string='Durée (sec)',
        compute='_compute_duration',
        store=True,
    )

    success_rate = fields.Float(
        string='Taux de Succès',
        compute='_compute_success_rate',
        store=True,
    )

    candidate_ids = fields.One2many(
        'admission.candidate',
        'import_batch_id',
        string='Candidats Importés',
    )

    @api.depends('form_template_id', 'start_date')
    def _compute_name(self):
        """Calcule un nom unique pour le lot d'import."""
        for record in self:
            if record.form_template_id and record.start_date:
                record.name = f"Import {record.form_template_id.name} - {record.start_date.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                record.name = f"Nouveau Lot d'Import ({record.id})"

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        """Calcule la durée de l'import en secondes."""
        for record in self:
            if record.start_date and record.end_date:
                duration = (record.end_date - record.start_date).total_seconds()
                record.duration = round(duration, 2)
            else:
                record.duration = 0.0

    @api.depends('total_count', 'imported_count', 'error_count')
    def _compute_success_rate(self):
        """Calcule le taux de succès de l'import."""
        for record in self:
            if record.total_count > 0:
                record.success_rate = (record.imported_count / record.total_count) * 100
            else:
                record.success_rate = 0.0

    def action_view_candidates(self):
        """Ouvre la vue des candidats importés dans ce lot."""
        self.ensure_one()
        return {
            'name': _('Candidats Importés'),
            'type': 'ir.actions.act_window',
            'res_model': 'admission.candidate',
            'view_mode': 'tree,form',
            'domain': [('import_batch_id', '=', self.id)],
            'context': {'create': False},
            'target': 'current',
        } 