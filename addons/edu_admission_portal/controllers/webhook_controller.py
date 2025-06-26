from odoo import http
from odoo.http import request
import json
import logging
import traceback
import sys
import base64
import os

_logger = logging.getLogger(__name__)

# Configuration du logging pour le webhook
WEBHOOK_LOG_FILE = '/tmp/webhook_debug.log'
os.makedirs(os.path.dirname(WEBHOOK_LOG_FILE), exist_ok=True)

webhook_logger = logging.getLogger('webhook_debug')
webhook_logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(WEBHOOK_LOG_FILE)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
webhook_logger.addHandler(handler)

class WebhookController(http.Controller):
    
    def _validate_token(self, token, form_id):
        """Valide le token du webhook."""
        if not token:
            return False
            
        server_config = request.env['limesurvey.server.config'].sudo().search([
            ('webhook_token', '=', token)
        ], limit=1)
        
        if not server_config:
            return False
            
        # Vérifier que le formulaire appartient à ce serveur
        form = request.env['admission.form.template'].sudo().search([
            ('sid', '=', str(form_id)),
            ('server_config_id', '=', server_config.id)
        ], limit=1)
        
        return bool(form)
    
    def _json_response(self, data, status=200):
        """Retourne une réponse JSON formatée."""
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status
        )
    
    def _json_error(self, message, status=400, debug_info=None):
        """Retourne une erreur JSON formatée."""
        response = {'error': message}
        if debug_info:
            response['debug'] = debug_info
        return self._json_response(response, status=status)
    
    @http.route('/admission/webhook/submit', type='json', auth='public', csrf=False)
    def handle_submission(self, **post):
        """Gère les soumissions de formulaires depuis LimeSurvey."""
        try:
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
            
            required_fields = ['form_id', 'response_id', 'response_data']
            if not all(field in data for field in required_fields):
                webhook_logger.error("Champs obligatoires manquants: %s", 
                    [f for f in required_fields if f not in data])
                return self._json_error('Champs obligatoires manquants', status=400)
            
            # Validation du token pour ce formulaire
            if not self._validate_token(token, data['form_id']):
                webhook_logger.error("Token invalide pour le formulaire %s", data['form_id'])
                return self._json_error('Token invalide', status=401)
            
            # Récupération du template
            form_template = request.env['admission.form.template'].sudo().search([
                ('sid', '=', str(data['form_id']))
            ], limit=1)
            
            if not form_template:
                webhook_logger.error("Formulaire non trouvé: %s", data['form_id'])
                return self._json_error('Formulaire non trouvé', status=404)
            
            # Vérification si la réponse existe déjà
            existing = request.env['admission.candidate'].sudo().search([
                ('form_id', '=', form_template.id),
                ('response_id', '=', str(data['response_id']))
            ], limit=1)
            
            if existing:
                webhook_logger.warning("Réponse déjà existante: %s", data['response_id'])
                return self._json_error('Réponse déjà enregistrée', status=409)
            
            try:
                # Validation des champs requis dans les données de réponse
                response_data = data['response_data']
                required_response_fields = {
                    'G01Q02': 'Nom',
                    'G01Q03': 'Prénom',
                    'G03Q14': 'Email',
                    'G01Q01': 'Civilité',
                }
                
                missing_fields = []
                for field, label in required_response_fields.items():
                    if not response_data.get(field):
                        missing_fields.append(label)
                
                if missing_fields:
                    webhook_logger.error("Champs requis manquants dans les données: %s", missing_fields)
                    return self._json_error(
                        f"Champs requis manquants dans les données: {', '.join(missing_fields)}",
                        status=400
                    )
                
                # Création du candidat
                candidate = request.env['admission.candidate'].sudo().create({
                    'form_id': form_template.id,
                    'response_id': str(data['response_id']),
                    'response_data': response_data,
                    'status': 'new'
                })
                
                webhook_logger.info("Candidat créé: %s", candidate.id)
                
                # Traitement des pièces jointes
                for attachment in data.get('attachments', []):
                    try:
                        request.env['ir.attachment'].sudo().create({
                            'name': attachment['name'],
                            'datas': attachment['content'],
                            'mimetype': attachment.get('type', 'application/octet-stream'),
                            'res_model': 'admission.candidate',
                            'res_id': candidate.id,
                        })
                        webhook_logger.info("Pièce jointe créée: %s", attachment['name'])
                    except Exception as e:
                        webhook_logger.error("Erreur lors de la création de la pièce jointe %s: %s",
                            attachment.get('name', 'unknown'), str(e))
                
                # Forcer le recalcul du compteur
                form_template.clear_caches()
                
                return self._json_response({
                    'status': 'success',
                    'message': 'Candidature enregistrée avec succès',
                    'candidate_id': candidate.id
                })
                
            except Exception as e:
                webhook_logger.error("Erreur lors de la création du candidat: %s", str(e))
                return self._json_error('Erreur lors de la création du candidat', status=500,
                    debug_info=str(e))
            
        except Exception as e:
            webhook_logger.error("Erreur générale: %s\n%s", str(e), traceback.format_exc())
            return self._json_error('Erreur interne du serveur', status=500) 