from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AdmissionMappingLine(models.Model):
    _name = 'admission.mapping.line'
    _description = 'Ligne de Mapping Admission'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Séquence',
        default=10,
    )

    mapping_id = fields.Many2one(
        'admission.form.mapping',
        string='Mapping',
        required=True,
        ondelete='cascade',
    )

    is_default = fields.Boolean(
        string='Mapping par défaut',
        default=False,
        help="Si coché, ce mapping sera utilisé comme modèle pour les nouveaux formulaires",
    )

    mapping_type = fields.Selection([
        ('direct', 'Mappage direct'),
        ('transform', 'Transformation')
    ], string='Type de mappage', required=True, default='direct')

    transform_python = fields.Text(
        string='Code de transformation',
        help="Code Python pour transformer la valeur source avant de l'assigner au champ destination"
    )

    validation_python = fields.Text(
        string='Code de validation',
        help="Code Python pour valider la valeur avant l'assignation"
    )

    is_attachment = fields.Boolean(
        string='Est une pièce jointe',
        default=False,
        help="Cocher si ce champ contient une pièce jointe"
    )

    question_code = fields.Char(
        string='Code Question',
        required=True,
        help="Code de la question dans LimeSurvey (ex: G01Q01)",
    )

    question_text = fields.Char(
        string='Question',
        required=True,
        help="Intitulé de la question",
    )

    group_name = fields.Char(
        string='Groupe',
        help="Nom du groupe de questions dans LimeSurvey",
    )

    question_type = fields.Selection([
        ('text', 'Texte'),
        ('numeric', 'Numérique'),
        ('date', 'Date'),
        ('choice', 'Liste de choix'),
        ('multiple', 'Choix multiple'),
        ('upload', 'Fichier'),
    ], string='Type', required=True)

    odoo_field = fields.Selection(
        selection='_get_candidate_field_options',
        string='Champ Odoo',
        required=False,
        help="Champ de destination dans admission.candidate (sélectionnez ou tapez librement)",
    )

    @api.onchange('odoo_field')
    def _onchange_odoo_field(self):
        """Met à jour automatiquement le statut quand un champ Odoo est sélectionné."""
        if self.odoo_field:
            # Si un champ est sélectionné, passer en "À Vérifier"
            self.status = 'to_verify'
            # Mettre à jour le score de confiance si pas déjà défini
            if self.confidence_score == 0:
                self.confidence_score = 50  # Score par défaut pour mapping manuel
        else:
            # Si aucun champ n'est sélectionné, repasser en brouillon
            self.status = 'draft'
            self.confidence_score = 0

    @api.model
    def _get_candidate_field_options(self):
        """Retourne les options pour le champ odoo_field avec descriptions."""
        options = [
            # Option vide pour permettre la non-sélection
            ('', ''),
            
            # Informations Personnelles
            ('civility', 'Civilité'),
            ('first_name', 'Prénom'),
            ('last_name', 'Nom'),
            ('cin_number', 'Numéro CIN'),
            ('massar_code', 'Code MASSAR'),
            ('birth_date', 'Date de naissance'),
            ('birth_city', 'Ville de naissance'),
            ('birth_country', 'Pays de naissance'),
            ('nationality', 'Nationalité'),
            ('email', 'Email'),
            ('phone', 'Téléphone'),
            
            # Adresse & Résidence
            ('address', 'Adresse'),
            ('postal_code', 'Code postal'),
            ('city', 'Ville'),
            ('residence_country', 'Pays de résidence'),
            
            # Informations Académiques
            ('bac_series', 'Série du Bac'),
            ('bac_year', 'Année du Bac'),
            ('bac_school', 'Lycée'),
            ('bac_country', 'Pays du Bac'),
            ('university', 'Établissement Bac+2/3'),
            ('degree_field', 'Filière'),
            ('university_city', 'Ville établissement'),
            ('degree_year', 'Année d\'obtention'),
            ('academic_level', 'Niveau académique'),
            
            # Moyennes Annuelles
            ('avg_year1', 'Moyenne 1ère année'),
            ('avg_year2', 'Moyenne 2ème année'),
            ('avg_year3', 'Moyenne 3ème année'),
            
            # Moyennes Semestrielles
            ('avg_sem1', 'Moyenne Semestre 1'),
            ('avg_sem2', 'Moyenne Semestre 2'),
            ('avg_sem3', 'Moyenne Semestre 3'),
            ('avg_sem4', 'Moyenne Semestre 4'),
            ('avg_sem5', 'Moyenne Semestre 5'),
            ('avg_sem6', 'Moyenne Semestre 6'),
            
            # Documents
            ('bac_scan', 'Scan du Baccalauréat'),
            ('bac2_transcript', 'Relevé de notes Bac+2'),
            ('bac3_transcript', 'Relevé de notes Bac+3'),
            ('payment_proof', 'Justificatif de paiement'),
            ('sem1_transcript', 'Relevé de notes S1'),
            ('sem2_transcript', 'Relevé de notes S2'),
            ('sem3_transcript', 'Relevé de notes S3'),
            ('sem4_transcript', 'Relevé de notes S4'),
            ('sem5_transcript', 'Relevé de notes S5'),
            ('sem6_transcript', 'Relevé de notes S6'),
            
            # Évaluation
            ('academic_score', 'Note Académique'),
            ('experience_score', 'Note Expérience'),
            ('motivation_score', 'Note Motivation'),
            ('evaluation_note', 'Notes d\'Évaluation'),
            
            # Autres
            ('notes', 'Notes'),
            ('status', 'Statut'),
            ('payment_confirmed', 'Paiement confirmé'),
            ('documents_validated', 'Documents validés'),
            ('identity_verified', 'Identité vérifiée'),
            ('academic_validated', 'Niveau académique validé'),
            ('interview_scheduled', 'Date d\'entretien'),
            ('interview_done', 'Entretien effectué'),
            
            # Champs techniques
            ('response_id', 'ID Réponse'),
            ('response_data', 'Données de Réponse'),
            ('submission_date', 'Date de Soumission'),
            ('form_id', 'Formulaire'),
        ]
        
        # Ajouter dynamiquement les champs personnalisés existants
        existing_fields = self.search([]).mapped('odoo_field')
        for field in existing_fields:
            if field and field not in [opt[0] for opt in options]:
                options.append((field, f'{field} (personnalisé)'))
        
        return options

    field_label = fields.Char(
        string='Champ',
        compute='_compute_field_label',
        help="Nom affiché du champ Odoo",
    )

    confidence_score = fields.Integer(
        string='Score',
        required=True,
        default=0,
        help="Score de confiance (0-100)",
    )

    mapping_quality = fields.Selection([
        ('confirmed', '✅ Confirmé'),
        ('warning', '⚠️ À vérifier'),
        ('unmatched', '❌ Non mappé')
    ], string='Qualité du Mapping',
        compute='_compute_mapping_quality',
        store=True,
    )
    
    justification = fields.Char(
        string='Justification',
        compute='_compute_mapping_quality',
        store=True,
        help='Explication de la suggestion de mapping',
    )

    status = fields.Selection([
        ('draft', 'Brouillon'),
        ('to_verify', 'À Vérifier'),
        ('validated', 'Validé'),
    ], string='Statut', 
        required=True,
        default='draft',
    )

    is_required = fields.Boolean(
        string='Requis',
        default=False,
    )

    notes = fields.Text(
        string='Notes',
    )

    attributes = fields.Text(
        string='Attributs',
        help="Attributs JSON de la question LimeSurvey",
    )

    @api.depends('odoo_field')
    def _compute_field_label(self):
        """Récupère le libellé du champ Odoo."""
        candidate_fields = self.env['admission.candidate'].fields_get()
        for line in self:
            if line.odoo_field in candidate_fields:
                line.field_label = candidate_fields[line.odoo_field]['string']
            else:
                line.field_label = line.odoo_field

    @api.constrains('confidence_score')
    def _check_confidence_score(self):
        """Vérifie que le score est entre 0 et 100."""
        for line in self:
            if not (0 <= line.confidence_score <= 100):
                raise ValidationError(_("Le score de confiance doit être entre 0 et 100."))

    @api.depends('confidence_score')
    def _compute_mapping_quality(self):
        """Calcule la qualité du mapping basée sur le score de confiance."""
        for record in self:
            if record.confidence_score >= 80:
                record.mapping_quality = 'confirmed'
                record.justification = 'Correspondance forte basée sur la similarité des noms et types'
            elif record.confidence_score >= 50:
                record.mapping_quality = 'warning'
                record.justification = 'Correspondance possible, à vérifier manuellement'
            else:
                record.mapping_quality = 'unmatched'
                record.justification = 'Aucune correspondance fiable trouvée'

    def action_validate(self):
        """Valide la ligne de mapping."""
        self.write({'status': 'validated'})

    def action_mark_to_verify(self):
        """Marque la ligne comme à vérifier."""
        self.write({'status': 'to_verify'})

    def action_reset_draft(self):
        """Repasse la ligne en brouillon."""
        self.write({'status': 'draft'})

    def transform_value(self, value):
        """
        Transforme la valeur en utilisant le code Python défini.
        
        Args:
            value: La valeur à transformer
            
        Returns:
            La valeur transformée
            
        Raises:
            Exception: Si une erreur survient pendant la transformation
        """
        if not self.transform_python:
            return value
            
        try:
            # Variables disponibles dans le code
            locals_dict = {
                'value': value,
                'self': self,
                'env': self.env,
            }
            
            # Exécution du code
            exec(self.transform_python, globals(), locals_dict)
            
            # Récupération de la valeur transformée
            if 'result' not in locals_dict:
                raise ValueError("Le code de transformation doit définir une variable 'result'")
                
            return locals_dict['result']
            
        except Exception as e:
            raise Exception(f"Erreur lors de la transformation: {str(e)}")

    def validate_value(self, value):
        """
        Valide la valeur en utilisant le code Python défini.
        
        Args:
            value: La valeur à valider
            
        Returns:
            bool: True si la valeur est valide, False sinon
            
        Raises:
            Exception: Si une erreur survient pendant la validation
        """
        if not self.validation_python:
            return True
            
        try:
            # Variables disponibles dans le code
            locals_dict = {
                'value': value,
                'self': self,
                'env': self.env,
            }
            
            # Exécution du code
            exec(self.validation_python, globals(), locals_dict)
            
            # Récupération du résultat
            if 'result' not in locals_dict:
                raise ValueError("Le code de validation doit définir une variable 'result'")
                
            return bool(locals_dict['result'])
            
        except Exception as e:
            raise Exception(f"Erreur lors de la validation: {str(e)}")

    @api.model
    def create_from_mapping_json(self, mapping_id, mapping_data):
        """
        Crée les lignes de mapping à partir du mapping_json.
        
        Args:
            mapping_id: ID du mapping parent
            mapping_data: Dictionnaire du mapping
        """
        lines_to_create = []
        for question_code, data in mapping_data.items():
            line_vals = {
                'mapping_id': mapping_id,
                'question_code': question_code,
                'question_text': data.get('label', ''),
                'question_type': data.get('type', 'text'),
                'odoo_field': data.get('field', ''),
                'confidence_score': int(data.get('confidence', 0)),
                'is_required': data.get('required', False),
                'status': 'validated' if data.get('confidence', 0) >= 90 else 'to_verify',
            }
            lines_to_create.append(line_vals)

        if lines_to_create:
            self.create(lines_to_create) 

    def get_candidate_field_suggestions(self):
        """Méthode conservée pour compatibilité."""
        return [opt[0] for opt in self._get_candidate_field_options() if opt[0]]

    def action_suggest_mapping(self):
        """Suggère automatiquement un mapping basé sur le texte de la question."""
        suggestions_applied = 0
        for line in self:
            suggested_field, confidence = line._suggest_field_mapping()
            if suggested_field:
                line.write({
                    'odoo_field': suggested_field,
                    'confidence_score': confidence,
                    'status': 'validated' if confidence >= 90 else 'to_verify',
                })
                suggestions_applied += 1
        
        # Message de confirmation
        if suggestions_applied > 0:
            message = f"✅ {suggestions_applied} mapping(s) suggéré(s) automatiquement !"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Suggestion Automatique',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Suggestion Automatique',
                    'message': 'Aucune suggestion trouvée pour ces questions.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

    @api.model
    def action_apply_all_suggestions(self):
        """Applique toutes les suggestions automatiques pour toutes les lignes."""
        all_lines = self.search([('status', '=', 'draft')])
        return all_lines.action_suggest_mapping()

    def _suggest_field_mapping(self):
        """Suggère un champ Odoo basé sur le texte de la question."""
        question_text = (self.question_text or '').lower()
        
        # Dictionnaire de mots-clés pour mapping automatique
        keyword_mapping = {
            # Informations personnelles
            'civilité': ('civility', 95),
            'titre': ('civility', 90),
            'prénom': ('first_name', 95),
            'prenom': ('first_name', 95),
            'nom': ('last_name', 95),
            'nom de famille': ('last_name', 95),
            'cin': ('cin_number', 95),
            'carte nationale': ('cin_number', 90),
            'pièce d\'identité': ('cin_number', 85),
            'massar': ('massar_code', 95),
            'code massar': ('massar_code', 95),
            'date de naissance': ('birth_date', 95),
            'né le': ('birth_date', 90),
            'naissance': ('birth_date', 85),
            'ville de naissance': ('birth_city', 90),
            'lieu de naissance': ('birth_city', 85),
            'pays de naissance': ('birth_country', 90),
            'nationalité': ('nationality', 90),
            'email': ('email', 95),
            'e-mail': ('email', 95),
            'adresse e-mail': ('email', 95),
            'adresse électronique': ('email', 90),
            'courriel': ('email', 90),
            'téléphone': ('phone', 95),
            'telephone': ('phone', 95),
            'numéro de téléphone': ('phone', 95),
            'portable': ('phone', 90),
            'gsm': ('phone', 85),
            
            # Adresse
            'adresse': ('address', 90),
            'domicile': ('address', 85),
            'résidence': ('address', 80),
            'code postal': ('postal_code', 90),
            'cp': ('postal_code', 85),
            'ville': ('city', 80),
            'localité': ('city', 75),
            'pays de résidence': ('residence_country', 90),
            'pays': ('residence_country', 70),
            
            # Informations académiques
            'série': ('bac_series', 85),
            'série du bac': ('bac_series', 95),
            'série baccalauréat': ('bac_series', 95),
            'filière bac': ('bac_series', 90),
            'année du bac': ('bac_year', 90),
            'année d\'obtention du bac': ('bac_year', 95),
            'année baccalauréat': ('bac_year', 90),
            'lycée': ('bac_school', 90),
            'lycée d\'obtention': ('bac_school', 95),
            'établissement secondaire': ('bac_school', 85),
            'pays du bac': ('bac_country', 85),
            'pays d\'obtention': ('bac_country', 90),
            'établissement': ('university', 85),
            'université': ('university', 90),
            'école': ('university', 85),
            'institut': ('university', 85),
            'filière': ('degree_field', 90),
            'spécialité': ('degree_field', 85),
            'domaine': ('degree_field', 80),
            'ville établissement': ('university_city', 85),
            'ville université': ('university_city', 85),
            'année d\'obtention': ('degree_year', 85),
            'année de préparation': ('degree_year', 80),
            
            # Moyennes
            'moyenne 1': ('avg_year1', 90),
            'moyenne première': ('avg_year1', 90),
            'moyenne 1ère': ('avg_year1', 90),
            'moyenne 2': ('avg_year2', 90),
            'moyenne deuxième': ('avg_year2', 90),
            'moyenne 2ème': ('avg_year2', 90),
            'moyenne 3': ('avg_year3', 90),
            'moyenne troisième': ('avg_year3', 90),
            'moyenne 3ème': ('avg_year3', 90),
            'semestre 1': ('avg_sem1', 90),
            '1er semestre': ('avg_sem1', 90),
            'semestre 2': ('avg_sem2', 90),
            '2ème semestre': ('avg_sem2', 90),
            'semestre 3': ('avg_sem3', 90),
            '3ème semestre': ('avg_sem3', 90),
            'semestre 4': ('avg_sem4', 90),
            '4ème semestre': ('avg_sem4', 90),
            'semestre 5': ('avg_sem5', 90),
            '5ème semestre': ('avg_sem5', 90),
            'semestre 6': ('avg_sem6', 90),
            '6ème semestre': ('avg_sem6', 90),
            
            # Autres champs utiles
            'notes': ('notes', 80),
            'remarques': ('notes', 75),
            'commentaires': ('notes', 75),
            'observations': ('notes', 70),
        }
        
        # Recherche de correspondances
        best_match = None
        best_score = 0
        
        for keyword, (field, confidence) in keyword_mapping.items():
            if keyword in question_text:
                if confidence > best_score:
                    best_match = field
                    best_score = confidence
        
        return best_match, best_score 

    @api.model
    def action_validate_all_mapped(self):
        """Valide toutes les lignes qui ont un champ Odoo sélectionné."""
        mapped_lines = self.search([
            ('odoo_field', '!=', False),
            ('odoo_field', '!=', ''),
            ('status', '!=', 'validated')
        ])
        
        if mapped_lines:
            mapped_lines.write({'status': 'validated'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validation en Lot',
                    'message': f'✅ {len(mapped_lines)} ligne(s) validée(s) automatiquement !',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validation en Lot',
                    'message': 'Aucune ligne à valider. Assurez-vous d\'avoir sélectionné des champs Odoo.',
                    'type': 'warning',
                    'sticky': False,
                }
            } 