from odoo import http
from odoo.http import request
import json
import logging
import traceback
import sys
import base64
import os
import tempfile
from datetime import datetime, timedelta
import hashlib
import hmac
import time

_logger = logging.getLogger(__name__)

# Configuration du logging pour le webhook
WEBHOOK_LOG_DIR = tempfile.gettempdir()
WEBHOOK_LOG_FILE = os.path.join(WEBHOOK_LOG_DIR, 'webhook_debug.log')
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB

# Configuration du logger
webhook_logger = logging.getLogger('webhook_debug')
webhook_logger.setLevel(logging.DEBUG)

# Rotation des logs
handler = logging.handlers.RotatingFileHandler(
    WEBHOOK_LOG_FILE,
    maxBytes=MAX_LOG_SIZE,
    backupCount=3
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
webhook_logger.addHandler(handler)

class WebhookController(http.Controller):
    
    def _clean_old_logs(self):
        """Nettoie les anciens fichiers de log."""
        try:
            now = datetime.now()
            for filename in os.listdir(WEBHOOK_LOG_DIR):
                if filename.startswith('webhook_debug.log.'):
                    filepath = os.path.join(WEBHOOK_LOG_DIR, filename)
                    if os.path.getmtime(filepath) < (now - timedelta(days=7)).timestamp():
                        os.remove(filepath)
        except Exception as e:
            _logger.error("Erreur lors du nettoyage des logs: %s", str(e))
    
    def _validate_token(self, token, form_id):
        """
        Valide le token du webhook avec protection contre les attaques par timing.
        """
        webhook_logger.debug(f"Validation du token pour le formulaire {form_id}")
        if not token:
            webhook_logger.error("Token manquant")
            return False
            
        # Protection contre les attaques par timing
        time.sleep(0.1)
            
        server_config = request.env['limesurvey.server.config'].sudo().search([
            ('webhook_token', '=', token)
        ], limit=1)
        
        if not server_config:
            webhook_logger.error(f"Token invalide: {token}")
            return False
            
        # Vérification que le formulaire appartient à ce serveur
        form = request.env['admission.form.template'].sudo().search([
            ('sid', '=', str(form_id)),
            ('server_config_id', '=', server_config.id)
        ], limit=1)
        
        webhook_logger.debug(f"Formulaire trouvé: {bool(form)}")
        return bool(form)
    
    def _json_response(self, data, status=200):
        """Retourne une réponse JSON formatée avec en-têtes de sécurité."""
        response = request.make_response(
            json.dumps(data),
            headers=[
                ('Content-Type', 'application/json'),
                ('X-Content-Type-Options', 'nosniff'),
                ('X-Frame-Options', 'DENY'),
                ('Content-Security-Policy', "default-src 'none'")
            ],
            status=status
        )
        return response
    
    def _json_error(self, message, status=400, debug_info=None):
        """Retourne une erreur JSON formatée."""
        response = {'error': message}
        if debug_info and request.env.user.has_group('base.group_system'):
            response['debug'] = debug_info
        return self._json_response(response, status=status)

    def _sanitize_response_data(self, response_data):
        """Nettoie les données de réponse."""
        if not isinstance(response_data, dict):
            return {}
            
        sanitized = {}
        for key, value in response_data.items():
            # Vérifie que la clé est une chaîne
            if not isinstance(key, str):
                continue
                
            # Limite la taille des valeurs
            if isinstance(value, str) and len(value) > 10000:
                value = value[:10000]
            elif isinstance(value, dict):
                # Pour les pièces jointes
                if 'content' in value and isinstance(value['content'], str):
                    if len(value['content']) > 10 * 1024 * 1024:  # 10 MB
                        continue
                sanitized[key] = self._sanitize_response_data(value)
            elif isinstance(value, (int, float, bool, str)):
                sanitized[key] = value
                
        return sanitized

    def _prepare_candidate_data(self, form_template, response_data):
        """Prépare les données du candidat à partir des données du formulaire."""
        webhook_logger.debug("Préparation des données du candidat")
        
        # Nettoyage des données
        response_data = self._sanitize_response_data(response_data)
        
        # Récupération du mapping validé
        mapping = request.env['admission.form.mapping'].sudo().search([
            ('form_template_id', '=', form_template.id),
            ('state', '=', 'validated')
        ], limit=1)

        if not mapping:
            webhook_logger.warning(
                "Aucun mapping validé trouvé pour le formulaire %s",
                form_template.name
            )
            return {}

        # Préparation des données
        candidate_data = {}
        attachments = []

        # Pour chaque ligne de mapping validée
        for line in mapping.mapping_line_ids.filtered(lambda l: l.status == 'validated'):
            try:
                value = response_data.get(line.question_code)
                
                if value is None:
                    continue

                # Traitement des pièces jointes
                if line.is_attachment and isinstance(value, dict):
                    # Validation du type MIME
                    mime_type = value.get('type', '').lower()
                    if not mime_type or mime_type.startswith(('text/html', 'text/javascript')):
                        webhook_logger.warning(
                            "Type MIME non autorisé pour la pièce jointe: %s",
                            mime_type
                        )
                        continue
                        
                    # Validation de la taille
                    content = value.get('content', '')
                    if len(content) > 10 * 1024 * 1024:  # 10 MB
                        webhook_logger.warning(
                            "Pièce jointe trop volumineuse: %s",
                            value.get('name', 'Sans nom')
                        )
                        continue
                        
                    attachments.append({
                        'name': value.get('name', 'Sans nom'),
                        'content': content,
                        'type': mime_type,
                        'field': line.question_code
                    })
                    continue

                # Transformation si nécessaire
                if line.mapping_type == 'transform' and line.transform_python:
                    try:
                        value = line.transform_value(value)
                    except Exception as e:
                        webhook_logger.error(
                            "Erreur de transformation pour %s: %s",
                            line.question_code, str(e)
                        )
                        continue

                # Validation si nécessaire
                if line.validation_python:
                    try:
                        if not line.validate_value(value):
                            webhook_logger.warning(
                                "Validation échouée pour %s: %s",
                                line.question_code, value
                            )
                            continue
                    except Exception as e:
                        webhook_logger.error(
                            "Erreur de validation pour %s: %s",
                            line.question_code, str(e)
                        )
                        continue

                # Ajout de la valeur aux données du candidat
                if line.odoo_field:
                    candidate_data[line.odoo_field] = value

            except Exception as e:
                webhook_logger.error(
                    "Erreur lors du traitement de la ligne %s: %s",
                    line.question_code, str(e)
                )
                continue

        return {
            'data': candidate_data,
            'attachments': attachments
        }
    
    @http.route('/admission/webhook/submit', type='json', auth='public', csrf=False)
    def handle_submission(self, **post):
        """Gère les soumissions de formulaires depuis LimeSurvey."""
        try:
            # Nettoyage des anciens logs
            self._clean_old_logs()
            
            # Log de la requête
            webhook_logger.info("Nouvelle soumission reçue")
            webhook_logger.debug("Headers: %s", request.httprequest.headers)
            webhook_logger.debug("Données: %s", request.jsonrequest)
            
            # Vérification du token
            token = request.httprequest.headers.get('X-Webhook-Token')
            if not token:
                webhook_logger.error("Token manquant")
                return self._json_error('Token manquant', status=401)
            
            # Validation des données
            data = request.jsonrequest
            if not data:
                webhook_logger.error("Données manquantes")
                return self._json_error('Données manquantes', status=400)
                
            # Validation du format des données
            required_fields = ['form_id', 'response_id', 'submitdate', 'response_data']
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                webhook_logger.error("Champs manquants: %s", missing_fields)
                return self._json_error(
                    f'Champs requis manquants: {", ".join(missing_fields)}',
                    status=400
                )
                
            # Validation du form_id
            form_id = data.get('form_id')
            if not str(form_id).isdigit():
                webhook_logger.error("ID de formulaire invalide: %s", form_id)
                return self._json_error('ID de formulaire invalide', status=400)
                
            # Validation du token avec le form_id
            if not self._validate_token(token, form_id):
                webhook_logger.error("Token invalide pour le formulaire %s", form_id)
                return self._json_error('Token invalide', status=401)
                
            # Recherche du template de formulaire
            form_template = request.env['admission.form.template'].sudo().search([
                ('sid', '=', str(form_id))
            ], limit=1)
            
            if not form_template:
                webhook_logger.error("Template de formulaire non trouvé: %s", form_id)
                return self._json_error('Formulaire non trouvé', status=404)
                
            # Préparation des données du candidat
            try:
                prepared_data = self._prepare_candidate_data(
                    form_template,
                    data.get('response_data', {})
                )
                
                if not prepared_data.get('data'):
                    webhook_logger.error("Aucune donnée valide après préparation")
                    return self._json_error(
                        'Aucune donnée valide après traitement',
                        status=400
                    )
                    
                # Ajout des métadonnées
                prepared_data['data'].update({
                    'response_id': data['response_id'],
                    'submit_date': data['submitdate'],
                    'form_template_id': form_template.id,
                })
                
                # Création du candidat
                candidate = request.env['admission.candidate'].sudo().create(
                    prepared_data['data']
                )
                
                # Traitement des pièces jointes
                for attachment in prepared_data.get('attachments', []):
                    try:
                        # Validation supplémentaire du contenu
                        if not attachment.get('content'):
                            continue
                            
                        # Décodage du contenu
                        try:
                            file_content = base64.b64decode(attachment['content'])
                        except:
                            webhook_logger.warning(
                                "Contenu de fichier invalide: %s",
                                attachment.get('name', 'Sans nom')
                            )
                            continue
                            
                        # Validation de la taille
                        if len(file_content) > 10 * 1024 * 1024:  # 10 MB
                            webhook_logger.warning(
                                "Fichier trop volumineux: %s",
                                attachment.get('name', 'Sans nom')
                            )
                            continue
                            
                        # Création de la pièce jointe
                        attachment_vals = {
                            'name': attachment.get('name', 'Sans nom'),
                            'datas': base64.b64encode(file_content),
                            'mimetype': attachment.get('type', 'application/octet-stream'),
                            'res_model': 'admission.candidate',
                            'res_id': candidate.id,
                            'description': f"Champ: {attachment.get('field', 'inconnu')}"
                        }
                        
                        request.env['ir.attachment'].sudo().create(attachment_vals)
                        
                    except Exception as e:
                        webhook_logger.error(
                            "Erreur lors du traitement de la pièce jointe %s: %s",
                            attachment.get('name', 'Sans nom'),
                            str(e)
                        )
                        continue
                
                # Envoi de la notification
                if form_template.notify_on_submit:
                    try:
                        template = request.env.ref(
                            'edu_admission_portal.email_template_new_submission'
                        )
                        if template:
                            template.sudo().send_mail(candidate.id)
                    except Exception as e:
                        webhook_logger.error(
                            "Erreur lors de l'envoi de la notification: %s",
                            str(e)
                        )
                
                webhook_logger.info(
                    "Candidat créé avec succès: %s (ID: %s)",
                    candidate.name,
                    candidate.id
                )
                
                return self._json_response({
                    'success': True,
                    'candidate_id': candidate.id
                })
                
            except Exception as e:
                webhook_logger.error(
                    "Erreur lors de la création du candidat: %s\n%s",
                    str(e),
                    traceback.format_exc()
                )
                return self._json_error(
                    'Erreur lors de la création du candidat',
                    status=500,
                    debug_info=str(e)
                )
                
        except Exception as e:
            webhook_logger.error(
                "Erreur inattendue: %s\n%s",
                str(e),
                traceback.format_exc()
            )
            return self._json_error(
                'Erreur inattendue',
                status=500,
                debug_info=str(e)
            ) 