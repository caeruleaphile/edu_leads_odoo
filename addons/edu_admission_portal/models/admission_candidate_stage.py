from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AdmissionCandidateStage(models.Model):
    _name = 'admission.candidate.stage'
    _description = "Étape du Pipeline d'Admission"
    _order = 'sequence, id'

    name = fields.Char(
        string='Nom',
        required=True,
        translate=True,
    )

    code = fields.Char(
        string='Code',
        required=True,
        help="Code technique de l'étape",
    )

    description = fields.Text(
        string='Description',
        translate=True,
        help="Description détaillée de l'étape",
    )

    sequence = fields.Integer(
        string='Séquence',
        default=10,
        help="Ordre d'affichage dans le pipeline",
    )

    form_template_id = fields.Many2one(
        'admission.form.template',
        string="Formulaire d'Admission",
        required=True,
        ondelete='cascade',
        help="Formulaire auquel cette étape est associée",
    )

    is_default = fields.Boolean(
        string='Étape par Défaut',
        default=False,
        help="Si coché, les nouveaux candidats seront placés dans cette étape",
    )

    fold = fields.Boolean(
        string='Plié dans Kanban',
        help="Si coché, cette étape sera pliée dans la vue Kanban",
    )

    active = fields.Boolean(
        default=True,
        help="Permet d'archiver une étape",
    )

    candidate_count = fields.Integer(
        string='Nombre de Candidats',
        compute='_compute_candidate_count',
    )

    color = fields.Integer(
        string='Couleur',
        help="Index de couleur pour la vue Kanban",
    )

    requirements = fields.Html(
        string='Prérequis',
        help="Conditions à remplir pour cette étape",
        sanitize=True,
        strip_style=True,
    )

    @api.constrains('is_default', 'form_template_id')
    def _check_default_stage(self):
        """Vérifie qu'il n'y a qu'une seule étape par défaut par formulaire."""
        for stage in self:
            if stage.is_default:
                default_stages = self.search([
                    ('form_template_id', '=', stage.form_template_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', stage.id),
                ])
                if default_stages:
                    raise ValidationError(_(
                        "Il ne peut y avoir qu'une seule étape par défaut par formulaire. "
                        "Le formulaire %(form)s a déjà l'étape %(stage)s comme étape par défaut.",
                        form=stage.form_template_id.name,
                        stage=default_stages[0].name
                    ))

    @api.depends('form_template_id')
    def _compute_candidate_count(self):
        """Calcule le nombre de candidats dans chaque étape."""
        candidates = self.env['admission.candidate'].read_group(
            [('stage_id', 'in', self.ids)],
            ['stage_id'],
            ['stage_id']
        )
        result = {x['stage_id'][0]: x['stage_id_count'] for x in candidates}
        for stage in self:
            stage.candidate_count = result.get(stage.id, 0)

    @api.model
    def create_default_stages(self, form_template):
        """Crée les étapes par défaut pour un nouveau formulaire."""
        default_stages = [
            {
                'sequence': 1,
                'name': '🆕 Nouvelle candidature',
                'code': 'new',
                'description': 'Candidat fraîchement importé',
                'is_default': True,
            },
            {
                'sequence': 2,
                'name': '📋 Dossier à vérifier',
                'code': 'pending_review',
                'description': 'En attente de validation des pièces',
            },
            {
                'sequence': 3,
                'name': '✅ Dossier complet',
                'code': 'complete',
                'description': 'Prêt pour évaluation',
            },
            {
                'sequence': 4,
                'name': '🧐 En cours d\'évaluation',
                'code': 'under_review',
                'description': 'Étude en commission',
            },
            {
                'sequence': 5,
                'name': '🟡 Liste d\'attente',
                'code': 'waitlist',
                'description': 'En attente de décision',
            },
            {
                'sequence': 6,
                'name': '📞 Entretien programmé',
                'code': 'interview',
                'description': 'Entretien prévu',
            },
            {
                'sequence': 7,
                'name': '🟢 Pré-sélectionné',
                'code': 'preselected',
                'description': 'Accepté sous condition',
            },
            {
                'sequence': 8,
                'name': '🏁 Accepté définitivement',
                'code': 'accepted',
                'description': 'Admission confirmée',
            },
            {
                'sequence': 9,
                'name': '❌ Rejeté',
                'code': 'rejected',
                'description': 'Candidat non retenu',
                'fold': True,
            },
            {
                'sequence': 10,
                'name': '📦 Archivé',
                'code': 'archived',
                'description': 'Hors campagne ou candidature reportée',
                'fold': True,
            },
        ]

        for stage_data in default_stages:
            stage_data['form_template_id'] = form_template.id
            self.create(stage_data) 