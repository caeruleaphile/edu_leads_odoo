# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import logging
import mimetypes
import base64
from werkzeug.urls import url_quote

_logger = logging.getLogger(__name__)

PREVIEW_MIME_TYPES = {
    'application/pdf': True,
    'image/jpeg': True,
    'image/png': True,
    'image/gif': True,
    'image/webp': True,
    'text/plain': True,
    'text/html': False,  # Désactivé pour la sécurité
    'text/javascript': False,  # Désactivé pour la sécurité
}

class AttachmentPreviewController(http.Controller):
    
    def _validate_attachment(self, attachment_id):
        """
        Valide et retourne une pièce jointe.
        
        Args:
            attachment_id: ID de la pièce jointe
            
        Returns:
            ir.attachment: La pièce jointe validée
            
        Raises:
            ValidationError: Si la pièce jointe n'est pas valide
        """
        if not isinstance(attachment_id, int):
            raise ValidationError("ID de pièce jointe invalide")
            
        attachment = request.env['ir.attachment'].browse(attachment_id)
        
        if not attachment.exists():
            raise ValidationError("Document non trouvé")
            
        try:
            attachment.check_access_rights('read')
            attachment.check_access_rule('read')
        except AccessError:
            raise ValidationError("Accès refusé")
            
        # Vérifie si le type MIME est autorisé
        mime_type = attachment.mimetype or mimetypes.guess_type(attachment.name)[0]
        if not mime_type or not PREVIEW_MIME_TYPES.get(mime_type, False):
            raise ValidationError("Type de fichier non supporté pour la prévisualisation")
            
        return attachment
    
    @http.route('/admission/attachment/preview/<int:attachment_id>', 
                type='http', auth='user', website=True)
    def preview_attachment(self, attachment_id, **kwargs):
        """
        Affiche la prévisualisation d'une pièce jointe.
        
        Args:
            attachment_id: ID de la pièce jointe
            
        Returns:
            Template de prévisualisation
        """
        try:
            # Validation de la pièce jointe
            attachment = self._validate_attachment(attachment_id)
            
            # Vérifie la taille du fichier
            if attachment.file_size > 10 * 1024 * 1024:  # 10 MB
                return request.render('edu_admission_portal.attachment_preview', {
                    'attachment': attachment,
                    'error': "Le fichier est trop volumineux pour la prévisualisation."
                })
            
            # Récupère les données de prévisualisation
            preview_data = attachment.get_preview_data()
            if not preview_data:
                return request.render('edu_admission_portal.attachment_preview', {
                    'attachment': attachment,
                    'error': "Impossible de générer la prévisualisation."
                })
            
            # Ajoute des en-têtes de sécurité
            response = request.render('edu_admission_portal.attachment_preview', {
                'attachment': attachment,
                'preview_data': preview_data,
                'safe_name': url_quote(attachment.name)
            })
            
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            return response
            
        except ValidationError as e:
            return request.render('edu_admission_portal.attachment_preview', {
                'error': str(e)
            })
        except Exception as e:
            _logger.error("Erreur lors de la prévisualisation: %s", str(e))
            return request.render('edu_admission_portal.attachment_preview', {
                'error': "Une erreur est survenue lors de la prévisualisation."
            })
            
    @http.route('/admission/attachment/preview/modal/<int:attachment_id>',
                type='json', auth='user')
    def get_preview_modal(self, attachment_id):
        """
        Retourne le contenu HTML pour la modal de prévisualisation.
        
        Args:
            attachment_id: ID de la pièce jointe
            
        Returns:
            dict: Données pour la modal
        """
        try:
            # Validation de la pièce jointe
            attachment = self._validate_attachment(attachment_id)
            
            # Vérifie la taille du fichier
            if attachment.file_size > 10 * 1024 * 1024:  # 10 MB
                return {
                    'error': "Le fichier est trop volumineux pour la prévisualisation.",
                    'download_url': f'/web/content/{attachment.id}/{url_quote(attachment.name)}'
                }
            
            # Génère le contenu de la modal
            preview_data = attachment.get_preview_data()
            if not preview_data:
                return {
                    'error': "Impossible de générer la prévisualisation.",
                    'download_url': f'/web/content/{attachment.id}/{url_quote(attachment.name)}'
                }
            
            preview_html = request.env['ir.ui.view']._render_template(
                'edu_admission_portal.attachment_preview',
                {
                    'attachment': attachment,
                    'preview_data': preview_data,
                    'safe_name': url_quote(attachment.name)
                }
            )
            
            return {
                'html': preview_html,
                'title': attachment.name,
                'download_url': f'/web/content/{attachment.id}/{url_quote(attachment.name)}'
            }
            
        except ValidationError as e:
            return {'error': str(e)}
        except Exception as e:
            _logger.error("Erreur lors de la génération de la modal: %s", str(e))
            return {'error': "Une erreur est survenue lors de la prévisualisation."} 