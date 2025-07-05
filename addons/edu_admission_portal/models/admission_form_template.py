# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
import json
import re
import base64
import traceback
from odoo.http import request

_logger = logging.getLogger(__name__)

class AdmissionFormTemplate(models.Model):
    _name = 'admission.form.template'
    _description = "Template de Formulaire d'Admission"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )
    sid = fields.Char(
        string='ID LimeSurvey',
        required=True,
        readonly=True,
        tracking=True,
        help="Identifiant unique du formulaire dans LimeSurvey",
    )
    title = fields.Char(
        string='Titre',
        required=True,
        readonly=True,
        tracking=True,
        help="Titre du formulaire tel que défini dans LimeSurvey",
    )
    description = fields.Html(
        string='Description',
        tracking=True,
        sanitize=True,
        strip_style=True,
    )
    is_active = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True,
        help="Indique si le formulaire est actif dans LimeSurvey",
    )
    owner = fields.Char(
        string='Propriétaire',
        tracking=True,
        help="ID du propriétaire dans LimeSurvey",
    )
    sync_status = fields.Selection([
        ('draft', 'Brouillon'),
        ('synced', 'Synchronisé'),
        ('error', 'Erreur'),
    ], string='Statut', default='draft', tracking=True)
    server_config_id = fields.Many2one(
        'limesurvey.server.config',
        string='Serveur LimeSurvey',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    last_sync_date = fields.Datetime(
        string='Dernière Synchronisation',
        tracking=True,
    )
    candidate_ids = fields.One2many(
        'admission.candidate',
        'form_id',
        string='Candidats liés'
    )
    candidate_count = fields.Integer(
        string='Nombre de Candidats',
        compute='_compute_candidate_count',
        store=True,
    )
    field_mapping = fields.Text(
        string='Structure des Champs',
        help="Structure JSON des champs du formulaire LimeSurvey",
        readonly=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )
    metadata = fields.Json(
        string='Métadonnées',
        help="Stockage des métadonnées additionnelles du formulaire",
    )
    survey_url = fields.Char(
        string='URL du Formulaire',
        compute='_compute_survey_url',
    )
    question_count = fields.Integer(
        string='Nombre de Questions',
        readonly=True,
    )

    # Champs pour la création automatique
    auto_create_candidates = fields.Boolean(
        string='Création Automatique des Candidats',
        default=False,
        tracking=True,
        help="Si activé, les candidats seront créés automatiquement lors de la soumission du formulaire",
    )
    
    mapping_validated = fields.Boolean(
        string='Mapping Validé',
        default=False,
        tracking=True,
        help="Indique si le mapping a été validé et est prêt pour la création automatique",
    )
    
    auto_create_status = fields.Selection([
        ('disabled', 'Désactivé'),
        ('enabled', 'Activé'),
        ('paused', 'En Pause'),
    ], string='Statut Auto-Création',
        default='disabled',
        tracking=True,
        help="Statut de la création automatique des candidats",
    )
    
    last_candidate_creation = fields.Datetime(
        string='Dernière Création de Candidat',
        tracking=True,
    )
    
    total_auto_created = fields.Integer(
        string='Total Auto-Créés',
        default=0,
        tracking=True,
        help="Nombre total de candidats créés automatiquement",
    )

    _sql_constraints = [
        ('sid_server_uniq', 'unique(sid,server_config_id)', 
         'Un formulaire avec cet ID existe déjà pour ce serveur!')
    ]

    def _process_survey_response(self, response_data):
        """Traite les réponses du sondage en utilisant le mapping configuré."""
        _logger.info(f"Traitement des données de réponse: {response_data}")
        processed = {}

        # Récupération du mapping validé
        mapping = self.env['admission.form.mapping'].search([
            ('form_template_id', '=', self.id),
            ('state', '=', 'validated')
        ], limit=1)

        if not mapping:
            _logger.warning(
                "Aucun mapping validé trouvé pour le formulaire %s",
                self.name
            )
            return response_data

        # Pour chaque ligne de mapping
        for line in mapping.mapping_line_ids.filtered(lambda l: l.status == 'validated'):
            try:
                # Récupération de la valeur source
                value = response_data.get(line.question_code)
                
                if value is None:
                    continue

                # Si c'est une pièce jointe
                if line.is_attachment and isinstance(value, dict):
                    processed[line.question_code] = value
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
                    processed[line.odoo_field] = value
                else:
                    processed[line.question_code] = value
            
            except Exception as e:
                _logger.error(
                    "Erreur lors du traitement de la ligne %s: %s",
                    line.question_code, str(e)
                )
                continue

        _logger.info(f"Données traitées: {processed}")
        return processed

    def _process_limesurvey_value(self, value):
        """Traite une valeur provenant de LimeSurvey."""
        if not isinstance(value, str):
            return value

        # Traitement des valeurs booléennes Y/N
        if value.upper() in ['Y', 'N']:
            return value  # Retourne directement 'Y' ou 'N' sans conversion en booléen

        # Traitement des valeurs numériques
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        return value

    def _map_question_type(self, limesurvey_type):
        """Mappe les types de questions LimeSurvey vers les types Odoo."""
        mapping = {
            'S': 'text',      # Short free text
            'T': 'text',      # Long free text
            'U': 'text',      # Huge free text
            'N': 'numeric',   # Numerical input
            'K': 'numeric',   # Multiple numerical input
            'D': 'date',      # Date/Time
            'L': 'choice',    # List (radio)
            'O': 'choice',    # List with comment
            'R': 'choice',    # Ranking
            '!': 'choice',    # List (dropdown)
            'M': 'multiple',  # Multiple choice
            'P': 'multiple',  # Multiple choice with comments
            '|': 'upload',    # File upload
            '*': 'upload',    # Equation
            'Y': 'choice',    # Yes/No
            ';': 'text',      # Array questions
            'X': 'text',      # Boilerplate text
        }
        return mapping.get(limesurvey_type, 'text')

    def _get_is_required(self, question):
        """Détermine si une question est requise."""
        mandatory = question.get('mandatory', False)
        if isinstance(mandatory, str):
            return mandatory.upper() == 'Y'
        return bool(mandatory)

    def _get_is_attachment(self, question):
        """Détermine si une question est une pièce jointe."""
        question_type = question.get('type', '')
        return question_type in ['|', '*']  # Types pour upload de fichiers

    @api.depends('title', 'sid')
    def _compute_name(self):
        """Génère un nom unique pour le template."""
        for template in self:
            template.name = f"{template.title} [{template.sid}]"

    @api.depends('server_config_id', 'sid')
    def _compute_survey_url(self):
        """Calcule l'URL du formulaire."""
        for record in self:
            if record.sid and record.server_config_id:
                # Utilise la fonction de nettoyage d'URL avec le type 'survey'
                url = f"{record.server_config_id.base_url}/index.php/{record.sid}?lang=fr"
                record.survey_url = self.env['limesurvey.server.config'].clean_limesurvey_url(url, 'survey')
            else:
                record.survey_url = ''

    @api.depends('candidate_ids')
    def _compute_candidate_count(self):
        """Calcule le nombre de candidats pour ce formulaire."""
        for template in self:
            template.candidate_count = len(template.candidate_ids)

    @api.model
    def _clean_html_text(self, html_text):
        """Nettoie les balises HTML d'un texte."""
        if not html_text:
            return ''
        
        import re
        
        # Suppression des balises HTML
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        
        # Remplacement des entités HTML courantes
        html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&eacute;': 'é',
            '&egrave;': 'è',
            '&agrave;': 'à',
            '&ccedil;': 'ç',
            '&uacute;': 'ú',
            '&oacute;': 'ó',
            '&iacute;': 'í',
            '&aacute;': 'á',
            '&ntilde;': 'ñ',
        }
        
        for entity, char in html_entities.items():
            clean_text = clean_text.replace(entity, char)
        
        # Suppression des espaces multiples et des sauts de ligne
        clean_text = re.sub(r'\s+', ' ', clean_text)
        clean_text = clean_text.strip()
        
        return clean_text

    @api.model
    def _create_default_mappings(self, questions_data):
        """Crée les mappings par défaut pour les champs du formulaire."""
        try:
            # Traitement direct des questions si c'est une liste
            if isinstance(questions_data, list):
                questions = questions_data
            else:
                # Si ce n'est pas une liste, essayer de parser JSON
                if isinstance(questions_data, str):
                    try:
                        parsed_data = json.loads(questions_data)
                        if isinstance(parsed_data, list):
                            questions = parsed_data
                        elif isinstance(parsed_data, dict) and 'questions' in parsed_data:
                            questions = parsed_data['questions']
                        else:
                            questions = parsed_data
                    except json.JSONDecodeError:
                        raise ValidationError(_("Le format des données de questions est invalide (JSON invalide)"))
                else:
                    questions = questions_data

            if not questions:
                _logger.warning("Aucune question à traiter pour le mapping")
                return None

            # Création du mapping principal
            mapping = self.env['admission.form.mapping'].create({
                'form_template_id': self.id,
                'name': f"Mapping - {self.title or self.sid}",
                'state': 'draft',
                'notes': f'Mapping généré automatiquement pour {self.title or self.sid}',
            })

            # Création des lignes de mapping
            for idx, question in enumerate(questions, 1):
                if not isinstance(question, dict):
                    _logger.warning("Question ignorée: format invalide - %s", question)
                    continue

                # Récupération des données de la question avec différents noms possibles
                code = question.get('title') or question.get('code') or question.get('qid', f'Q{idx}')
                question_text = question.get('question') or question.get('text', '')
                question_type = question.get('type', 'T')
                
                # Déterminer si c'est une pièce jointe
                is_attachment = question_type in ['|', '*']
                
                # Déterminer si c'est requis
                mandatory = question.get('mandatory', False)
                if isinstance(mandatory, str):
                    is_required = mandatory.upper() == 'Y'
                else:
                    is_required = bool(mandatory)

                # Préparation des valeurs de la ligne
                line_vals = {
                    'mapping_id': mapping.id,
                    'sequence': idx,
                    'question_code': code,
                    'question_text': self._clean_html_text(question_text),
                    'question_type': self._map_question_type(question_type),
                    'is_required': is_required,
                    'is_attachment': is_attachment,
                    'group_name': question.get('group_name', ''),
                    'attributes': json.dumps(question.get('attributes', {})),
                    'status': 'draft',
                    'odoo_field': '',  # À mapper manuellement par l'utilisateur
                    'confidence_score': 0,
                }

                # Création de la ligne
                self.env['admission.mapping.line'].create(line_vals)

            _logger.info("Mapping créé avec %d lignes pour le formulaire %s", len(questions), self.sid)
            return mapping

        except Exception as e:
            _logger.error(
                "Erreur lors de la création des mappings: %s\n%s",
                str(e), traceback.format_exc()
            )
            raise ValidationError(_(
                "Erreur lors de la création des mappings.\n\n"
                "Détail : %s"
            ) % str(e))

    def action_generate_mappings(self):
        """Action pour générer/régénérer les mappings."""
        self.ensure_one()
        if not self.field_mapping:
            raise UserError(_("Veuillez d'abord synchroniser le formulaire avec LimeSurvey."))
        
        try:
            fields_data = json.loads(self.field_mapping)
            self._create_default_mappings(fields_data)
        except Exception as e:
            raise UserError(_("Erreur lors de la génération des mappings: %s") % str(e))

    def action_view_candidates(self):
        """Ouvre la vue des candidats liés à ce formulaire."""
        self.ensure_one()
        return {
            'name': _('Candidats'),
            'type': 'ir.actions.act_window',
            'res_model': 'admission.candidate',
            'view_mode': 'kanban,tree,form',
            'domain': [('form_id', '=', self.id)],
            'context': {'default_form_id': self.id},
            'target': 'current',
        }

    def action_open_form_url(self):
        """Ouvre l'URL du formulaire dans une nouvelle fenêtre."""
        self.ensure_one()
        if not self.survey_url:
            raise UserError(_("L'URL du formulaire n'est pas disponible."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': self.survey_url,
            'target': 'new',
        }

    def action_import_responses(self):
        """Importe les réponses du formulaire et crée les fiches candidats."""
        self.ensure_one()
        
        # Vérification du serveur
        if not self.server_config_id:
            raise UserError(_("Veuillez configurer un serveur LimeSurvey pour ce formulaire."))

        # Vérification du mapping
        mapping = self.env['admission.form.mapping'].search([
            ('form_template_id', '=', self.id),
            ('state', '=', 'validated')
        ], limit=1)

        if not mapping:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration requise'),
                    'message': _('Aucun mapping validé trouvé. Veuillez d\'abord configurer et valider le mapping des champs.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        try:
            # Récupération des réponses depuis LimeSurvey
            responses = self.server_config_id.get_survey_responses(self.sid)
            
            # Vérification si des réponses ont été trouvées
            if responses is None:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Erreur de Connexion'),
                        'message': _('Impossible de récupérer les réponses. Vérifiez la connexion au serveur LimeSurvey.'),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            
            if not responses:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Information'),
                        'message': _('Aucune nouvelle réponse à importer pour ce formulaire.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }

            # Compteurs pour le rapport
            stats = {
                'total': len(responses),
                'imported': 0,
                'skipped': 0,
                'errors': 0,
                'error_details': []
            }

            # Création d'un lot d'import pour le suivi
            import_batch = self.env['admission.import.batch'].create({
                'form_template_id': self.id,
                'start_date': fields.Datetime.now(),
                'state': 'running'
            })

            for response in responses:
                try:
                    # Vérification si la réponse existe déjà
                    existing = self.env['admission.candidate'].search([
                        ('form_id', '=', self.id),
                        ('response_id', '=', str(response.get('id')))
                    ], limit=1)

                    if existing:
                        _logger.info(
                            "Réponse déjà existante - Form: %s, Response: %s",
                            self.sid, response.get('id')
                        )
                        stats['skipped'] += 1
                        continue

                    # Traitement des données de la réponse
                    processed_data = self._process_survey_response(response.get('answers', {}))
                    if not processed_data:
                        stats['errors'] += 1
                        stats['error_details'].append(
                            f"Réponse {response.get('id')}: Données invalides après traitement"
                        )
                        continue

                    # Création du candidat
                    candidate_vals = {
                        'form_id': self.id,
                        'response_id': str(response.get('id')),
                        'submission_date': response.get('submitdate'),
                        'import_batch_id': import_batch.id,
                        'status': 'new'
                    }
                    candidate_vals.update(processed_data)

                    candidate = self.env['admission.candidate'].create(candidate_vals)

                    # Traitement des pièces jointes
                    attachments = response.get('files', [])
                    if attachments:
                        self._process_response_attachments(candidate, attachments)

                    stats['imported'] += 1
                    _logger.info("Candidat créé avec succès - ID: %s", candidate.id)

                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f"Réponse {response.get('id')}: {str(e)}"
                    stats['error_details'].append(error_msg)
                    _logger.error(
                        "Erreur lors du traitement de la réponse %s: %s",
                        response.get('id'), str(e)
                    )
                    continue

            # Mise à jour du lot d'import
            import_batch.write({
                'end_date': fields.Datetime.now(),
                'state': 'done' if stats['errors'] == 0 else 'partial',
                'total_count': stats['total'],
                'imported_count': stats['imported'],
                'skipped_count': stats['skipped'],
                'error_count': stats['errors'],
                'error_details': '\n'.join(stats['error_details'])
            })

            # Mise à jour du template
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'sync_status': 'synced' if stats['errors'] == 0 else 'error'
            })

            # Message de succès
            message_parts = []
            if stats['imported'] > 0:
                message_parts.append(_("%d candidat(s) importé(s) avec succès") % stats['imported'])
            if stats['skipped'] > 0:
                message_parts.append(_("%d réponse(s) déjà importée(s)") % stats['skipped'])
            if stats['errors'] > 0:
                message_parts.append(_("%d erreur(s) lors de l'import") % stats['errors'])

            if not message_parts:
                message = _("Aucun nouveau candidat importé")
            else:
                message = "\n".join(message_parts)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import Terminé'),
                    'message': message,
                    'type': 'success' if stats['errors'] == 0 else 'warning',
                    'sticky': True,
                    'next': {
                        'type': 'ir.actions.act_window',
                        'name': _('Résultats de l\'import'),
                        'res_model': 'admission.import.batch',
                        'res_id': import_batch.id,
                        'view_mode': 'form',
                        'target': 'new',
                    }
                }
            }

        except Exception as e:
            self.sync_status = 'error'
            raise UserError(_(
                "Erreur lors de l'import des réponses.\n\n"
                "Vérifiez que :\n"
                "1. Le formulaire est correctement configuré\n"
                "2. Le serveur LimeSurvey est accessible\n"
                "3. Les mappings sont correctement définis\n"
                "4. Vous avez les droits nécessaires\n\n"
                "Détail de l'erreur : %s"
            ) % str(e))

    def _process_response_attachments(self, candidate, attachments):
        """Traite les pièces jointes d'une réponse."""
        for attachment in attachments:
            try:
                # Création de la pièce jointe
                attachment_vals = {
                    'name': attachment.get('name', 'Sans nom'),
                    'datas': attachment.get('content'),
                    'mimetype': attachment.get('type', 'application/octet-stream'),
                    'res_model': 'admission.candidate',
                    'res_id': candidate.id,
                }

                attachment_id = self.env['ir.attachment'].create(attachment_vals)
                candidate.write({
                    'attachment_ids': [(4, attachment_id.id)]
                })

            except Exception as e:
                _logger.error(
                    "Erreur lors de la création de la pièce jointe %s: %s",
                    attachment.get('name', 'unknown'), str(e)
                )

    def _get_survey_questions(self):
        """Récupère et traite les questions du formulaire LimeSurvey."""
        self.ensure_one()
        
        if not self.sid or not self.server_config_id:
            return []
            
        try:
            # Récupération des questions via l'API
            server = self.server_config_id._get_rpc_session()
            if not server:
                raise ValidationError(_("Impossible de se connecter au serveur LimeSurvey"))
                
            # Récupération des propriétés du sondage
            survey_properties = self.server_config_id.get_survey_properties(self.sid)
            if not survey_properties:
                raise ValidationError(_("Impossible de récupérer les propriétés du formulaire"))
                
            # Extraction et traitement des questions
            questions = []
            all_questions = survey_properties.get('questions', [])
            groups = survey_properties.get('groups', [])
            
            # Création d'un dictionnaire des groupes pour un accès rapide
            group_dict = {str(group['gid']): group.get('group_name', '') for group in groups}
            
            for question in all_questions:
                # Validation de base
                if not question.get('title') or not question.get('qid'):
                    continue
                    
                # Récupération du nom du groupe
                group_name = group_dict.get(str(question.get('gid', '')), '')
                
                # Construction de la structure de la question
                processed_question = {
                    'qid': str(question['qid']),
                    'code': question['title'],
                    'text': question.get('question', ''),
                    'type': question.get('type', ''),
                    'mandatory': question.get('mandatory', 'N') == 'Y',
                    'relevance': question.get('relevance', '1'),
                    'group_name': group_name,
                    'attributes': {}
                }
                
                # Traitement des attributs de la question
                attributes = question.get('attributes', {})
                if isinstance(attributes, dict):
                    processed_question['attributes'] = {
                        k: v for k, v in attributes.items()
                        if isinstance(k, str) and v is not None
                    }
                
                # Traitement des sous-questions
                subquestions = []
                for subq in question.get('subquestions', []):
                    if not subq.get('title') or not subq.get('qid'):
                        continue
                        
                    subquestions.append({
                        'qid': str(subq['qid']),
                        'code': subq['title'],
                        'text': subq.get('question', ''),
                        'relevance': subq.get('relevance', '1')
                    })
                
                if subquestions:
                    processed_question['subquestions'] = subquestions
                
                # Traitement des options de réponse
                answers = []
                for answer in question.get('answeroptions', []):
                    if not answer.get('code'):
                        continue
                        
                    answers.append({
                        'code': answer['code'],
                        'text': answer.get('answer', ''),
                        'assessment_value': answer.get('assessment_value', 0)
                    })
                
                if answers:
                    processed_question['answers'] = answers
                
                questions.append(processed_question)
            
            _logger.info("Questions récupérées avec succès: %s", questions)
            return questions
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la récupération des questions du formulaire %s: %s\n%s",
                self.sid, str(e), traceback.format_exc()
            )
            raise ValidationError(_(
                "Erreur lors de la récupération des questions du formulaire: %s"
            ) % str(e))

    def action_sync_questions(self):
        """Synchronise les questions du formulaire avec LimeSurvey."""
        self.ensure_one()
        
        try:
            # Récupération des questions
            questions = self._get_survey_questions()
            if not questions:
                raise ValidationError(_("Aucune question trouvée dans le formulaire"))
                
            # Mise à jour des questions dans le mapping
            mapping = self.env['admission.form.mapping'].search([
                ('form_template_id', '=', self.id),
                ('state', '=', 'draft')
            ], limit=1)
            
            if not mapping:
                # Création d'un nouveau mapping
                mapping = self.env['admission.form.mapping'].create({
                    'form_template_id': self.id,
                    'name': f"Mapping {self.name}",
                    'state': 'draft'
                })
            
            # Mise à jour ou création des lignes de mapping
            existing_lines = {
                line.question_code: line
                for line in mapping.mapping_line_ids
            }
            
            for question in questions:
                line_vals = {
                    'question_code': question['code'],
                    'question_text': question['text'],
                    'question_type': self._map_question_type(question['type']),
                    'is_required': question['mandatory'],
                    'group_name': question['group_name'],
                    'attributes': json.dumps(question['attributes']),
                    'status': 'draft'
                }
                
                if question['code'] in existing_lines:
                    # Mise à jour de la ligne existante
                    line = existing_lines[question['code']]
                    if line.status != 'validated':
                        line.write(line_vals)
                else:
                    # Création d'une nouvelle ligne
                    line_vals.update({
                        'mapping_id': mapping.id,
                        'sequence': len(existing_lines) + 1
                    })
                    self.env['admission.mapping.line'].create(line_vals)
            
            # Mise à jour de la date de synchronisation
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'question_count': len(questions)
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Synchronisation réussie"),
                    'message': _(
                        "%d questions ont été synchronisées avec succès"
                    ) % len(questions),
                    'sticky': False,
                    'type': 'success'
                }
            }
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la synchronisation des questions: %s\n%s",
                str(e), traceback.format_exc()
            )
            raise ValidationError(_(
                "Erreur lors de la synchronisation des questions: %s"
            ) % str(e))

    def action_sync_form(self):
        """Synchronise le formulaire avec LimeSurvey."""
        self.ensure_one()
        try:
            # Synchronisation avec le serveur LimeSurvey
            sync_data = self.server_config_id.sync_specific_form(self.sid)
            
            # Mise à jour du template avec les données synchronisées
            vals = {
                'title': sync_data['title'],
                'description': sync_data['description'],
                'is_active': sync_data['is_active'],
                'owner': sync_data['owner'],
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
                'metadata': sync_data['metadata'],
                'field_mapping': json.dumps(sync_data['questions']),
            }
            self.write(vals)
            
            # Génération automatique des mappings si des questions existent
            if sync_data['questions']:
                self._create_default_mappings(sync_data['questions'])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Formulaire synchronisé avec succès.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation: %s", str(e))
            self.write({'sync_status': 'error'})
            raise UserError(_("Erreur lors de la synchronisation: %s") % str(e))

    def action_enable_auto_creation(self):
        """Active la création automatique des candidats."""
        self.ensure_one()
        
        # Vérification que le mapping est validé
        if not self.mapping_validated:
            raise ValidationError(_(
                "Le mapping doit être validé avant d'activer la création automatique.\n"
                "Veuillez d'abord valider le mapping dans l'onglet 'Mappings de Formulaire'."
            ))
        
        # Vérification qu'il existe des mappings validés
        validated_mappings = self.env['admission.form.mapping'].search([
            ('form_template_id', '=', self.id),
            ('state', '=', 'validated')
        ])
        
        if not validated_mappings:
            raise ValidationError(_(
                "Aucun mapping validé trouvé.\n"
                "Veuillez d'abord créer et valider un mapping."
            ))
        
        self.write({
            'auto_create_candidates': True,
            'auto_create_status': 'enabled',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Création automatique des candidats activée !'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_disable_auto_creation(self):
        """Désactive la création automatique des candidats."""
        self.ensure_one()
        
        self.write({
            'auto_create_candidates': False,
            'auto_create_status': 'disabled',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Information'),
                'message': _('Création automatique des candidats désactivée.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_pause_auto_creation(self):
        """Met en pause la création automatique des candidats."""
        self.ensure_one()
        
        self.write({
            'auto_create_status': 'paused',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Information'),
                'message': _('Création automatique des candidats mise en pause.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_resume_auto_creation(self):
        """Reprend la création automatique des candidats."""
        self.ensure_one()
        
        self.write({
            'auto_create_status': 'enabled',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Création automatique des candidats reprise.'),
                'type': 'success',
                'sticky': False,
            }
        } 

    def action_diagnose_auto_creation(self):
        """Diagnostique pourquoi la création automatique ne fonctionne pas."""
        self.ensure_one()
        
        issues = []
        status = "success"
        
        # Vérification 1: Mapping validé
        validated_mappings = self.env['admission.form.mapping'].search([
            ('form_template_id', '=', self.id),
            ('state', '=', 'validated')
        ])
        
        if not validated_mappings:
            issues.append("❌ Aucun mapping validé trouvé")
            status = "error"
        else:
            issues.append(f"✅ {len(validated_mappings)} mapping(s) validé(s)")
        
        # Vérification 2: Lignes de mapping validées
        if validated_mappings:
            mapping = validated_mappings[0]
            validated_lines = mapping.mapping_line_ids.filtered(lambda l: l.status == 'validated')
            total_lines = len(mapping.mapping_line_ids)
            
            if not validated_lines:
                issues.append("❌ Aucune ligne de mapping validée")
                status = "error"
            else:
                issues.append(f"✅ {len(validated_lines)}/{total_lines} lignes validées")
        
        # Vérification 3: Création automatique activée
        if not self.auto_create_candidates:
            issues.append("❌ Création automatique désactivée")
            status = "error"
        else:
            issues.append("✅ Création automatique activée")
        
        # Vérification 4: Statut de création automatique
        if self.auto_create_status != 'enabled':
            issues.append(f"❌ Statut auto-création: {self.auto_create_status}")
            status = "error"
        else:
            issues.append("✅ Statut auto-création: Activé")
        
        # Vérification 5: Mapping validé dans le template
        if not self.mapping_validated:
            issues.append("❌ Mapping non marqué comme validé dans le template")
            status = "error"
        else:
            issues.append("✅ Mapping marqué comme validé")
        
        # Vérification 6: URL du webhook
        webhook_url = f"{request.httprequest.host_url.rstrip('/')}/admission/webhook/submit"
        issues.append(f"🔗 URL Webhook: {webhook_url}")
        
        # Vérification 7: Token du webhook
        if self.server_config_id.webhook_token:
            issues.append("✅ Token webhook configuré")
        else:
            issues.append("❌ Token webhook manquant")
            status = "error"
        
        # Vérification 8: Test de récupération des réponses
        try:
            if self.server_config_id:
                responses = self.server_config_id.get_survey_responses(self.sid)
                if responses is not None:
                    if responses:
                        issues.append(f"✅ {len(responses)} réponses disponibles")
                    else:
                        issues.append("✅ Aucune réponse disponible (normal si le formulaire est vide)")
                else:
                    issues.append("❌ Impossible de récupérer les réponses")
                    status = "error"
        except Exception as e:
            issues.append(f"❌ Erreur lors du test de récupération: {str(e)}")
            status = "error"
        
        # Message de diagnostic
        message = "\n".join(issues)
        
        if status == "error":
            message += "\n\n🔧 Actions recommandées:\n"
            message += "1. Valider le mapping dans l'onglet 'Mappings de Formulaire'\n"
            message += "2. Activer la création automatique\n"
            message += "3. Configurer le webhook dans LimeSurvey\n"
            message += "4. Vérifier le token webhook\n"
            message += "5. Tester la connexion au serveur LimeSurvey"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Diagnostic Création Automatique'),
                'message': message,
                'type': status,
                'sticky': True,
            }
        } 