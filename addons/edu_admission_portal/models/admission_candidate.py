import logging
import json
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import datetime, timedelta
import traceback

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
        string='ID Réponse',
        readonly=True,
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

    color = fields.Integer(
        string='Color Index',
        help='Color index for kanban view',
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

    stage_id = fields.Many2one(
        'admission.candidate.stage',
        string='Étape',
        domain="[('form_template_id', '=', form_id)]",
        tracking=True,
        group_expand='_read_group_stage_ids',
        copy=False,
    )

    user_id = fields.Many2one(
        'res.users',
        string='Responsable',
        default=lambda self: self.env.user,
        tracking=True,
    )

    # Mapping des statuts autorisés par code d'étape
    _STAGE_STATUS_MAPPING = {
        'new': ['new'],
        'pending_review': ['new', 'complete'],
        'complete': ['complete'],
        'under_review': ['complete', 'shortlisted'],
        'waitlist': ['shortlisted'],
        'interview': ['shortlisted', 'invited'],
        'preselected': ['invited', 'accepted'],
        'accepted': ['accepted'],
        'rejected': ['refused'],
        'archived': ['refused', 'accepted'],
    }

    _sql_constraints = [
        ('response_id_form_uniq', 'unique(response_id,form_id)',
         'Une réponse avec cet ID existe déjà pour ce formulaire!')
    ]

    import_batch_id = fields.Many2one(
        'admission.import.batch',
        string="Lot d'Import",
        readonly=True,
        ondelete='set null',
        help="Lot d'import lors de la création du candidat",
    )

    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        """Calcule le nom complet du candidat."""
        for candidate in self:
            try:
                if candidate.first_name and candidate.last_name:
                    candidate.name = f"{candidate.first_name} {candidate.last_name}"
                elif candidate.last_name:
                    candidate.name = candidate.last_name
                elif candidate.first_name:
                    candidate.name = candidate.first_name
                else:
                    candidate.name = f"Nouveau candidat ({candidate.id})"
            except Exception as e:
                _logger.error(f"Erreur lors du calcul du nom complet: {str(e)}")
                candidate.name = f"Nouveau candidat ({candidate.id})"

    @api.depends('response_data')
    def _compute_contact_info(self):
        """Calcule les informations de contact à partir des données de réponse."""
        for candidate in self:
            if not candidate.response_data:
                continue
                
            _logger.info(f"Calcul des informations de contact pour le candidat {candidate.id}")
            _logger.info(f"Données de réponse: {candidate.response_data}")
            
            try:
                # Recherche des champs dans les données de réponse
                response_data = candidate.response_data
                
                # Civilité (G01Q01)
                civility_mapping = {
                    'M.': 'mr',
                    'Mme': 'mrs',
                    'Mlle': 'ms'
                }
                civility_value = response_data.get('G01Q01')
                candidate.civility = civility_mapping.get(civility_value, 'mr')
                
                # Nom (G01Q02)
                candidate.last_name = response_data.get('G01Q02', '')
                
                # Prénom (G01Q03)
                candidate.first_name = response_data.get('G01Q03', '')
                
                # Email (G03Q14)
                candidate.email = response_data.get('G03Q14', '')
                
                # Téléphone (G03Q15)
                candidate.phone = response_data.get('G03Q15', '')
                
                _logger.info(f"Informations calculées: {candidate.first_name} {candidate.last_name} ({candidate.email})")
                
            except Exception as e:
                _logger.error(f"Erreur lors du calcul des informations de contact: {str(e)}")
                _logger.error(f"Traceback: {traceback.format_exc()}")

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

    @api.constrains('stage_id', 'form_id')
    def _check_stage_form_consistency(self):
        """Vérifie que l'étape appartient bien au formulaire du candidat."""
        for record in self:
            if record.stage_id and record.stage_id.form_template_id != record.form_id:
                raise ValidationError(_(
                    "L'étape %(stage)s ne peut pas être utilisée avec le formulaire %(form)s. "
                    "Les étapes sont spécifiques à chaque formulaire.",
                    stage=record.stage_id.name,
                    form=record.form_id.name
                ))

    @api.constrains('status', 'stage_id')
    def _check_status_stage_consistency(self):
        """Vérifie la cohérence entre le statut et l'étape du candidat."""
        for record in self:
            if not record.stage_id or not record.status:
                continue
            
            allowed_statuses = self._STAGE_STATUS_MAPPING.get(record.stage_id.code, [])
            if record.status not in allowed_statuses:
                raise ValidationError(_(
                    "Le statut %(status)s n'est pas autorisé pour l'étape %(stage)s. "
                    "Statuts autorisés : %(allowed)s",
                    status=dict(self._fields['status'].selection).get(record.status),
                    stage=record.stage_id.name,
                    allowed=', '.join(dict(self._fields['status'].selection).get(s) for s in allowed_statuses)
                ))

    @api.constrains('attachment_ids', 'form_id')
    def _check_required_attachments(self):
        """Vérifie la présence des pièces jointes requises."""
        for record in self:
            # TODO: Implémenter la logique de vérification des pièces requises
            # selon le formulaire et le mapping
            required_docs = record.form_id.get_required_documents()
            if not required_docs:
                continue

            attached_types = set(record.attachment_ids.mapped('res_model'))
            missing_docs = [doc for doc in required_docs if doc not in attached_types]
            
            if missing_docs:
                raise ValidationError(_(
                    "Documents obligatoires manquants : %(docs)s",
                    docs=', '.join(missing_docs)
                ))

    def action_move_to_stage(self, stage):
        """
        Déplace le candidat vers une nouvelle étape en synchronisant le statut.
        
        Args:
            stage: L'objet admission.candidate.stage cible
            
        Returns:
            bool: True si le déplacement a réussi
            
        Raises:
            ValidationError: Si le déplacement n'est pas autorisé
        """
        self.ensure_one()
        
        # Vérifie que l'étape appartient au bon formulaire
        if stage.form_template_id != self.form_id:
            raise ValidationError(_(
                "Impossible de déplacer vers une étape d'un autre formulaire."
            ))
        
        # Détermine le nouveau statut selon l'étape
        new_status = None
        allowed_statuses = self._STAGE_STATUS_MAPPING.get(stage.code, [])
        
        # Si le statut actuel est autorisé dans la nouvelle étape, on le garde
        if self.status in allowed_statuses:
            new_status = self.status
        # Sinon on prend le premier statut autorisé
        elif allowed_statuses:
            new_status = allowed_statuses[0]
        else:
            raise ValidationError(_(
                "Aucun statut valide trouvé pour l'étape %(stage)s",
                stage=stage.name
            ))
            
        # Met à jour l'étape et le statut
        self.write({
            'stage_id': stage.id,
            'status': new_status,
        })
        
        return True

    @api.model
    def create_from_webhook(self, form_id, response_id, response_data, attachments=None):
        """
        Crée un candidat à partir des données du webhook LimeSurvey.
        
        Args:
            form_id (int): ID du formulaire LimeSurvey
            response_id (str): ID de la réponse LimeSurvey
            response_data (dict): Données de la réponse
            attachments (list): Liste des pièces jointes
            
        Returns:
            record: Le candidat créé
        """
        _logger.info(
            "Création d'un candidat depuis webhook - Form: %s, Response: %s",
            form_id, response_id
        )
        
        try:
            # Récupération du template de formulaire
            form_template = self.env['admission.form.template'].sudo().search([
                ('sid', '=', str(form_id))
            ], limit=1)
            
            if not form_template:
                raise ValidationError(_(
                    "Formulaire non trouvé pour l'ID LimeSurvey %s"
                ) % form_id)

            # Vérification si la réponse existe déjà
            existing = self.sudo().search([
                ('form_id', '=', form_template.id),
                ('response_id', '=', str(response_id))
            ], limit=1)
            
            if existing:
                _logger.warning(
                    "Réponse déjà existante - Form: %s, Response: %s",
                    form_id, response_id
                )
                return existing

            # Traitement des données du formulaire
            processed_data = form_template._process_survey_response(response_data)
            
            # Création du candidat
            vals = {
                'form_id': form_template.id,
                'response_id': str(response_id),
                'response_data': processed_data,
                'status': 'new',
                'submission_date': fields.Datetime.now(),
            }

            # Création du candidat
            candidate = self.sudo().create(vals)
            _logger.info("Candidat créé avec succès - ID: %s", candidate.id)

            # Traitement des pièces jointes
            if attachments:
                try:
                    self._validate_attachments(attachments, form_template)
                    self._create_attachments(candidate.id, attachments)
                    _logger.info(
                        "Pièces jointes créées pour le candidat %s",
                        candidate.id
                    )
                except Exception as e:
                    _logger.error(
                        "Erreur lors du traitement des pièces jointes: %s",
                        str(e)
                    )
                    # On ne lève pas l'erreur pour ne pas bloquer la création

            # Traitement des données du formulaire
            candidate._process_form_data()
            
            # Vérification de la complétude
            candidate._check_required_fields()
            
            # Notification
            candidate.message_post(
                body=_("Candidature créée depuis le formulaire LimeSurvey"),
                message_type='notification'
            )

            return candidate

        except Exception as e:
            _logger.error(
                "Erreur lors de la création du candidat - Form: %s, Response: %s\n%s",
                form_id, response_id, traceback.format_exc()
            )
            raise ValidationError(_(
                "Erreur lors de la création du candidat: %s"
            ) % str(e))

    def _process_form_data(self):
        """Traite les données du formulaire pour mettre à jour les champs du candidat."""
        self.ensure_one()
        
        if not self.response_data:
            return

        try:
            # Récupération du mapping
            mapping = self.env['admission.form.mapping'].search([
                ('form_template_id', '=', self.form_id.id),
                ('state', '=', 'validated')
                ], limit=1)
                
            if not mapping:
                _logger.warning(
                    "Aucun mapping validé trouvé pour le formulaire %s",
                    self.form_id.name
                )
                return

            # Traitement des données
            processed_data = {}
            attachments_data = []

            # Pour chaque ligne de mapping
            for line in mapping.mapping_line_ids.filtered(lambda l: l.status == 'validated'):
                try:
                    # Récupération de la valeur source
                    value = self.response_data.get(line.question_code)
                    
                    if value is None:
                        continue

                    # Si c'est une pièce jointe
                    if line.is_attachment and isinstance(value, dict):
                        attachments_data.append({
                            'name': value.get('name', 'Sans nom'),
                            'data': value.get('content'),
                            'type': value.get('type', 'application/octet-stream'),
                            'field': line.question_code
                        })
                        continue

                    # Transformation de la valeur si nécessaire
                    if line.mapping_type == 'transform' and line.transform_python:
                        try:
                            value = line.transform_value(value)
                        except Exception as e:
                            _logger.error(
                                "Erreur lors de la transformation pour %s: %s",
                                line.question_code, str(e)
                            )
                            continue

                    # Validation de la valeur si nécessaire
                    if line.validation_python:
                        try:
                            if not line.validate_value(value):
                                _logger.warning(
                                    "Validation échouée pour %s: %s",
                                    line.question_code, value
                                )
                                continue
                        except Exception as e:
                            _logger.error(
                                "Erreur lors de la validation pour %s: %s",
                                line.question_code, str(e)
                            )
                            continue

                    # Ajout de la valeur aux données traitées
                    if line.odoo_field:
                        processed_data[line.odoo_field] = value
                
                except Exception as e:
                    _logger.error(
                        "Erreur lors du traitement de la ligne %s: %s",
                        line.question_code, str(e)
                    )
                    continue

            # Mise à jour des champs du candidat
            if processed_data:
                self.write(processed_data)
                _logger.info(
                    "Données mises à jour pour le candidat %s: %s",
                    self.id, processed_data
                )

            # Traitement des pièces jointes
            if attachments_data:
                self._process_attachments(attachments_data)

            # Vérification de la complétude
            self._check_required_fields()
            
        except Exception as e:
            _logger.error(
                "Erreur lors du traitement des données du formulaire: %s",
                str(e)
            )
            raise

    def _process_attachments(self, attachments_data):
        """Traite les pièces jointes du formulaire."""
        for attachment in attachments_data:
            try:
                # Création de la pièce jointe
                attachment_vals = {
                    'name': attachment['name'],
                    'datas': attachment['data'],
                    'mimetype': attachment['type'],
                    'res_model': self._name,
                    'res_id': self.id,
                }

                # Création de la pièce jointe
                attachment_id = self.env['ir.attachment'].create(attachment_vals)

                # Ajout au candidat
                self.write({
                    'attachment_ids': [(4, attachment_id.id)]
                })

                _logger.info(
                    "Pièce jointe créée pour le candidat %s: %s",
                    self.id, attachment['name']
                )

            except Exception as e:
                _logger.error(
                    "Erreur lors de la création de la pièce jointe %s: %s",
                    attachment.get('name', 'unknown'), str(e)
                )
                continue

    @api.model
    def _clean_incomplete_candidates(self, days=30):
        """
        Nettoie les candidatures incomplètes après un certain nombre de jours.
        
        Args:
            days (int): Nombre de jours avant suppression
        """
        deadline = fields.Datetime.now() - timedelta(days=days)
        candidates = self.search([
            ('create_date', '<', deadline),
            ('is_complete', '=', False),
            ('status', '=', 'new')
        ])
        
        for candidate in candidates:
            try:
                # Suppression des pièces jointes
                candidate.attachment_ids.unlink()
                # Suppression du candidat
                candidate.unlink()
            except Exception as e:
                _logger.error(
                    "Erreur lors de la suppression du candidat %s: %s",
                    candidate.id, str(e)
                )
                continue

        _logger.info("%d candidatures incomplètes nettoyées", len(candidates))

    @api.model
    def _auto_check_completeness(self):
        """
        Vérifie automatiquement si les dossiers sont complets.
        Cette méthode est appelée par le CRON.
        """
        candidates = self.search([
            ('status', '=', 'new'),
            ('is_complete', '=', False)
        ])
        
        for candidate in candidates:
            try:
                # Vérification de la complétude
                if candidate._check_required_fields() and candidate._check_required_attachments():
                    candidate.write({
                        'status': 'complete',
                        'is_complete': True
                    })
                    candidate.message_post(
                        body=_("Dossier marqué comme complet automatiquement"),
                        message_type='notification'
                    )
            except Exception as e:
                _logger.error(
                    "Erreur lors de la vérification de la complétude pour le candidat %s: %s",
                    candidate.id, str(e)
                )
                continue

    def _check_required_fields(self):
        """
        Vérifie si tous les champs requis sont remplis.
        
        Returns:
            bool: True si tous les champs requis sont remplis
        """
        self.ensure_one()
        
        # Récupération des mappings requis
        required_mappings = self.env['admission.mapping.line'].sudo().search([
            ('mapping_id.form_template_id', '=', self.form_id.id),
            ('status', '=', 'validated'),
            ('is_required', '=', True)
        ])

        # Vérification de chaque champ requis
        for mapping in required_mappings:
            value = self.response_data.get(mapping.question_code)
            if value is None or value == '':
                return False

        return True

    def _validate_attachments(self, attachments, form):
        """Valide les pièces jointes avant import."""
        ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 
                        'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        MAX_SIZE = 10 * 1024 * 1024  # 10 MB
        
        for name, content, mime_type in attachments:
            # Validation du type MIME
            if mime_type not in ALLOWED_TYPES:
                raise ValidationError(_(
                    "Type de fichier non autorisé pour %(name)s (type: %(type)s)",
                    name=name, type=mime_type
                ))
            
            # Validation de la taille
            if len(content) > MAX_SIZE:
                raise ValidationError(_(
                    "Fichier trop volumineux : %(name)s (max: 10 MB)",
                    name=name
                ))
            
            # Validation du nom
            if not re.match(r'^[\w\-. ]+$', name):
                raise ValidationError(_(
                    "Nom de fichier invalide : %(name)s",
                    name=name
                ))

    def _create_attachments(self, candidate_id, attachments):
        """Crée les pièces jointes pour un candidat."""
        IrAttachment = self.env['ir.attachment']
        attachment_ids = []
        
        for name, content, mime_type in attachments:
            attachment = IrAttachment.create({
                'name': name,
                'res_model': self._name,
                'res_id': candidate_id,
                'type': 'binary',
                'datas': content,
                'mimetype': mime_type,
            })
            attachment_ids.append(attachment.id)
        
        if attachment_ids:
            self.browse(candidate_id).write({
                'attachment_ids': [(4, att_id) for att_id in attachment_ids]
            })

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

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Utilisé pour toujours afficher toutes les étapes dans la vue kanban."""
        if self._context.get('default_form_id'):
            search_domain = [('form_template_id', '=', self._context['default_form_id'])]
        else:
            search_domain = []
        return self.env['admission.candidate.stage'].search(search_domain, order=order)

    @api.model
    def create(self, vals):
        """Surcharge de create pour affecter l'étape par défaut."""
        record = super().create(vals)
        
        # Si pas d'étape définie et qu'on a un formulaire
        if not record.stage_id and record.form_id:
            # Recherche de l'étape par défaut
            default_stage = self.env['admission.candidate.stage'].search([
                ('form_template_id', '=', record.form_id.id),
                ('is_default', '=', True)
            ], limit=1)
            
            if default_stage:
                record.stage_id = default_stage.id
            else:
                _logger.warning(
                    "Aucune étape par défaut trouvée pour le formulaire %s (ID: %s)",
                    record.form_id.name, record.form_id.id
                )
        
        return record

    @api.onchange('form_id')
    def _onchange_form_id(self):
        """Reset stage_id when form changes to avoid invalid stages."""
        if self.form_id:
            self.stage_id = False

    def write(self, vals):
        """Surcharge de write pour gérer le changement de formulaire."""
        if 'form_id' in vals and not vals.get('stage_id'):
            # Recherche de l'étape par défaut du nouveau formulaire
            default_stage = self.env['admission.candidate.stage'].search([
                ('form_template_id', '=', vals['form_id']),
                ('is_default', '=', True)
            ], limit=1)
            
            if default_stage:
                vals['stage_id'] = default_stage.id
            else:
                _logger.warning(
                    "Aucune étape par défaut trouvée pour le formulaire ID: %s",
                    vals['form_id']
                )
                vals['stage_id'] = False
                
        return super().write(vals)

    @api.depends('response_data', 'academic_level', 'experience_years')
    def _compute_scores(self):
        """Calcule automatiquement les scores du candidat."""
        for candidate in self:
            # Score académique (0-40 points)
            academic_score = 0
            if candidate.academic_level:
                ACADEMIC_SCORES = {
                    'bac': 20,
                    'bac+2': 25,
                    'bac+3': 30,
                    'bac+4': 35,
                    'bac+5': 40
                }
                academic_score = ACADEMIC_SCORES.get(candidate.academic_level, 0)
            
            # Score d'expérience (0-30 points)
            experience_score = min(candidate.experience_years * 5, 30)
            
            # Score de motivation (0-30 points)
            motivation_score = 0
            if candidate.response_data:
                # Analyse des réponses aux questions de motivation
                motivation_keys = ['motivation', 'projet', 'objectifs', 'ambitions']
                responses = []
                for key in motivation_keys:
                    for field, value in candidate.response_data.items():
                        if key in field.lower() and isinstance(value, str):
                            responses.append(value)
                
                # Évaluation basée sur la longueur et la qualité des réponses
                for response in responses:
                    # Longueur (0-10 points)
                    words = len(response.split())
                    length_score = min(words / 50, 1) * 10
                    
                    # Mots clés positifs (0-10 points)
                    POSITIVE_KEYWORDS = [
                        'passion', 'objectif', 'projet', 'ambition', 'motivation',
                        'réussite', 'développement', 'apprentissage', 'challenge',
                        'innovation', 'excellence', 'engagement', 'détermination'
                    ]
                    keyword_count = sum(1 for word in POSITIVE_KEYWORDS if word in response.lower())
                    keyword_score = min(keyword_count * 2, 10)
                    
                    # Score total pour cette réponse
                    response_score = (length_score + keyword_score) / len(responses)
                    motivation_score += response_score
            
            # Mise à jour des scores
            candidate.academic_score = academic_score
            candidate.experience_score = experience_score
            candidate.motivation_score = motivation_score
            
            # Score total et recommandation
            total_score = academic_score + experience_score + motivation_score
            candidate.total_score = total_score
            
            # Recommandation automatique
            if total_score >= 80:
                candidate.recommendation = 'strong_accept'
            elif total_score >= 60:
                candidate.recommendation = 'accept'
            elif total_score >= 40:
                candidate.recommendation = 'review'
            else:
                candidate.recommendation = 'reject'

    def action_evaluate(self):
        """Lance l'évaluation automatique du candidat."""
        self.ensure_one()
        
        if not self.response_data:
            raise ValidationError(_("Impossible d'évaluer un candidat sans réponses"))
        
        try:
            # Force le recalcul des scores
            self._compute_scores()
            
            # Crée une note d'évaluation
            self.env['mail.message'].create({
                'model': self._name,
                'res_id': self.id,
                'message_type': 'comment',
                'body': _("""
                    <strong>Évaluation Automatique</strong><br/>
                    Score académique: %(academic)s/40<br/>
                    Score d'expérience: %(experience)s/30<br/>
                    Score de motivation: %(motivation)s/30<br/>
                    <br/>
                    Score total: %(total)s/100<br/>
                    Recommandation: %(recommendation)s
                """) % {
                    'academic': round(self.academic_score, 1),
                    'experience': round(self.experience_score, 1),
                    'motivation': round(self.motivation_score, 1),
                    'total': round(self.total_score, 1),
                    'recommendation': dict(self._fields['recommendation'].selection).get(
                        self.recommendation, ''
                    )
                }
            })
            
            # Met à jour le statut si nécessaire
            if self.status == 'new':
                self.write({'status': 'evaluated'})
            
        except Exception as e:
            raise ValidationError(_(
                "Erreur lors de l'évaluation automatique: %s", str(e)
            ))

    def action_schedule_interview(self):
        """Planifie un entretien pour le candidat."""
        self.ensure_one()
        
        # Vérifie que le candidat peut être invité
        if self.status not in ['evaluated', 'shortlisted']:
            raise ValidationError(_(
                "Le candidat doit être évalué ou présélectionné pour planifier un entretien"
            ))
        
        # Crée un événement calendrier
        calendar_event = self.env['calendar.event'].create({
            'name': _('Entretien - %s') % self.name,
            'start': fields.Datetime.now() + timedelta(days=7),  # Par défaut dans 7 jours
            'stop': fields.Datetime.now() + timedelta(days=7, hours=1),  # Durée 1h
            'duration': 1.0,
            'partner_ids': [(4, self.partner_id.id)] if self.partner_id else False,
            'user_id': self.env.user.id,
            'admission_candidate_id': self.id,
        })
        
        # Met à jour le statut du candidat
        self.write({
            'status': 'interview_scheduled',
            'interview_date': calendar_event.start,
        })
        
        # Envoie l'invitation par email
        if self.email:
            template = self.env.ref('edu_admission_portal.email_template_interview_invitation')
            template.send_mail(self.id, force_send=True)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'res_id': calendar_event.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_record_interview_feedback(self):
        """Enregistre le feedback d'entretien."""
        self.ensure_one()
        
        if self.status != 'interview_scheduled':
            raise ValidationError(_("L'entretien doit être planifié pour enregistrer un feedback"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Feedback Entretien'),
            'res_model': 'admission.interview.feedback.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_candidate_id': self.id,
                'default_interview_date': self.interview_date,
            }
        }

    @api.depends('status')
    def _compute_dashboard_data(self):
        """Compute dashboard KPI data"""
        domain = self._get_dashboard_domain()
        all_candidates = self.env['admission.candidate'].search(domain)
        
        for record in self:
            record.total_candidates = len(all_candidates)
            record.accepted_candidates = len(all_candidates.filtered(lambda r: r.status == 'accepted'))
            record.pending_candidates = len(all_candidates.filtered(lambda r: r.status in ['new', 'complete', 'shortlisted', 'invited']))
            record.refused_candidates = len(all_candidates.filtered(lambda r: r.status == 'refused'))

    @api.depends('status')
    def _compute_status_distribution(self):
        """Compute status distribution for pie chart"""
        domain = self._get_dashboard_domain()
        candidates = self.env['admission.candidate'].search(domain)
        
        status_counts = {}
        status_labels = dict(self._fields['status'].selection)
        
        for status, _ in self._fields['status'].selection:
            count = len(candidates.filtered(lambda r: r.status == status))
            if count > 0:  # Only include non-zero counts
                status_counts[status_labels[status]] = count
        
        for record in self:
            record.status_distribution = {
                'labels': list(status_counts.keys()),
                'datasets': [{
                    'data': list(status_counts.values()),
                    'backgroundColor': [self._get_status_color(status) for status in status_counts.keys()]
                }]
            }

    @api.depends('submission_date')
    def _compute_submission_timeline(self):
        """Compute submission timeline for line chart"""
        domain = self._get_dashboard_domain()
        candidates = self.env['admission.candidate'].search(domain)
        
        # Group by month
        timeline_data = {}
        for candidate in candidates:
            month = candidate.submission_date.strftime('%Y-%m')
            timeline_data[month] = timeline_data.get(month, 0) + 1
        
        # Sort by month
        sorted_months = sorted(timeline_data.keys())
        
        for record in self:
            record.submission_timeline = {
                'labels': sorted_months,
                'datasets': [{
                    'label': 'Candidatures',
                    'data': [timeline_data[month] for month in sorted_months],
                    'borderColor': '#2196F3',
                    'fill': False
                }]
            }

    @api.depends('form_id')
    def _compute_form_distribution(self):
        """Compute form distribution for bar chart"""
        domain = self._get_dashboard_domain()
        candidates = self.env['admission.candidate'].search(domain)
        
        form_counts = {}
        for candidate in candidates:
            form_name = candidate.form_id.name
            form_counts[form_name] = form_counts.get(form_name, 0) + 1
        
        for record in self:
            record.form_distribution = {
                'labels': list(form_counts.keys()),
                'datasets': [{
                    'label': 'Candidatures par Formulaire',
                    'data': list(form_counts.values()),
                    'backgroundColor': '#4CAF50'
                }]
            }

    @api.depends('academic_level')
    def _compute_academic_level_distribution(self):
        """Compute academic level distribution for bar chart"""
        domain = self._get_dashboard_domain()
        candidates = self.env['admission.candidate'].search(domain)
        
        level_counts = {}
        level_labels = dict(self._fields['academic_level'].selection)
        
        for level, _ in self._fields['academic_level'].selection:
            count = len(candidates.filtered(lambda r: r.academic_level == level))
            if count > 0:  # Only include non-zero counts
                level_counts[level_labels[level]] = count
        
        for record in self:
            record.academic_level_distribution = {
                'labels': list(level_counts.keys()),
                'datasets': [{
                    'label': 'Distribution par Niveau',
                    'data': list(level_counts.values()),
                    'backgroundColor': '#FF9800'
                }]
            } 