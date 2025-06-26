import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import xmlrpc.client
import json
import base64
import traceback
import csv
from io import StringIO
import itertools

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
        tracking=True,
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
    form_url = fields.Char(
        string='URL du Formulaire',
        compute='_compute_form_url',
    )
    metadata = fields.Json(
        string='Métadonnées',
        help="Stockage des métadonnées additionnelles du formulaire",
    )
    default_token = fields.Char(
        string='Code d\'accès par défaut',
        readonly=True,
        copy=False,
        help='Code d\'accès par défaut pour ce formulaire',
    )

    _sql_constraints = [
        ('sid_server_uniq', 'unique(sid,server_config_id)', 
         'Un formulaire avec cet ID existe déjà pour ce serveur!')
    ]

    @api.depends('title', 'sid')
    def _compute_name(self):
        """Génère un nom unique pour le template."""
        for template in self:
            template.name = f"{template.title} [{template.sid}]"

    @api.depends('server_config_id', 'sid')
    def _compute_form_url(self):
        """Calcule l'URL publique du formulaire."""
        for template in self:
            if template.server_config_id and template.sid:
                # Nettoyage de l'URL de base
                base_url = template.server_config_id.base_url.rstrip('/')
                # Suppression de /admin/remotecontrol s'il est présent
                base_url = base_url.replace('/admin/remotecontrol', '')
                # Suppression des index.php multiples
                base_url = base_url.replace('/index.php/index.php', '/index.php')
                # Si l'URL ne contient pas encore index.php, l'ajouter
                if '/index.php' not in base_url:
                    base_url = f"{base_url}/index.php"
                # Construction de l'URL correcte du formulaire (format public)
                template.form_url = f"{base_url}/survey/index/{template.sid}?lang=fr"
            else:
                template.form_url = False

    @api.depends('candidate_ids')
    def _compute_candidate_count(self):
        """Calcule le nombre de candidats pour ce formulaire."""
        for template in self:
            template.candidate_count = self.env['admission.candidate'].search_count([
                ('form_id', '=', template.id)
            ])

    def action_sync_form(self):
        """Synchronise les métadonnées du formulaire depuis LimeSurvey."""
        self.ensure_one()
        server, session_key = self.server_config_id._get_rpc_session()

        try:
            # Conversion de l'ID en entier
            survey_id = int(self.sid)
            _logger.info("Tentative de synchronisation du formulaire %s", survey_id)

            # Liste des propriétés à récupérer
            properties = [
                'active', 'expires', 'startdate', 'attributedescriptions',
                'language', 'additional_languages', 'surveyls_title',
                'surveyls_description'
            ]

            # Appel avec la signature correcte :
            # get_survey_properties(string $sSessionKey, int $iSurveyID, array|null $aSurveySettings)
            survey_properties = server.get_survey_properties(session_key, survey_id, properties)

            if not survey_properties:
                _logger.error("Aucune propriété retournée pour le formulaire %s", survey_id)
                raise UserError(_("Formulaire non trouvé sur le serveur LimeSurvey"))

            _logger.info("Propriétés reçues pour le formulaire %s: %s", survey_id, survey_properties)

            # Mise à jour des métadonnées
            self.write({
                'title': survey_properties.get('surveyls_title', self.title),
                'description': survey_properties.get('surveyls_description'),
                'is_active': survey_properties.get('active') == 'Y',
                'metadata': survey_properties,
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
            })

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

        except xmlrpc.client.Fault as e:
            _logger.error(
                "Erreur RPC lors de la synchronisation du formulaire %s: [%s] %s",
                self.sid, getattr(e, 'faultCode', 'N/A'), str(e)
            )
            self.sync_status = 'error'
            raise UserError(_(
                "Erreur lors de la synchronisation avec LimeSurvey:\n\n"
                "Code: %s\n"
                "Message: %s"
            ) % (getattr(e, 'faultCode', 'N/A'), str(e)))

        except Exception as e:
            _logger.error(
                "Erreur inattendue lors de la synchronisation du formulaire %s: %s",
                self.sid, str(e)
            )
            self.sync_status = 'error'
            raise UserError(_("Erreur inattendue lors de la synchronisation: %s") % str(e))

    def action_view_candidates(self):
        """Ouvre la vue des candidats pour ce formulaire."""
        self.ensure_one()
        return {
            'name': _('Candidats'),
            'type': 'ir.actions.act_window',
            'res_model': 'admission.candidate',
            'view_mode': 'kanban,tree,form',
            'domain': [('form_id', '=', self.id)],
            'context': {'default_form_id': self.id},
        }

    def action_open_form_url(self):
        """Ouvre l'URL du formulaire dans un nouvel onglet."""
        self.ensure_one()
        if not self.form_url:
            raise UserError(_("URL du formulaire non disponible"))
            
        return {
            'type': 'ir.actions.act_url',
            'url': self.form_url,
            'target': 'new',
        }

    @api.model
    def sync_all_forms(self):
        """Synchronize all active forms with LimeSurvey.
        This method is called by the scheduled action.
        """
        forms = self.search([('active', '=', True)])
        for form in forms:
            try:
                form.sync_from_limesurvey()
            except Exception as e:
                _logger.error("Failed to sync form %s: %s", form.name, str(e))
        return True

    @api.model
    def create(self, vals):
        """Surcharge de la création pour s'assurer que le template est actif si le serveur l'est."""
        template = super(AdmissionFormTemplate, self).create(vals)
        if template.server_config_id and not template.server_config_id.active:
            template.active = False
        return template

    @api.onchange('server_config_id')
    def _onchange_server_config(self):
        """Met à jour le statut actif en fonction du serveur."""
        if self.server_config_id:
            self.active = self.server_config_id.active 

    def action_import_responses(self):
        """Import responses from LimeSurvey."""
        self.ensure_one()
        
        if not self.sid:
            raise UserError(_("Veuillez d'abord configurer l'ID du questionnaire LimeSurvey."))
            
        if not self.server_config_id:
            raise UserError(_("Veuillez d'abord configurer le serveur LimeSurvey."))
            
        _logger.info("🚀 Début de l'importation des réponses pour le formulaire %s (SID: %s)", self.name, self.sid)
        _logger.info("📡 Serveur LimeSurvey: %s", self.server_config_id.base_url)
            
        try:
            # Connexion à LimeSurvey
            _logger.info("🔑 Tentative de connexion à LimeSurvey...")
            server, session_key = self.server_config_id._get_rpc_session()
            _logger.info("✅ Connexion établie avec succès")
            
            try:
                # Conversion de l'ID en entier
                survey_id = int(self.sid)
                _logger.info("🔄 Tentative d'export des réponses au format CSV...")
                
                # Récupération des réponses
                _logger.info("Appel de export_responses avec session_key=%s, survey_id=%s", session_key, survey_id)
                responses = server.export_responses(session_key, survey_id, 'csv')
                _logger.info("Type de réponse: %s", type(responses))
                _logger.info("Réponse reçue: %s", responses[:1000] if responses else None)
                
                if not responses:
                    _logger.warning("❌ Aucune réponse reçue du serveur")
                    raise UserError(_("Aucune réponse n'a été reçue du serveur LimeSurvey."))
                
                # Décodage et analyse des réponses
                if isinstance(responses, str):
                    try:
                        _logger.info("📝 Décodage du contenu base64...")
                        csv_content = base64.b64decode(responses).decode('utf-8')
                        _logger.info("CSV décodé: %s", csv_content[:1000])
                        
                        # Conversion du CSV en liste de dictionnaires
                        csv_file = StringIO(csv_content)
                        
                        # Détecter le délimiteur (virgule ou point-virgule)
                        sample_line = csv_content.split('\n')[0]
                        delimiter = ';' if ';' in sample_line else ','
                        _logger.info("Délimiteur détecté: %s", delimiter)
                        
                        # Si les colonnes commencent par des guillemets, les extraire directement
                        if sample_line.startswith('"'):
                            header_line = sample_line.strip()
                            # Enlever les guillemets au début et à la fin
                            if header_line.startswith('"') and header_line.endswith('"'):
                                header_line = header_line[1:-1]
                            # Séparer les colonnes et nettoyer
                            raw_columns = [col.strip().strip('"').strip() for col in header_line.split(delimiter)]
                            _logger.info("Colonnes extraites manuellement: %s", raw_columns)
                            
                            # Créer un nouveau contenu CSV avec les en-têtes nettoyés
                            new_csv_content = delimiter.join(raw_columns) + '\n'
                            new_csv_content += '\n'.join(csv_content.split('\n')[1:])
                            csv_file = StringIO(new_csv_content)
                        
                        reader = csv.DictReader(csv_file, delimiter=delimiter, quotechar='"')
                        rows = list(reader)
                        
                        _logger.info("Nombre de réponses: %d", len(rows))
                        if rows:
                            # Nettoyage des noms de colonnes
                            _logger.info("Colonnes avant nettoyage: %s", list(rows[0].keys()))
                            
                            # Créer un nouveau dictionnaire avec les clés nettoyées
                            cleaned_rows = []
                            for row in rows:
                                cleaned_row = {}
                                for key, value in row.items():
                                    # Nettoyer la clé
                                    clean_key = key.strip().strip('"').strip('\ufeff').strip(';').strip(',').strip()
                                    if clean_key:  # Ignorer les clés vides
                                        cleaned_row[clean_key] = value.strip() if value else value
                                cleaned_rows.append(cleaned_row)
                            
                            rows = cleaned_rows
                            columns = list(rows[0].keys()) if rows else []
                            _logger.info("Colonnes après nettoyage: %s", columns)
                            _logger.info("Première réponse après nettoyage: %s", rows[0] if rows else None)
                            
                            # Mapping des codes LimeSurvey vers nos champs
                            field_mapping = {
                                # Identifiants et métadonnées
                                'id': {
                                    'patterns': ['ID de la réponse', 'response_id', 'responseid', 'submitid', 'submission_id', 'id'],
                                    'type': 'id',
                                    'required': True
                                },
                                'token': {
                                    'patterns': ['token', 'Code d\'accès'],
                                    'type': 'char',
                                    'required': False
                                },
                                # Informations personnelles
                                'civility': {
                                    'patterns': ['G01Q01', 'Civilité'],
                                    'type': 'selection',
                                    'required': False
                                },
                                'last_name': {
                                    'patterns': ['G01Q02', 'Nom'],
                                    'type': 'char',
                                    'required': True
                                },
                                'first_name': {
                                    'patterns': ['G01Q03', 'Prénom'],
                                    'type': 'char',
                                    'required': True
                                },
                                'cin_number': {
                                    'patterns': ['G01Q04', 'Numéro CIN'],
                                    'type': 'char',
                                    'required': False
                                },
                                'massar_code': {
                                    'patterns': ['G01Q05', 'Code MASSAR'],
                                    'type': 'char',
                                    'required': False
                                },
                                'birth_city': {
                                    'patterns': ['G01Q06', 'Ville de naissance'],
                                    'type': 'char',
                                    'required': False
                                },
                                'birth_date': {
                                    'patterns': ['G01Q07', 'Date de naissance'],
                                    'type': 'date',
                                    'required': False
                                },
                                'birth_country': {
                                    'patterns': ['G01Q08', 'Pays de naissance'],
                                    'type': 'char',
                                    'required': False
                                },
                                'nationality': {
                                    'patterns': ['G01Q09', 'Nationalité'],
                                    'type': 'char',
                                    'required': False
                                },
                                'address': {
                                    'patterns': ['G01Q11', 'Adresse'],
                                    'type': 'text',
                                    'required': False
                                },
                                'postal_code': {
                                    'patterns': ['G01Q12', 'Code postal'],
                                    'type': 'char',
                                    'required': False
                                },
                                'residence_country': {
                                    'patterns': ['G02Q10', 'Pays de résidence'],
                                    'type': 'char',
                                    'required': False
                                },
                                'city': {
                                    'patterns': ['G02Q13', 'Ville'],
                                    'type': 'char',
                                    'required': False
                                },
                                'email': {
                                    'patterns': ['G03Q14', 'Adresse e-mail'],
                                    'type': 'email',
                                    'required': True
                                },
                                'phone': {
                                    'patterns': ['G03Q15', 'Numéro de téléphone'],
                                    'type': 'phone',
                                    'required': False
                                },
                                # Informations Bac
                                'bac_series': {
                                    'patterns': ['G04Q17', 'Série du Bac'],
                                    'type': 'char',
                                    'required': False
                                },
                                'bac_year': {
                                    'patterns': ['G04Q21', 'Année d\'obtention du Bac'],
                                    'type': 'integer',
                                    'required': False
                                },
                                'bac_school': {
                                    'patterns': ['G04Q22', 'Lycée'],
                                    'type': 'char',
                                    'required': False
                                },
                                'bac_country': {
                                    'patterns': ['G04Q23', 'Pays'],
                                    'type': 'char',
                                    'required': False
                                },
                                # Informations études supérieures
                                'university': {
                                    'patterns': ['G05Q25', 'Établissement Bac+2/3'],
                                    'type': 'char',
                                    'required': False
                                },
                                'degree_field': {
                                    'patterns': ['G05Q26', 'Filière'],
                                    'type': 'char',
                                    'required': False
                                },
                                'university_city': {
                                    'patterns': ['G05Q28', 'Ville établissement'],
                                    'type': 'char',
                                    'required': False
                                },
                                'degree_year': {
                                    'patterns': ['G01Q29', 'Année d\'obtention ou préparation du Bac+2'],
                                    'type': 'integer',
                                    'required': False
                                },
                                # Moyennes par année
                                'avg_year1': {
                                    'patterns': ['G01Q32[SQ001_SQ001]', 'Moyenne 1ère année'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_year2': {
                                    'patterns': ['G01Q32[SQ001_SQ002]', 'Moyenne 2ème année'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_year3': {
                                    'patterns': ['G01Q32[SQ001_SQ003]', 'Moyenne 3ème année'],
                                    'type': 'float',
                                    'required': False
                                },
                                # Moyennes par semestre
                                'avg_sem1': {
                                    'patterns': ['G05Q31[SQ001_SQ001]', 'Moyenne Semestre 1'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_sem2': {
                                    'patterns': ['G05Q31[SQ001_SQ002]', 'Moyenne Semestre 2'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_sem3': {
                                    'patterns': ['G05Q31[SQ001_SQ003]', 'Moyenne Semestre 3'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_sem4': {
                                    'patterns': ['G05Q31[SQ001_SQ004]', 'Moyenne Semestre 4'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_sem5': {
                                    'patterns': ['G05Q31[SQ001_SQ005]', 'Moyenne Semestre 5'],
                                    'type': 'float',
                                    'required': False
                                },
                                'avg_sem6': {
                                    'patterns': ['G05Q31[SQ001_SQ006]', 'Moyenne Semestre 6'],
                                    'type': 'float',
                                    'required': False
                                },
                                # Documents
                                'attestation_bac2': {
                                    'patterns': ['G01Q34', 'Attestation Bac+2'],
                                    'type': 'binary',
                                    'required': False
                                },
                                'attestation_bac3': {
                                    'patterns': ['G06Q35', 'Attestation Bac+3'],
                                    'type': 'binary',
                                    'required': False
                                },
                                'transcript_files': {
                                    'patterns': ['G06Q33', 'Relevés de notes S1 à S6'],
                                    'type': 'binary',
                                    'required': False
                                },
                                'other_documents': {
                                    'patterns': ['G06Q36', 'Autres documents utiles'],
                                    'type': 'binary',
                                    'required': False
                                },
                                'payment_proof': {
                                    'patterns': ['G07Q37', 'Justificatif de paiement'],
                                    'type': 'binary',
                                    'required': False
                                },
                                'declaration': {
                                    'patterns': ['G08Q39', 'Déclaration sur l\'honneur'],
                                    'type': 'boolean',
                                    'required': False
                                }
                            }

                            def normalize_column_name(col_name):
                                """Normalise un nom de colonne pour la comparaison."""
                                if not col_name:
                                    return ""
                                # Supprime les caractères spéciaux et la ponctuation
                                normalized = col_name.lower()
                                normalized = normalized.replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                                normalized = normalized.replace('à', 'a').replace('â', 'a')
                                normalized = normalized.replace('ô', 'o').replace('ö', 'o')
                                normalized = normalized.replace('ù', 'u').replace('û', 'u')
                                normalized = normalized.replace('ç', 'c')
                                # Supprime la ponctuation
                                normalized = normalized.replace(':', '').replace('"', '').replace('\'', '')
                                normalized = normalized.replace('[', '').replace(']', '')
                                normalized = normalized.replace('(', '').replace(')', '')
                                # Supprime les espaces multiples
                                normalized = ' '.join(normalized.split())
                                return normalized

                            def find_matching_column(patterns, columns):
                                """Trouve la colonne correspondante dans le CSV."""
                                normalized_columns = {normalize_column_name(col): col for col in columns}
                                
                                for pattern in patterns:
                                    normalized_pattern = normalize_column_name(pattern)
                                    # Correspondance exacte
                                    if normalized_pattern in normalized_columns:
                                        return normalized_columns[normalized_pattern]
                                    # Correspondance partielle pour les codes LimeSurvey (ex: G01Q01[SQ001])
                                    if pattern.startswith('G'):
                                        for norm_col, original_col in normalized_columns.items():
                                            if norm_col.startswith(normalized_pattern):
                                                return original_col
                                    # Correspondance partielle générale
                                    for norm_col, original_col in normalized_columns.items():
                                        if normalized_pattern in norm_col or norm_col in normalized_pattern:
                                            return original_col
                                return None

                            # Construction du mapping effectif
                            column_mapping = {}
                            missing_required = []
                            
                            _logger.info("=== Début du mapping des colonnes ===")
                            _logger.info("Colonnes disponibles dans le CSV: %s", columns)
                            
                            for field, config in field_mapping.items():
                                _logger.info("Recherche du champ '%s' avec patterns: %s", field, config['patterns'])
                                column = find_matching_column(config['patterns'], columns)
                                if column:
                                    column_mapping[field] = column
                                    _logger.info("✅ Champ '%s' mappé à la colonne '%s'", field, column)
                                elif config.get('required', False):
                                    missing_required.append(field)
                                    _logger.warning("❌ Champ requis '%s' non trouvé dans les colonnes", field)
                                else:
                                    _logger.info("ℹ️ Champ optionnel '%s' non trouvé", field)
                            
                            _logger.info("=== Résultat du mapping ===")
                            _logger.info("Mapping final: %s", column_mapping)
                            if missing_required:
                                _logger.error("Champs requis manquants: %s", missing_required)
                                raise UserError(_(
                                    "Champs obligatoires non trouvés dans le CSV : %s\n"
                                    "Colonnes disponibles : %s"
                                ) % (', '.join(missing_required), ', '.join(columns)))
                            
                            success_count = 0
                            error_count = 0
                            error_details = []
                            
                            for row in rows:
                                try:
                                    _logger.info("=== Traitement d'une nouvelle réponse ===")
                                    _logger.info("Données brutes de la réponse: %s", row)
                                    
                                    # Vérification des valeurs requises
                                    missing_values = []
                                    for field, mapped_column in column_mapping.items():
                                        if field_mapping[field].get('required', False):
                                            if not row.get(mapped_column):
                                                missing_values.append(field)
                                    
                                    if missing_values:
                                        error_msg = f"Valeurs manquantes pour les champs requis: {', '.join(missing_values)}"
                                        _logger.warning(error_msg)
                                        error_details.append(error_msg)
                                        error_count += 1
                                        continue
                                    
                                    # Création du candidat avec le mapping complet
                                    candidate_vals = {
                                        'form_id': self.id,
                                        'response_id': row.get(column_mapping['id']),
                                        'name': f"{row.get(column_mapping.get('first_name', ''), '')} {row.get(column_mapping.get('last_name', ''), '')}".strip(),
                                        'civility': row.get(column_mapping.get('civility', '')),
                                        'first_name': row.get(column_mapping.get('first_name', '')),
                                        'last_name': row.get(column_mapping.get('last_name', '')),
                                        'email': row.get(column_mapping.get('email', '')),
                                        'phone': row.get(column_mapping.get('phone', '')),
                                        'cin_number': row.get(column_mapping.get('cin_number', '')),
                                        'massar_code': row.get(column_mapping.get('massar_code', '')),
                                        'birth_city': row.get(column_mapping.get('birth_city', '')),
                                        'birth_date': row.get(column_mapping.get('birth_date', '')),
                                        'birth_country': row.get(column_mapping.get('birth_country', '')),
                                        'nationality': row.get(column_mapping.get('nationality', '')),
                                        'address': row.get(column_mapping.get('address', '')),
                                        'postal_code': row.get(column_mapping.get('postal_code', '')),
                                        'city': row.get(column_mapping.get('city', '')),
                                        'residence_country': row.get(column_mapping.get('residence_country', '')),
                                        
                                        # Informations Bac
                                        'bac_series': row.get(column_mapping.get('bac_series', '')),
                                        'bac_year': row.get(column_mapping.get('bac_year', '')),
                                        'bac_school': row.get(column_mapping.get('bac_school', '')),
                                        'bac_country': row.get(column_mapping.get('bac_country', '')),
                                        
                                        # Informations études supérieures
                                        'university': row.get(column_mapping.get('university', '')),
                                        'degree_field': row.get(column_mapping.get('degree_field', '')),
                                        'university_city': row.get(column_mapping.get('university_city', '')),
                                        'degree_year': row.get(column_mapping.get('degree_year', '')),
                                        
                                        # Moyennes
                                        'avg_year1': float(row.get(column_mapping.get('avg_year1', '0')) or 0),
                                        'avg_year2': float(row.get(column_mapping.get('avg_year2', '0')) or 0),
                                        'avg_year3': float(row.get(column_mapping.get('avg_year3', '0')) or 0),
                                        'avg_sem1': float(row.get(column_mapping.get('avg_sem1', '0')) or 0),
                                        'avg_sem2': float(row.get(column_mapping.get('avg_sem2', '0')) or 0),
                                        'avg_sem3': float(row.get(column_mapping.get('avg_sem3', '0')) or 0),
                                        'avg_sem4': float(row.get(column_mapping.get('avg_sem4', '0')) or 0),
                                        'avg_sem5': float(row.get(column_mapping.get('avg_sem5', '0')) or 0),
                                        'avg_sem6': float(row.get(column_mapping.get('avg_sem6', '0')) or 0),
                                        
                                        # Statut et données brutes
                                        'status': 'new',
                                        'response_data': json.dumps(row, ensure_ascii=False),
                                    }
                                    
                                    # Conversion des valeurs numériques
                                    for field in ['bac_year', 'degree_year']:
                                        if candidate_vals.get(field):
                                            try:
                                                candidate_vals[field] = int(candidate_vals[field])
                                            except (ValueError, TypeError):
                                                candidate_vals[field] = False
                                                _logger.warning("Impossible de convertir %s en entier: %s", field, candidate_vals[field])
                                    
                                    # Nettoyage des valeurs vides
                                    candidate_vals = {k: v for k, v in candidate_vals.items() if v not in [False, '', None, 0] or k in ['status', 'response_data']}
                                    
                                    _logger.info("Tentative de création du candidat avec: %s", candidate_vals)
                                    
                                    # Vérification de l'existence
                                    existing = self.env['admission.candidate'].search([
                                        ('response_id', '=', candidate_vals['response_id']),
                                        ('form_id', '=', self.id)
                                    ])
                                    
                                    if existing:
                                        error_msg = f"Candidat déjà existant avec l'ID: {candidate_vals['response_id']}"
                                        _logger.warning(error_msg)
                                        error_details.append(error_msg)
                                        error_count += 1
                                        continue
                                    
                                    # Création du candidat
                                    try:
                                        new_candidate = self.env['admission.candidate'].create(candidate_vals)
                                        _logger.info("✅ Candidat créé avec succès, ID: %s", new_candidate.id)
                                        success_count += 1
                                    except Exception as e:
                                        error_msg = f"Erreur lors de la création du candidat: {str(e)}"
                                        _logger.error(error_msg)
                                        error_details.append(error_msg)
                                        error_count += 1
                                        continue
                                    
                                except Exception as e:
                                    error_msg = f"Erreur inattendue lors du traitement de la réponse: {str(e)}"
                                    _logger.error(error_msg)
                                    error_details.append(error_msg)
                                    error_count += 1
                                    continue
                            
                            # Résumé de l'importation
                            _logger.info("=== Résumé de l'importation ===")
                            _logger.info("Succès: %d", success_count)
                            _logger.info("Erreurs: %d", error_count)
                            if error_details:
                                _logger.info("Détails des erreurs:")
                                for error in error_details:
                                    _logger.info("- %s", error)
                            
                            return {
                                'type': 'ir.actions.client',
                                'tag': 'display_notification',
                                'params': {
                                    'title': _('Succès'),
                                    'message': _(
                                        '%d réponse(s) importée(s) avec succès. %d erreur(s) rencontrée(s).\n'
                                        '%s'
                                    ) % (success_count, error_count, '\n'.join(error_details) if error_details else ''),
                                    'type': 'info' if success_count > 0 else 'warning',
                                    'sticky': True if error_count > 0 else False,
                                }
                            }
                            
                    except Exception as e:
                        _logger.error("Erreur lors du traitement du CSV: %s", str(e))
                        _logger.error("Détails de l'erreur: %s", traceback.format_exc())
                        raise UserError(_("Erreur lors du traitement des réponses: %s") % str(e))
                else:
                    _logger.error("Format de réponse invalide: %s", type(responses))
                    raise UserError(_("Format de réponse invalide reçu du serveur LimeSurvey."))
                    
            finally:
                try:
                    server.release_session_key(session_key)
                    _logger.info("Session libérée")
                except:
                    _logger.warning("Erreur lors de la libération de la session")
                
        except Exception as e:
            _logger.error("Erreur lors de l'importation: %s", str(e))
            _logger.error("Détails de l'erreur: %s", traceback.format_exc())
            raise UserError(_("Erreur lors de l'import des réponses: %s") % str(e)) 

    def _disable_tokens_in_db(self, server, session_key):
        """Désactive les tokens dans LimeSurvey."""
        try:
            # 1. Vérification de l'existence du sondage
            _logger.info("Vérification du sondage %s", self.sid)
            survey_properties = server.get_survey_properties(session_key, self.sid)
            if not survey_properties:
                _logger.error("Sondage %s non trouvé", self.sid)
                return False

            # 2. Mise à jour des paramètres du sondage pour désactiver les tokens
            _logger.info("Désactivation des tokens pour le sondage %s", self.sid)
            try:
                survey_data = {
                    'usecookie': 'N',
                    'allowregister': 'N',
                    'allowsave': 'Y',
                    'anonymized': 'N',
                    'tokenanswerspersistence': 'N',
                    'usecaptcha': 'N',
                    'listpublic': 'Y',
                    'publicstatistics': 'N',
                    'printanswers': 'N',
                    'publicgraphs': 'N',
                    'assessments': 'N',
                    'usetokens': 'N',  # Désactivation des tokens
                    'showwelcome': 'N',
                    'showprogress': 'Y',
                    'questionindex': 0,
                    'navigationdelay': 0,
                    'nokeyboard': 'N',
                    'allowprev': 'Y',
                    'format': 'G',
                    'template': 'default',
                    'active': 'Y'
                }
                result = server.set_survey_properties(session_key, self.sid, survey_data)
                if not result:
                    _logger.error("Échec de la désactivation des tokens")
                    return False
                _logger.info("Tokens désactivés avec succès")

                # 3. Activation du sondage
                try:
                    server.activate_survey(session_key, self.sid)
                    _logger.info("Sondage activé avec succès")
                except Exception as e:
                    _logger.warning("Erreur lors de l'activation du sondage: %s", str(e))
                    # On continue même si cette étape échoue

                return True

            except Exception as e:
                _logger.error("Erreur lors de la mise à jour des paramètres: %s", str(e))
                return False

        except Exception as e:
            _logger.error("Erreur générale lors de la désactivation des tokens: %s", str(e))
            _logger.error("Traceback complet:", exc_info=True)
            return False

    def action_set_public(self):
        """Configure le formulaire en mode public."""
        self.ensure_one()
        
        if not self.sid:
            raise UserError(_("Veuillez d'abord configurer l'ID du questionnaire LimeSurvey."))
            
        if not self.server_config_id:
            raise UserError(_("Veuillez d'abord configurer le serveur LimeSurvey."))
            
        try:
            # Connexion à LimeSurvey
            server, session_key = self.server_config_id._get_rpc_session()
            
            # Conversion de l'ID en entier
            survey_id = int(self.sid)

            # 1. Désactiver le système de tokens au niveau de la base de données
            if not self._disable_tokens_in_db(server, session_key):
                raise UserError(_("Erreur lors de la désactivation des tokens dans la base de données."))

            # 2. Configuration des paramètres pour rendre le formulaire public
            params = {
                'allowregister': 'N',  # Désactiver l'inscription
                'allowsave': 'Y',      # Permettre la sauvegarde
                'anonymized': 'N',     # Ne pas anonymiser les réponses
                'tokenanswerspersistence': 'N',  # Ne pas utiliser les tokens
                'usecaptcha': 'N',     # Ne pas utiliser de captcha
                'listpublic': 'Y',     # Rendre le formulaire public
                'publicstatistics': 'N',  # Ne pas publier les statistiques
                'printanswers': 'N',   # Ne pas permettre l'impression des réponses
                'publicgraphs': 'N',   # Ne pas publier les graphiques
                'usecookie': 'N',      # Ne pas utiliser de cookies
                'alloweditaftercompletion': 'N',  # Ne pas permettre l'édition après complétion
                'ipaddr': 'N',         # Ne pas collecter les adresses IP
                'refurl': 'N',         # Ne pas collecter les URL de référence
                'tokenencryption': 'N',  # Ne pas crypter les tokens
                'usetokens': 'N',      # Désactiver l'utilisation des tokens
                'showwelcome': 'N',    # Masquer la page de bienvenue
                'showprogress': 'Y',   # Afficher la barre de progression
                'questionindex': '0',   # Désactiver l'index des questions
                'navigationdelay': '0', # Pas de délai de navigation
                'nokeyboard': 'N',     # Autoriser le clavier
                'allowprev': 'Y',      # Autoriser retour en arrière
                'format': 'G',         # Format de groupe par groupe
                'template': 'default',  # Template par défaut
                'surveymode': 'open'   # Mode ouvert sans tokens
            }
            
            # 3. Mise à jour des paramètres du formulaire
            result = server.set_survey_properties(session_key, survey_id, params)
            
            if result:
                # 4. Réactiver le formulaire pour appliquer les changements
                server.activate_survey(session_key, survey_id)
                
                # 5. Mise à jour du statut dans Odoo
                self.write({
                    'is_active': True,
                    'sync_status': 'synced',
                    'last_sync_date': fields.Datetime.now(),
                })
                
                # 6. Forcer la mise à jour de l'URL du formulaire
                self._compute_form_url()
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Succès'),
                        'message': _('Le formulaire a été configuré en mode public.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("Erreur lors de la configuration du formulaire en mode public."))
                
        except xmlrpc.client.Fault as e:
            _logger.error(
                "Erreur RPC lors de la configuration du formulaire %s: [%s] %s",
                self.sid, getattr(e, 'faultCode', 'N/A'), str(e)
            )
            raise UserError(_(
                "Erreur lors de la configuration du formulaire:\n\n"
                "Code: %s\n"
                "Message: %s"
            ) % (getattr(e, 'faultCode', 'N/A'), str(e)))
            
        except Exception as e:
            _logger.error(
                "Erreur inattendue lors de la configuration du formulaire %s: %s",
                self.sid, str(e)
            )
            raise UserError(_("Erreur lors de la configuration du formulaire: %s") % str(e))
            
        finally:
            try:
                server.release_session_key(session_key)
            except:
                pass

    def action_disable_tokens(self):
        """Désactive les tokens et rend le formulaire public."""
        self.ensure_one()
        
        if not self.sid:
            raise UserError(_("Veuillez d'abord configurer l'ID du questionnaire LimeSurvey."))
            
        if not self.server_config_id:
            raise UserError(_("Veuillez d'abord configurer le serveur LimeSurvey."))
            
        try:
            # Connexion à LimeSurvey
            server, session_key = self.server_config_id._get_rpc_session()
            
            # Conversion de l'ID en entier
            survey_id = int(self.sid)

            # 1. Désactiver les tokens existants
            try:
                server.delete_survey_tokens(session_key, survey_id)
                _logger.info("Tokens existants supprimés avec succès")
            except:
                _logger.info("Pas de tokens à supprimer ou erreur lors de la suppression")

            # 2. Configuration des paramètres pour rendre le formulaire public sans tokens
            params = {
                'allowregister': 'N',  # Désactiver l'inscription
                'allowsave': 'Y',      # Permettre la sauvegarde
                'anonymized': 'N',     # Ne pas anonymiser les réponses
                'tokenanswerspersistence': 'N',  # Ne pas utiliser les tokens
                'usecaptcha': 'N',     # Ne pas utiliser de captcha
                'listpublic': 'Y',     # Rendre le formulaire public
                'publicstatistics': 'N',  # Ne pas publier les statistiques
                'printanswers': 'N',   # Ne pas permettre l'impression des réponses
                'publicgraphs': 'N',   # Ne pas publier les graphiques
                'usecookie': 'N',      # Ne pas utiliser de cookies
                'alloweditaftercompletion': 'N',  # Ne pas permettre l'édition après complétion
                'ipaddr': 'N',         # Ne pas collecter les adresses IP
                'refurl': 'N',         # Ne pas collecter les URL de référence
                'usetokens': 'N',      # Désactiver l'utilisation des tokens
                'showwelcome': 'N',    # Masquer la page de bienvenue
                'showprogress': 'Y',   # Afficher la barre de progression
                'questionindex': '0',   # Désactiver l'index des questions
                'navigationdelay': '0', # Pas de délai de navigation
                'nokeyboard': 'N',     # Autoriser le clavier
                'allowprev': 'Y',      # Autoriser retour en arrière
                'format': 'G',         # Format de groupe par groupe
                'template': 'default',  # Template par défaut
                'active': 'Y',         # Activer le formulaire
                'surveymode': 'open'   # Mode ouvert sans tokens
            }
            
            # 3. Mise à jour des paramètres du formulaire
            result = server.set_survey_properties(session_key, survey_id, params)
            
            if result:
                # 4. Désactiver explicitement les tokens
                try:
                    server.set_survey_property(session_key, survey_id, 'usetokens', 'N')
                except:
                    _logger.warning("Erreur lors de la désactivation explicite des tokens")

                # 5. Réactiver le formulaire pour appliquer les changements
                server.activate_survey(session_key, survey_id)
                
                # 6. Mise à jour du statut dans Odoo
                self.write({
                    'is_active': True,
                    'sync_status': 'synced',
                    'last_sync_date': fields.Datetime.now(),
                    'default_token': False  # Supprimer l'ancien token par défaut
                })
                
                # 7. Forcer la mise à jour de l'URL du formulaire
                self._compute_form_url()
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Succès'),
                        'message': _('Le formulaire est maintenant public et accessible sans code d\'accès.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_("Erreur lors de la configuration du formulaire en mode public."))
                
        except xmlrpc.client.Fault as e:
            _logger.error(
                "Erreur RPC lors de la configuration du formulaire %s: [%s] %s",
                self.sid, getattr(e, 'faultCode', 'N/A'), str(e)
            )
            raise UserError(_(
                "Erreur lors de la configuration du formulaire:\n\n"
                "Code: %s\n"
                "Message: %s"
            ) % (getattr(e, 'faultCode', 'N/A'), str(e)))
            
        except Exception as e:
            _logger.error(
                "Erreur inattendue lors de la configuration du formulaire %s: %s",
                self.sid, str(e)
            )
            raise UserError(_("Erreur lors de la configuration du formulaire: %s") % str(e))
            
        finally:
            try:
                server.release_session_key(session_key)
            except:
                pass 