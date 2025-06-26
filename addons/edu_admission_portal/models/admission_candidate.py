import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError

_logger = logging.getLogger(__name__)

class AdmissionCandidate(models.Model):
    _name = 'admission.candidate'
    _description = "Candidat à l'Admission"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nom du Candidat',
        required=True,
        tracking=True,
        compute='_compute_name',
        store=True,
    )
    civility = fields.Selection([
        ('mr', 'Monsieur'),
        ('mrs', 'Madame'),
        ('ms', 'Mademoiselle'),
    ], string='Civilité',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    first_name = fields.Char(
        string='Prénom',
        required=True,
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    last_name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    cin_number = fields.Char(
        string='Numéro CIN',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    massar_code = fields.Char(
        string='Code MASSAR',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    birth_city = fields.Char(
        string='Ville de naissance',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    birth_date = fields.Date(
        string='Date de naissance',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    birth_country = fields.Char(
        string='Pays de naissance',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    nationality = fields.Char(
        string='Nationalité',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    address = fields.Text(
        string='Adresse',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    postal_code = fields.Char(
        string='Code postal',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    residence_country = fields.Char(
        string='Pays de résidence',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    city = fields.Char(
        string='Ville',
        tracking=True,
        compute='_compute_contact_info',
        store=True,
    )
    # Informations Bac
    bac_series = fields.Char(
        string='Série du Bac',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    bac_year = fields.Integer(
        string='Année d\'obtention du Bac',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    bac_school = fields.Char(
        string='Lycée',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    bac_country = fields.Char(
        string='Pays du Bac',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    # Informations études supérieures
    university = fields.Char(
        string='Établissement Bac+2/3',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    degree_field = fields.Char(
        string='Filière',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    university_city = fields.Char(
        string='Ville établissement',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    degree_year = fields.Integer(
        string='Année d\'obtention ou préparation du Bac+2',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    # Moyennes par année
    avg_year1 = fields.Float(
        string='Moyenne 1ère année',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_year2 = fields.Float(
        string='Moyenne 2ème année',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_year3 = fields.Float(
        string='Moyenne 3ème année',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    # Moyennes par semestre
    avg_sem1 = fields.Float(
        string='Moyenne Semestre 1',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_sem2 = fields.Float(
        string='Moyenne Semestre 2',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_sem3 = fields.Float(
        string='Moyenne Semestre 3',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_sem4 = fields.Float(
        string='Moyenne Semestre 4',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_sem5 = fields.Float(
        string='Moyenne Semestre 5',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    avg_sem6 = fields.Float(
        string='Moyenne Semestre 6',
        tracking=True,
        compute='_compute_academic_info',
        store=True,
    )
    form_id = fields.Many2one(
        'admission.form.template',
        string="Formulaire d'Admission",
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    response_id = fields.Char(
        string='ID Réponse LimeSurvey',
        required=True,
        readonly=True,
        tracking=True,
        help="Identifiant unique de la réponse dans LimeSurvey",
    )
    response_data = fields.Json(
        string='Données de Réponse',
        help="Stockage JSON des réponses du formulaire",
        readonly=True,
    )
    status = fields.Selection([
        ('new', 'Nouveau'),
        ('complete', 'Dossier Complet'),
        ('shortlisted', 'Présélectionné'),
        ('invited', 'Invité à l\'Entretien'),
        ('accepted', 'Accepté'),
        ('refused', 'Refusé'),
    ], string='Statut',
        default='new',
        tracking=True,
        required=True,
    )
    submission_date = fields.Datetime(
        string='Date de Soumission',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    last_update_date = fields.Datetime(
        string='Dernière Mise à Jour',
        compute='_compute_last_update_date',
        store=True,
        tracking=True,
    )
    email = fields.Char(
        string='Email',
        required=True,
        compute='_compute_contact_info',
        store=True,
    )
    phone = fields.Char(
        string='Téléphone',
        compute='_compute_contact_info',
        store=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Pièces Jointes',
        tracking=True,
    )
    attachment_count = fields.Integer(
        string='Nombre de Pièces Jointes',
        compute='_compute_attachment_count',
    )
    is_complete = fields.Boolean(
        string='Dossier Complet',
        compute='_compute_is_complete',
        store=True,
    )
    notes = fields.Html(
        string='Notes',
        tracking=True,
        sanitize=True,
        strip_style=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    # Validation Checkboxes
    payment_confirmed = fields.Boolean(
        string='Paiement Confirmé',
        tracking=True,
    )
    documents_validated = fields.Boolean(
        string='Documents Validés',
        tracking=True,
    )
    identity_verified = fields.Boolean(
        string='Identité Vérifiée',
        tracking=True,
    )
    academic_validated = fields.Boolean(
        string='Niveau Académique Validé',
        tracking=True,
    )
    interview_scheduled = fields.Datetime(
        string="Date d'Entretien",
        tracking=True,
    )
    interview_done = fields.Boolean(
        string='Entretien Effectué',
        tracking=True,
    )

    # Academic Level field
    academic_level = fields.Selection([
        ('bac', 'BAC'),
        ('bac+2', 'BAC+2'),
        ('bac+3', 'BAC+3'),
        ('bac+4', 'BAC+4'),
        ('bac+5', 'BAC+5'),
    ], string='Niveau Académique',
        compute='_compute_academic_level',
        store=True,
    )

    # Dashboard computed fields
    total_candidates = fields.Integer(
        string='Total Candidats',
        compute='_compute_dashboard_data',
    )
    accepted_candidates = fields.Integer(
        string='Candidats Acceptés',
        compute='_compute_dashboard_data',
    )
    pending_candidates = fields.Integer(
        string='Candidats en Attente',
        compute='_compute_dashboard_data',
    )
    refused_candidates = fields.Integer(
        string='Candidats Refusés',
        compute='_compute_dashboard_data',
    )
    status_distribution = fields.Json(
        string='Distribution par Statut',
        compute='_compute_status_distribution',
    )
    submission_timeline = fields.Json(
        string='Timeline des Soumissions',
        compute='_compute_submission_timeline',
    )
    form_distribution = fields.Json(
        string='Distribution par Formulaire',
        compute='_compute_form_distribution',
    )
    academic_level_distribution = fields.Json(
        string='Distribution par Niveau',
        compute='_compute_academic_level_distribution',
    )

    # Evaluation fields
    evaluation_score = fields.Float(
        string='Note Globale',
        compute='_compute_evaluation_score',
        store=True,
        help='Note moyenne calculée à partir des critères d\'évaluation',
    )
    
    academic_score = fields.Float(
        string='Note Académique',
        groups='edu_admission_portal.group_admission_admin,edu_admission_portal.group_admission_reviewer',
        tracking=True,
        help='Évaluation du dossier académique (0-20)',
    )
    
    experience_score = fields.Float(
        string='Note Expérience',
        groups='edu_admission_portal.group_admission_admin,edu_admission_portal.group_admission_reviewer',
        tracking=True,
        help='Évaluation des expériences professionnelles (0-20)',
    )
    
    motivation_score = fields.Float(
        string='Note Motivation',
        groups='edu_admission_portal.group_admission_admin,edu_admission_portal.group_admission_reviewer',
        tracking=True,
        help='Évaluation de la lettre de motivation (0-20)',
    )
    
    evaluation_note = fields.Html(
        string='Notes d\'Évaluation',
        groups='edu_admission_portal.group_admission_admin,edu_admission_portal.group_admission_reviewer',
        tracking=True,
        help='Notes et commentaires sur la candidature',
    )
    
    evaluation_date = fields.Datetime(
        string='Date d\'Évaluation',
        tracking=True,
    )
    
    evaluator_id = fields.Many2one(
        'res.users',
        string='Évaluateur',
        tracking=True,
    )
    
    evaluation_status = fields.Selection([
        ('pending', 'En Attente'),
        ('in_progress', 'En Cours'),
        ('completed', 'Évaluée'),
    ], string='Statut Évaluation',
        default='pending',
        tracking=True,
        groups='edu_admission_portal.group_admission_admin,edu_admission_portal.group_admission_reviewer',
    )

    _sql_constraints = [
        ('response_id_form_uniq', 'unique(response_id,form_id)',
         'Une réponse avec cet ID existe déjà pour ce formulaire!')
    ]

    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        """Calcule le nom complet du candidat."""
        for candidate in self:
            if candidate.first_name and candidate.last_name:
                candidate.name = f"{candidate.first_name} {candidate.last_name}"
            elif candidate.last_name:
                candidate.name = candidate.last_name
            elif candidate.first_name:
                candidate.name = candidate.first_name
            else:
                candidate.name = _('Nouveau Candidat')

    @api.depends('response_data')
    def _compute_contact_info(self):
        """Calcule les informations de contact à partir des données de réponse."""
        for candidate in self:
            if not candidate.response_data:
                continue

            try:
                data = candidate.response_data
                
                # Mapping des champs LimeSurvey vers les champs Odoo
                field_mapping = {
                    'civility': ['G01Q01', 'Civilité'],
                    'first_name': ['G01Q02', 'Prénom', 'FirstName'],
                    'last_name': ['G01Q03', 'Nom', 'LastName'],
                    'email': ['G01Q04', 'Email', 'EmailAddress'],
                    'phone': ['G01Q05', 'Téléphone'],
                    'cin_number': ['G01Q06', 'CIN'],
                    'massar_code': ['G01Q07', 'Code MASSAR'],
                    'birth_date': ['G01Q08', 'Date de naissance'],
                    'birth_city': ['G01Q09', 'Ville de naissance'],
                    'birth_country': ['G01Q10', 'Pays de naissance'],
                    'nationality': ['G01Q11', 'Nationalité'],
                    'address': ['G01Q12', 'Adresse'],
                    'postal_code': ['G01Q13', 'Code postal'],
                    'city': ['G01Q14', 'Ville'],
                    'residence_country': ['G01Q15', 'Pays de résidence'],
                }

                # Extraction des données
                for field, possible_keys in field_mapping.items():
                    field_value = False
                    for key in possible_keys:
                        if data.get(key):
                            field_value = data[key]
                            break
                    
                    # Vérification des champs requis
                    if field in ['first_name', 'last_name', 'email'] and not field_value:
                        raise ValidationError(_(
                            "Le champ %s est requis mais n'a pas été trouvé dans les données du formulaire"
                        ) % field)
                    
                    setattr(candidate, field, field_value)

                # Conversion de la date de naissance si présente
                if candidate.birth_date:
                    try:
                        candidate.birth_date = fields.Date.from_string(candidate.birth_date)
                    except Exception:
                        candidate.birth_date = False

            except ValidationError as ve:
                raise ve
            except Exception as e:
                _logger.error(
                    "Erreur lors du calcul des informations de contact pour le candidat %s: %s",
                    candidate.id, str(e)
                )
                # Réinitialisation des champs en cas d'erreur
                for field in field_mapping.keys():
                    setattr(candidate, field, False)

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Calcule le nombre de pièces jointes."""
        for candidate in self:
            candidate.attachment_count = len(candidate.attachment_ids)

    @api.depends('response_data', 'attachment_ids', 'payment_confirmed', 
                'documents_validated', 'identity_verified')
    def _compute_is_complete(self):
        """Vérifie si le dossier est complet selon tous les critères."""
        for candidate in self:
            candidate.is_complete = (
                bool(candidate.response_data) and
                bool(candidate.attachment_ids) and
                candidate.payment_confirmed and
                candidate.documents_validated and
                candidate.identity_verified
            )

    def action_view_attachments(self):
        """Ouvre la vue des pièces jointes."""
        self.ensure_one()
        return {
            'name': _('Pièces Jointes'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    def _send_template_email(self, template_xmlid):
        """Envoie un email basé sur le template spécifié."""
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            _logger.warning("Template d'email non trouvé: %s", template_xmlid)

    def action_mark_complete(self):
        """Marque le dossier comme complet et envoie l'email de confirmation."""
        super().action_mark_complete()
        self._send_template_email('edu_admission_portal.email_template_admission_complete')

    def action_shortlist(self):
        """Présélectionne le candidat et envoie l'email de notification."""
        super().action_shortlist()
        self._send_template_email('edu_admission_portal.email_template_admission_shortlisted')

    def action_invite(self):
        """Invite le candidat à un entretien et envoie l'email d'invitation."""
        super().action_invite()
        self._send_template_email('edu_admission_portal.email_template_admission_interview')

    def action_accept(self):
        """Accepte le candidat et envoie l'email d'acceptation."""
        super().action_accept()
        self._send_template_email('edu_admission_portal.email_template_admission_accepted')

    def action_refuse(self):
        """Refuse le candidat et envoie l'email de refus."""
        super().action_refuse()
        self._send_template_email('edu_admission_portal.email_template_admission_refused')

    @api.model
    def create_from_webhook(self, form_id, response_id, response_data, attachments=None):
        """Crée un candidat à partir des données du webhook."""
        try:
            # Validation des données requises
            if not form_id or not response_id or not response_data:
                raise ValidationError(_("Données de webhook incomplètes"))

            # Création du candidat
            vals = {
                'form_id': form_id,
                'response_id': response_id,
                'response_data': response_data,
                'status': 'new',
            }

            candidate = self.create(vals)

            # Traitement des pièces jointes
            if attachments:
                attachment_ids = []
                for att_data in attachments:
                    attachment = self.env['ir.attachment'].create({
                        'name': att_data['name'],
                        'datas': att_data['content'],
                        'res_model': self._name,
                        'res_id': candidate.id,
                    })
                    attachment_ids.append(attachment.id)
                
                if attachment_ids:
                    candidate.write({'attachment_ids': [(6, 0, attachment_ids)]})

            return candidate

        except Exception as e:
            _logger.error("Erreur lors de la création du candidat: %s", str(e))
            raise ValidationError(_("Erreur lors de la création du candidat: %s") % str(e))

    @api.depends('response_data')
    def _compute_academic_level(self):
        """Extrait le niveau académique des réponses."""
        for candidate in self:
            if not candidate.response_data:
                candidate.academic_level = False
                continue

            data = candidate.response_data
            # Cherche dans les champs communs
            level_fields = ['niveau', 'level', 'diplome', 'diploma', 'education_level']
            
            for field in level_fields:
                if field in data:
                    value = data[field].lower()
                    if 'bac+5' in value or 'master' in value:
                        candidate.academic_level = 'bac+5'
                    elif 'bac+4' in value or 'master 1' in value:
                        candidate.academic_level = 'bac+4'
                    elif 'bac+3' in value or 'licence' in value:
                        candidate.academic_level = 'bac+3'
                    elif 'bac+2' in value or 'dut' in value or 'bts' in value:
                        candidate.academic_level = 'bac+2'
                    elif 'bac' in value:
                        candidate.academic_level = 'bac'
                    break
            else:
                candidate.academic_level = False

    @api.model
    def _compute_dashboard_data(self):
        """Calcule les KPIs du tableau de bord."""
        domain = self._get_dashboard_domain()
        
        for record in self:
            record.total_candidates = self.search_count(domain)
            record.accepted_candidates = self.search_count(domain + [('status', '=', 'accepted')])
            record.pending_candidates = self.search_count(
                domain + [('status', 'in', ['new', 'complete', 'shortlisted', 'invited'])]
            )
            record.refused_candidates = self.search_count(domain + [('status', '=', 'refused')])

    @api.model
    def _compute_status_distribution(self):
        """Calcule la distribution des statuts pour le graphique circulaire."""
        domain = self._get_dashboard_domain()
        
        for record in self:
            data = []
            for status, label in self._fields['status'].selection:
                count = self.search_count(domain + [('status', '=', status)])
                if count:
                    data.append({
                        'label': label,
                        'value': count,
                        'color': self._get_status_color(status),
                    })
            
            record.status_distribution = {
                'data': data,
                'title': 'Distribution par Statut',
            }

    @api.model
    def _compute_submission_timeline(self):
        """Calcule l'évolution des candidatures dans le temps."""
        domain = self._get_dashboard_domain()
        
        for record in self:
            # Groupe par mois
            self.env.cr.execute("""
                SELECT DATE_TRUNC('month', submission_date) as month,
                       COUNT(*) as count
                FROM admission_candidate
                WHERE submission_date >= NOW() - INTERVAL '1 year'
                GROUP BY DATE_TRUNC('month', submission_date)
                ORDER BY month
            """)
            
            data = self.env.cr.dictfetchall()
            record.submission_timeline = {
                'labels': [d['month'].strftime('%B %Y') for d in data],
                'datasets': [{
                    'label': 'Candidatures',
                    'data': [d['count'] for d in data],
                }],
            }

    @api.model
    def _compute_form_distribution(self):
        """Calcule la distribution des candidatures par formulaire."""
        domain = self._get_dashboard_domain()
        
        for record in self:
            data = []
            forms = self.env['admission.form.template'].search([])
            
            for form in forms:
                count = self.search_count(domain + [('form_id', '=', form.id)])
                if count:
                    data.append({
                        'label': form.name,
                        'value': count,
                    })
            
            record.form_distribution = {
                'data': data,
                'title': 'Candidatures par Formulaire',
            }

    @api.model
    def _compute_academic_level_distribution(self):
        """Calcule la distribution des niveaux académiques."""
        domain = self._get_dashboard_domain()
        
        for record in self:
            data = []
            for level, label in self._fields['academic_level'].selection:
                count = self.search_count(domain + [('academic_level', '=', level)])
                if count:
                    data.append({
                        'label': label,
                        'value': count,
                    })
            
            record.academic_level_distribution = {
                'data': data,
                'title': 'Distribution par Niveau',
            }

    @api.depends('academic_score', 'experience_score', 'motivation_score')
    def _compute_evaluation_score(self):
        """Compute the overall evaluation score as an average of all scores."""
        for record in self:
            scores = [
                score for score in [
                    record.academic_score,
                    record.experience_score,
                    record.motivation_score
                ] if score > 0
            ]
            record.evaluation_score = sum(scores) / len(scores) if scores else 0.0

    def action_start_evaluation(self):
        """Start the evaluation process for the candidate."""
        if self.evaluation_status != 'pending':
            raise UserError(_("L'évaluation ne peut être démarrée que pour les candidats en attente d'évaluation."))
        
        self.write({
            'evaluation_status': 'in_progress',
            'evaluator_id': self.env.user.id,
        })
        return True

    def action_complete_evaluation(self):
        """Complete the evaluation process for the candidate."""
        if self.evaluation_status != 'in_progress':
            raise UserError(_("Seules les évaluations en cours peuvent être terminées."))
        
        if not all(self[field] for field in ['academic_score', 'experience_score', 'motivation_score']):
            raise UserError(_("Toutes les notes d'évaluation doivent être renseignées avant de terminer l'évaluation."))
        
        self.write({
            'evaluation_status': 'completed',
            'evaluation_date': fields.Datetime.now(),
        })
        return True

    def action_reset_evaluation(self):
        """Reset the evaluation to pending status."""
        if self.evaluation_status == 'pending':
            raise UserError(_("L'évaluation est déjà en attente."))
        
        self.write({
            'evaluation_status': 'pending',
            'academic_score': 0.0,
            'experience_score': 0.0,
            'motivation_score': 0.0,
            'evaluation_note': False,
            'evaluator_id': False,
            'evaluation_date': False,
        })
        return True

    @api.model
    def _clean_old_attachments(self, days=90):
        """Clean up old attachments from refused or inactive candidates.
        
        Args:
            days (int): Number of days after which attachments should be cleaned
        """
        cutoff_date = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        
        # Find candidates that are either refused or inactive
        candidates = self.search([
            '|',
            ('status', '=', 'refused'),
            ('active', '=', False),
            ('write_date', '<', cutoff_date)
        ])
        
        if not candidates:
            return
            
        # Get all attachments
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', 'in', candidates.ids)
        ])
        
        # Delete the attachments
        if attachments:
            _logger.info('Cleaning %d old attachments from %d candidates', 
                        len(attachments), len(candidates))
            attachments.unlink()

    @api.model
    def _get_dashboard_domain(self):
        """Retourne le domaine pour les calculs du tableau de bord."""
        domain = []
        context = self.env.context
        
        if context.get('dashboard_year'):
            year = context['dashboard_year']
            domain += [
                ('submission_date', '>=', f'{year}-01-01'),
                ('submission_date', '<=', f'{year}-12-31'),
            ]
        
        if context.get('form_id'):
            domain += [('form_id', '=', context['form_id'])]
            
        if context.get('academic_level'):
            domain += [('academic_level', '=', context['academic_level'])]
            
        return domain

    @api.model
    def _get_status_color(self, status):
        colors = {
            'new': '#808080',        # Gray
            'complete': '#17a2b8',    # Info blue
            'shortlisted': '#ffc107', # Warning yellow
            'invited': '#007bff',     # Primary blue
            'accepted': '#28a745',    # Success green
            'refused': '#dc3545',     # Danger red
        }
        return colors.get(status, '#808080')

    @api.depends('write_date', 'create_date')
    def _compute_last_update_date(self):
        """Calcule la date de dernière mise à jour."""
        for record in self:
            record.last_update_date = record.write_date or record.create_date 

    @api.depends('response_data')
    def _compute_academic_info(self):
        """Extrait les informations académiques des réponses."""
        for candidate in self:
            if not candidate.response_data:
                candidate.bac_series = False
                candidate.bac_year = False
                candidate.bac_school = False
                candidate.bac_country = False
                candidate.university = False
                candidate.degree_field = False
                candidate.university_city = False
                candidate.degree_year = False
                candidate.avg_year1 = False
                candidate.avg_year2 = False
                candidate.avg_year3 = False
                candidate.avg_sem1 = False
                candidate.avg_sem2 = False
                candidate.avg_sem3 = False
                candidate.avg_sem4 = False
                candidate.avg_sem5 = False
                candidate.avg_sem6 = False
                continue

            try:
                data = candidate.response_data
                
                # Extraction série du Bac
                bac_series_fields = ['G04Q17', 'Série du Bac']
                for field in bac_series_fields:
                    if data.get(field):
                        candidate.bac_series = data[field]
                        break
                
                # Extraction année d'obtention du Bac
                bac_year_fields = ['G04Q21', 'Année d\'obtention du Bac']
                for field in bac_year_fields:
                    if data.get(field):
                        candidate.bac_year = int(data[field]) if data[field] else False
                        break
                
                # Extraction lycée
                bac_school_fields = ['G04Q22', 'Lycée']
                for field in bac_school_fields:
                    if data.get(field):
                        candidate.bac_school = data[field]
                        break
                
                # Extraction pays du Bac
                bac_country_fields = ['G04Q23', 'Pays']
                for field in bac_country_fields:
                    if data.get(field):
                        candidate.bac_country = data[field]
                        break
                
                # Extraction établissement Bac+2/3
                university_fields = ['G05Q25', 'Établissement Bac+2/3']
                for field in university_fields:
                    if data.get(field):
                        candidate.university = data[field]
                        break
                
                # Extraction filière
                degree_field_fields = ['G05Q26', 'Filière']
                for field in degree_field_fields:
                    if data.get(field):
                        candidate.degree_field = data[field]
                        break
                
                # Extraction ville établissement
                university_city_fields = ['G05Q28', 'Ville établissement']
                for field in university_city_fields:
                    if data.get(field):
                        candidate.university_city = data[field]
                        break
                
                # Extraction année d'obtention ou préparation du Bac+2
                degree_year_fields = ['G01Q29', 'Année d\'obtention ou préparation du Bac+2']
                for field in degree_year_fields:
                    if data.get(field):
                        candidate.degree_year = int(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne 1ère année
                avg_year1_fields = ['G01Q32[SQ001_SQ001]', 'Moyenne 1ère année']
                for field in avg_year1_fields:
                    if data.get(field):
                        candidate.avg_year1 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne 2ème année
                avg_year2_fields = ['G01Q32[SQ001_SQ002]', 'Moyenne 2ème année']
                for field in avg_year2_fields:
                    if data.get(field):
                        candidate.avg_year2 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne 3ème année
                avg_year3_fields = ['G01Q32[SQ001_SQ003]', 'Moyenne 3ème année']
                for field in avg_year3_fields:
                    if data.get(field):
                        candidate.avg_year3 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 1
                avg_sem1_fields = ['G05Q31[SQ001_SQ001]', 'Moyenne Semestre 1']
                for field in avg_sem1_fields:
                    if data.get(field):
                        candidate.avg_sem1 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 2
                avg_sem2_fields = ['G05Q31[SQ001_SQ002]', 'Moyenne Semestre 2']
                for field in avg_sem2_fields:
                    if data.get(field):
                        candidate.avg_sem2 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 3
                avg_sem3_fields = ['G05Q31[SQ001_SQ003]', 'Moyenne Semestre 3']
                for field in avg_sem3_fields:
                    if data.get(field):
                        candidate.avg_sem3 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 4
                avg_sem4_fields = ['G05Q31[SQ001_SQ004]', 'Moyenne Semestre 4']
                for field in avg_sem4_fields:
                    if data.get(field):
                        candidate.avg_sem4 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 5
                avg_sem5_fields = ['G05Q31[SQ001_SQ005]', 'Moyenne Semestre 5']
                for field in avg_sem5_fields:
                    if data.get(field):
                        candidate.avg_sem5 = float(data[field]) if data[field] else False
                        break
                
                # Extraction moyenne Semestre 6
                avg_sem6_fields = ['G05Q31[SQ001_SQ006]', 'Moyenne Semestre 6']
                for field in avg_sem6_fields:
                    if data.get(field):
                        candidate.avg_sem6 = float(data[field]) if data[field] else False
                        break
                        
            except Exception as e:
                _logger.error("Erreur lors de l'extraction des informations académiques: %s", str(e))
                candidate.bac_series = False
                candidate.bac_year = False
                candidate.bac_school = False
                candidate.bac_country = False
                candidate.university = False
                candidate.degree_field = False
                candidate.university_city = False
                candidate.degree_year = False
                candidate.avg_year1 = False
                candidate.avg_year2 = False
                candidate.avg_year3 = False
                candidate.avg_sem1 = False
                candidate.avg_sem2 = False
                candidate.avg_sem3 = False
                candidate.avg_sem4 = False
                candidate.avg_sem5 = False
                candidate.avg_sem6 = False 