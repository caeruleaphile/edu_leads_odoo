from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import magic
import os
import logging

_logger = logging.getLogger(__name__)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # Champs additionnels pour les pièces jointes d'admission
    is_admission_document = fields.Boolean(
        string='Document d\'admission',
        compute='_compute_is_admission_document',
        store=True
    )
    document_type = fields.Selection([
        ('identity', 'Pièce d\'identité'),
        ('diploma', 'Diplôme'),
        ('transcript', 'Relevé de notes'),
        ('cv', 'CV'),
        ('motivation', 'Lettre de motivation'),
        ('recommendation', 'Lettre de recommandation'),
        ('other', 'Autre')
    ], string='Type de document')
    
    validation_state = fields.Selection([
        ('pending', 'En attente'),
        ('valid', 'Valide'),
        ('invalid', 'Non valide')
    ], string='État de validation', default='pending')
    
    validation_note = fields.Text('Note de validation')
    file_size_human = fields.Char(
        string='Taille',
        compute='_compute_file_size_human',
        store=True
    )
    preview_available = fields.Boolean(
        string='Prévisualisation disponible',
        compute='_compute_preview_available',
        store=True
    )

    @api.depends('res_model')
    def _compute_is_admission_document(self):
        """Détermine si la pièce jointe est un document d'admission."""
        for attachment in self:
            attachment.is_admission_document = attachment.res_model == 'admission.candidate'

    @api.depends('file_size')
    def _compute_file_size_human(self):
        """Convertit la taille du fichier en format lisible."""
        for attachment in self:
            if not attachment.file_size:
                attachment.file_size_human = '0 B'
                continue
                
            size = attachment.file_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    attachment.file_size_human = f"{size:.1f} {unit}"
                    break
                size /= 1024.0

    @api.depends('mimetype')
    def _compute_preview_available(self):
        """Détermine si une prévisualisation est disponible."""
        PREVIEWABLE_MIMETYPES = [
            'application/pdf',
            'image/jpeg',
            'image/png',
            'image/gif',
            'image/bmp',
            'image/webp',
            'image/svg+xml'
        ]
        for attachment in self:
            attachment.preview_available = attachment.mimetype in PREVIEWABLE_MIMETYPES

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de create pour ajouter la validation des fichiers."""
        for vals in vals_list:
            if vals.get('res_model') == 'admission.candidate':
                self._validate_admission_attachment(vals)
        
        return super().create(vals_list)

    def write(self, vals):
        """Surcharge de write pour ajouter la validation des fichiers."""
        if 'datas' in vals and any(att.is_admission_document for att in self):
            self._validate_admission_attachment(vals)
        
        return super().write(vals)

    def _validate_admission_attachment(self, vals):
        """
        Valide une pièce jointe d'admission.
        
        Args:
            vals (dict): Valeurs à valider
            
        Raises:
            ValidationError: Si la validation échoue
        """
        if not vals.get('datas'):
            return
            
        try:
            # Décode les données en base64
            binary_data = base64.b64decode(vals['datas'])
            file_size = len(binary_data)
            
            # Vérifie la taille (max 10 MB)
            if file_size > 10 * 1024 * 1024:
                raise ValidationError(_(
                    "Le fichier est trop volumineux (max: 10 MB)"
                ))
            
            # Détecte le type MIME réel
            mime = magic.Magic(mime=True)
            real_mimetype = mime.from_buffer(binary_data)
            
            # Liste des types MIME autorisés
            ALLOWED_MIMETYPES = {
                'application/pdf': ['.pdf'],
                'image/jpeg': ['.jpg', '.jpeg'],
                'image/png': ['.png'],
                'application/msword': ['.doc'],
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
                'application/vnd.ms-excel': ['.xls'],
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']
            }
            
            # Vérifie le type MIME
            if real_mimetype not in ALLOWED_MIMETYPES:
                raise ValidationError(_(
                    "Type de fichier non autorisé (%(type)s)",
                    type=real_mimetype
                ))
            
            # Vérifie l'extension
            name = vals.get('name', '')
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_MIMETYPES[real_mimetype]:
                raise ValidationError(_(
                    "Extension de fichier non autorisée (%(ext)s)",
                    ext=ext
                ))
            
            # Met à jour le type MIME
            vals['mimetype'] = real_mimetype
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la validation du fichier %s: %s",
                vals.get('name'), str(e)
            )
            raise ValidationError(str(e))

    def action_validate_document(self):
        """Action pour valider un document."""
        self.ensure_one()
        
        if not self.is_admission_document:
            raise ValidationError(_("Ce n'est pas un document d'admission"))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Valider le Document'),
            'res_model': 'admission.document.validation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_attachment_id': self.id,
                'default_current_state': self.validation_state,
                'default_current_note': self.validation_note,
            }
        }

    def get_preview_data(self):
        """
        Récupère les données pour la prévisualisation.
        
        Returns:
            dict: Données de prévisualisation
        """
        self.ensure_one()
        
        if not self.preview_available:
            return False
        
        return {
            'mimetype': self.mimetype,
            'data': self.datas.decode('utf-8') if self.datas else False,
            'url': f'/web/content/{self.id}?download=false'
        }

    def action_preview_attachment(self):
        """Open the attachment in a preview window."""
        self.ensure_one()
        
        if not self.url and not self.datas:
            raise UserError(_("Aucun contenu à prévisualiser."))
            
        # For files stored in database or local filesystem
        if self.datas:
            action = {
                'type': 'ir.actions.act_url',
                'name': 'Preview',
                'target': 'new',
                'url': f'/web/content/{self.id}?download=false'
            }
            return action
            
        # For external URLs
        if self.url:
            action = {
                'type': 'ir.actions.act_url',
                'name': 'Preview',
                'target': 'new',
                'url': self.url
            }
            return action
            
        return {'type': 'ir.actions.act_window_close'} 