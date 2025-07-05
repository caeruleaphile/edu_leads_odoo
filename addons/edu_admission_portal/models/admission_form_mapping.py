from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import json
import logging
import re

_logger = logging.getLogger(__name__)

class AdmissionFormMapping(models.Model):
    _name = 'admission.form.mapping'
    _description = "Mapping Formulaire d'Admission"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(
        string='Nom',
        compute='_compute_name',
        store=True,
    )
    
    form_template_id = fields.Many2one(
        'admission.form.template',
        string='Template de Formulaire',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    
    sequence = fields.Integer(
        string='Séquence',
        default=10
    )
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('validated', 'Validé'),
    ], string='État',
        default='draft',
        tracking=True,
    )
    
    generated_at = fields.Datetime(
        string='Date de Génération',
        default=fields.Datetime.now,
        tracking=True,
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

    mapping_line_ids = fields.One2many(
        'admission.mapping.line',
        'mapping_id',
        string='Lignes de Mapping',
    )

    mapping_json = fields.Text(
        string='Configuration JSON du Mapping',
        help='Stocke la configuration complète du mapping au format JSON',
        tracking=True,
    )

    @api.depends('form_template_id', 'generated_at')
    def _compute_name(self):
        """Calcule un nom unique pour le mapping."""
        for record in self:
            if record.form_template_id:
                record.name = f"Mapping - {record.form_template_id.name}"
            else:
                record.name = f"Nouveau Mapping ({record.id})"

    def action_validate(self):
        """Valide le mapping."""
        self.ensure_one()
        
        # Vérification de l'existence des lignes de mapping
        if not self.mapping_line_ids:
            raise ValidationError(_(
                "Impossible de valider un mapping vide.\n"
                "Veuillez d'abord générer ou créer des lignes de mapping."
            ))
            
        # Vérification que toutes les lignes requises sont mappées
        unmapped_required = self.mapping_line_ids.filtered(
            lambda l: l.is_required and not l.odoo_field
        )
        if unmapped_required:
            raise ValidationError(_(
                "Certains champs requis ne sont pas mappés :\n%s"
            ) % '\n'.join(['- ' + line.question_text for line in unmapped_required]))

        self.write({'state': 'validated'})
        
        # Activation automatique de la création des candidats
        self._activate_auto_creation()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Le mapping a été validé avec succès. Création automatique activée !'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _activate_auto_creation(self):
        """Active automatiquement la création des candidats après validation du mapping."""
        self.ensure_one()
        
        # Mise à jour du template de formulaire
        self.form_template_id.write({
            'mapping_validated': True,
            'auto_create_candidates': True,
            'auto_create_status': 'enabled',
        })
        
        _logger.info(
            "Création automatique activée pour le formulaire %s (ID: %s)",
            self.form_template_id.name, self.form_template_id.id
        )

    def action_reset_to_draft(self):
        """Repasse le mapping en brouillon."""
        self.ensure_one()
        self.write({'state': 'draft'})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Information'),
                'message': _('Le mapping est repassé en brouillon.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_regenerate_mapping(self):
        """Régénère le mapping à partir du template."""
        self.ensure_one()
        self.form_template_id._create_default_mappings(
            json.loads(self.form_template_id.field_mapping or '{}')
        )

    def action_validate_high_confidence(self):
        """Valide toutes les lignes avec un score > 90%."""
        high_confidence_lines = self.mapping_line_ids.filtered(
            lambda l: l.confidence_score >= 90 and l.status != 'validated'
        )
        if high_confidence_lines:
            high_confidence_lines.write({'status': 'validated'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('%d lignes validées automatiquement.') % len(high_confidence_lines),
                    'type': 'success',
                    'sticky': False,
                }
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Information'),
                'message': _('Aucune ligne à valider automatiquement.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def transform_value(self, value):
        """
        Transforme une valeur selon les règles de mappage.
        
        Args:
            value: Valeur à transformer
            
        Returns:
            La valeur transformée
            
        Raises:
            ValidationError: Si la transformation échoue
        """
        self.ensure_one()
        
        try:
            if self.mapping_type == 'direct':
                return value
                
            if not self.transform_python:
                return value
                
            # Contexte d'exécution sécurisé
            safe_globals = {
                'datetime': __import__('datetime'),
                'json': __import__('json'),
                're': __import__('re'),
            }
            safe_locals = {'value': value}
            
            # Exécute le code de transformation
            exec(self.transform_python, safe_globals, safe_locals)
            
            if 'result' not in safe_locals:
                raise ValidationError(_("Le code de transformation doit définir une variable 'result'"))
                
            return safe_locals['result']
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la transformation de la valeur %s: %s",
                value, str(e)
            )
            raise ValidationError(_(
                "Erreur lors de la transformation de la valeur: %s", str(e)
            ))

    def validate_value(self, value):
        """
        Valide une valeur selon les règles définies.
        
        Args:
            value: Valeur à valider
            
        Returns:
            tuple: (is_valid, message)
        """
        self.ensure_one()
        
        if not self.is_required:
            return True, ''
            
        if not value and self.is_required:
            return False, _("Ce champ est requis")
            
        if not self.validation_python:
            return True, ''
            
        try:
            # Contexte d'exécution sécurisé
            safe_globals = {
                'datetime': __import__('datetime'),
                'json': __import__('json'),
                're': __import__('re'),
            }
            safe_locals = {'value': value}
            
            # Exécute le code de validation
            exec(self.validation_python, safe_globals, safe_locals)
            
            if 'is_valid' not in safe_locals or 'message' not in safe_locals:
                raise ValidationError(_(
                    "Le code de validation doit définir les variables 'is_valid' et 'message'"
                ))
                
            return safe_locals['is_valid'], safe_locals['message']
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la validation de la valeur %s: %s",
                value, str(e)
            )
            return False, str(e)

    def suggest_mappings(self):
        """Suggère des mappings automatiques basés sur l'analyse des champs."""
        self.ensure_one()
        
        # Récupération des champs du modèle admission.candidate
        candidate_fields = self.env['ir.model.fields'].search([
            ('model', '=', 'admission.candidate'),
            ('ttype', 'not in', ['one2many', 'many2many', 'binary'])
        ])

        suggestions = []
        for source_field in self.form_template_id.field_ids:
            best_match = None
            best_score = 0
            
            for candidate_field in candidate_fields:
                # Calcul du score de correspondance
                source_name = source_field.name.lower()
                target_name = candidate_field.name.lower()
                
                # Score basé sur la similarité des noms
                name_similarity = self._compute_name_similarity(source_name, target_name)
                
                # Score basé sur la compatibilité des types
                type_compatibility = self._compute_type_compatibility(
                    source_field.field_type,
                    candidate_field.ttype
                )
                
                total_score = name_similarity * 0.7 + type_compatibility * 0.3
                
                if total_score > best_score:
                    best_score = total_score
                    best_match = candidate_field

            if best_match and best_score > 0.5:
                suggestions.append({
                    'source_field_id': source_field.id,
                    'odoo_field_name': best_match.id,
                })

        return suggestions

    def _compute_name_similarity(self, name1, name2):
        """Calcule la similarité entre deux noms de champs."""
        # Normalisation
        name1 = name1.replace('_', ' ')
        name2 = name2.replace('_', ' ')
        
        # Mots communs
        words1 = set(name1.split())
        words2 = set(name2.split())
        common_words = words1.intersection(words2)
        
        if not words1 or not words2:
            return 0
            
        return len(common_words) / max(len(words1), len(words2))

    def _compute_type_compatibility(self, type1, type2):
        """Calcule la compatibilité entre deux types de champs."""
        if type1 == type2:
            return 1.0
            
        COMPATIBILITY_SCORES = {
            ('char', 'text'): 0.9,
            ('text', 'char'): 0.9,
            ('integer', 'float'): 0.8,
            ('float', 'integer'): 0.7,
            ('char', 'selection'): 0.6,
            ('selection', 'char'): 0.6,
        }
        
        return COMPATIBILITY_SCORES.get((type1, type2), 0.0)

    def action_regenerate_suggestions(self):
        """Action pour régénérer les suggestions de mapping."""
        self.ensure_one()
        suggestions = self.suggest_mappings()
        
        for suggestion in suggestions:
            self.write({
                'odoo_field_name': suggestion['odoo_field_name'],
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Suggestions régénérées'),
                'message': _('%d suggestions ont été mises à jour.') % len(suggestions),
                'sticky': False,
                'type': 'success',
            }
        }

    def action_test_mapping(self):
        """Action pour tester un mappage avec des données d'exemple."""
        self.ensure_one()
        
        # Récupère un exemple de données du formulaire
        sample_data = self.form_template_id.get_sample_data()
        
        if not sample_data:
            raise ValidationError(_("Aucune donnée d'exemple disponible pour ce formulaire"))
        
        # Teste le mappage
        try:
            source_value = sample_data.get(self.source_field_id.name)
            transformed_value = self.transform_value(source_value)
            is_valid, message = self.validate_value(transformed_value)
            
            # Crée un wizard pour afficher les résultats
            wizard = self.env['admission.mapping.test.wizard'].create({
                'mapping_id': self.id,
                'source_value': str(source_value),
                'transformed_value': str(transformed_value),
                'is_valid': is_valid,
                'validation_message': message,
            })
            
            return {
                'name': _('Résultat du Test'),
                'type': 'ir.actions.act_window',
                'res_model': 'admission.mapping.test.wizard',
                'res_id': wizard.id,
                'view_mode': 'form',
                'target': 'new',
            }
            
        except Exception as e:
            raise ValidationError(_(
                "Erreur lors du test du mappage: %s", str(e)
            )) 

    def action_apply_all_mappings(self):
        """Applique automatiquement tous les mappings possibles."""
        self.ensure_one()
        
        # Appliquer les suggestions automatiques sur toutes les lignes
        draft_lines = self.mapping_line_ids.filtered(lambda l: l.status == 'draft')
        if draft_lines:
            result = draft_lines.action_suggest_mapping()
            
            # Valider automatiquement les lignes avec un score élevé
            self.action_validate_high_confidence()
            
            return result
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _('Toutes les lignes sont déjà mappées.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

    def action_create_candidates_automatically(self):
        """Active la création automatique des candidats pour ce mapping."""
        self.ensure_one()
        
        if self.state != 'validated':
            raise ValidationError(_(
                "Le mapping doit être validé avant d'activer la création automatique des candidats."
            ))
        
        # Marquer le template comme auto-créateur
        self.form_template_id.write({
            'auto_create_candidates': True,
            'mapping_validated': True,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Création automatique des candidats activée ! Les nouvelles soumissions créeront automatiquement les candidats.'),
                'type': 'success',
                'sticky': True,
            }
        } 

    def action_validate_all_mapped_lines(self):
        """Valide toutes les lignes de mapping qui ont un champ Odoo renseigné."""
        self.ensure_one()
        mapped_lines = self.mapping_line_ids.filtered(lambda l: l.odoo_field and l.status != 'validated')
        if mapped_lines:
            mapped_lines.write({'status': 'validated'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Validation en Lot'),
                    'message': _('✅ %d ligne(s) validée(s) automatiquement !') % len(mapped_lines),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Validation en Lot'),
                    'message': _('Aucune ligne à valider. Assurez-vous d\'avoir sélectionné des champs Odoo.'),
                    'type': 'warning',
                    'sticky': False,
                }
            } 