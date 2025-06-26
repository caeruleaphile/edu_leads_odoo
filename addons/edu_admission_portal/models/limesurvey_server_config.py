import logging
import xmlrpc.client
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class LimeSurveyServerConfig(models.Model):
    _name = 'limesurvey.server.config'
    _description = 'Configuration du Serveur LimeSurvey'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nom',
        required=True,
        tracking=True,
    )
    base_url = fields.Char(
        string='URL du Serveur',
        required=True,
        help='URL complète du serveur LimeSurvey (ex: http://localhost/limesurvey)',
        tracking=True,
    )
    api_username = fields.Char(
        string="Nom d'utilisateur API",
        required=True,
        tracking=True,
    )
    api_password = fields.Char(
        string='Mot de passe API',
        required=True,
        tracking=True,
    )
    connection_status = fields.Selection([
        ('not_tested', 'Non Testé'),
        ('connected', 'Connecté'),
        ('failed', 'Échec de Connexion')
    ], string='Statut de Connexion',
        default='not_tested',
        tracking=True,
    )
    last_sync_date = fields.Datetime(
        string='Dernière Synchronisation',
        tracking=True,
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
    )
    webhook_token = fields.Char(
        string='Token Webhook',
        help='Token de sécurité pour l\'authentification des webhooks LimeSurvey',
        copy=False,
    )
    form_template_ids = fields.One2many(
        'admission.form.template',
        'server_config_id',
        string='Templates de Formulaires',
        compute='_compute_empty_templates',
    )

    _sql_constraints = [
        ('name_uniq', 
         'UNIQUE(name, active)',
         'Le nom de la configuration doit être unique pour les configurations actives!')
    ]

    def unlink(self):
        """Surcharge de la méthode de suppression pour archiver au lieu de supprimer."""
        for record in self:
            if record.form_template_ids:
                # Si des templates sont liés, on archive au lieu de supprimer
                record.write({'active': False})
                return True
        return super(LimeSurveyServerConfig, self).unlink()

    def _check_server_config(self, server):
        """Vérifie la configuration du serveur LimeSurvey et retourne les informations de version."""
        try:
            # Essai de la méthode get_site_settings sans session
            try:
                settings = server.get_site_settings()
                _logger.info("Site settings (no session): %s", settings)
                return settings
            except:
                pass

            # Essai avec différents formats d'authentification basique
            try:
                settings = server.get_site_settings(self.api_username, self.api_password)
                _logger.info("Site settings (basic auth): %s", settings)
                return settings
            except:
                pass

            # Essai avec paramètres nommés
            try:
                settings = server.get_site_settings({
                    'username': self.api_username,
                    'password': self.api_password
                })
                _logger.info("Site settings (named params): %s", settings)
                return settings
            except:
                pass

            return None
        except Exception as e:
            _logger.warning("Impossible de récupérer les paramètres du site: %s", str(e))
            return None

    def _get_rpc_session(self):
        """Établit une session XML-RPC avec le serveur LimeSurvey."""
        try:
            # Construction de l'URL RPC
            base_url = self.base_url.rstrip('/')
            _logger.info("URL de base: %s", base_url)

            # Essai avec différentes variantes d'URL
            urls_to_try = [
                f"{base_url}/admin/remotecontrol",  # Sans index.php
                f"{base_url}/index.php/admin/remotecontrol",  # Avec index.php
                f"{base_url}/index.php/admin/remotecontrol/sa/index",  # Format complet
            ]

            last_error = None
            for rpc_url in urls_to_try:
                try:
                    _logger.info("=== Tentative avec URL: %s ===", rpc_url)
                    
                    # Création du client RPC
                    server = xmlrpc.client.ServerProxy(
                        rpc_url,
                        allow_none=True,
                        use_builtin_types=True,
                        verbose=True
                    )
                    
                    # Test de la méthode system.listMethods si disponible
                    try:
                        methods = server.system.listMethods()
                        _logger.info("Méthodes disponibles: %s", methods)
                    except:
                        _logger.info("Méthode listMethods non disponible")
                    
                    # Tentative d'authentification
                    _logger.info("Tentative d'authentification avec user: %s", self.api_username)
                    session_key = server.get_session_key(self.api_username, self.api_password)
                    
                    if isinstance(session_key, str) and session_key:
                        _logger.info("Authentification réussie avec URL: %s", rpc_url)
                        return server, session_key
                    else:
                        _logger.warning("Réponse invalide du serveur: %s", session_key)
                        
                except Exception as e:
                    _logger.warning("Échec avec URL %s: %s", rpc_url, str(e))
                    last_error = e
                    continue
            
            # Si nous arrivons ici, aucune URL n'a fonctionné
            _logger.error("Toutes les tentatives de connexion ont échoué")
            _logger.error("Dernière erreur: %s", str(last_error))
            
            # Message d'erreur détaillé pour l'utilisateur
            raise UserError(_(
                "Échec de l'authentification LimeSurvey.\n\n"
                "Vérifiez que :\n"
                "1. L'URL du serveur est correcte\n"
                "2. Les identifiants API sont corrects\n"
                "3. L'API RemoteControl2 est activée dans LimeSurvey\n"
                "   - Allez dans Configuration > Global settings > Interfaces\n"
                "   - Activez 'RPC interface enabled'\n"
                "   - Activez 'JSON-RPC' et 'XML-RPC'\n"
                "4. Vous utilisez un compte administrateur\n\n"
                "URLs testées:\n%s\n\n"
                "Dernière erreur: %s"
            ) % ("\n".join(urls_to_try), str(last_error)))
                
        except Exception as e:
            _logger.error("=== Erreur de connexion ===")
            _logger.error("Type: %s", type(e).__name__)
            _logger.error("Message: %s", str(e))
            raise UserError(_(
                "Impossible de se connecter au serveur LimeSurvey.\n\n"
                "Erreur : %s\n\n"
                "Vérifiez que le serveur est accessible et que l'API est activée."
            ) % str(e))
        finally:
            _logger.info("=== Fin de la tentative de connexion RPC ===\n")

    def action_test_connection(self):
        """Bouton pour tester la connexion au serveur LimeSurvey."""
        self.ensure_one()
        try:
            server, session_key = self._get_rpc_session()
            
            # Test de la connexion avec une commande simple
            try:
                server.list_surveys(session_key)
                _logger.info("Test de list_surveys réussi")
            except:
                try:
                    server.list_surveys({'sSessionKey': session_key})
                    _logger.info("Test de list_surveys réussi avec paramètres nommés")
                except Exception as e:
                    _logger.warning("Test de list_surveys échoué: %s", str(e))
            
            self.write({
                'connection_status': 'connected',
                'last_sync_date': fields.Datetime.now()
            })
            
            # Libération de la session
            try:
                server.release_session_key(session_key)
            except:
                try:
                    server.release_session_key({'sSessionKey': session_key})
                except Exception as e:
                    _logger.warning("Erreur lors de la libération de la session: %s", str(e))
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('Connexion au serveur LimeSurvey établie avec succès.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.connection_status = 'failed'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_sync_forms(self):
        """Synchronise les formulaires depuis LimeSurvey."""
        self.ensure_one()
        server, session_key = self._get_rpc_session()
        
        try:
            # Formats de list_surveys à essayer
            list_surveys_formats = [
                lambda: server.list_surveys(session_key),
                lambda: server.list_surveys({'sSessionKey': session_key}),
                lambda: server.list_surveys(sSessionKey=session_key),
                lambda: server.list_surveys(session_key, self.api_username)
            ]
            
            surveys = None
            list_error = None
            
            for list_attempt in list_surveys_formats:
                try:
                    _logger.info("Tentative de récupération des sondages...")
                    surveys = list_attempt()
                    if surveys:
                        _logger.info("Sondages récupérés avec succès!")
                        break
                except Exception as e:
                    list_error = str(e)
                    _logger.warning("Échec de récupération des sondages: %s", str(e))
                    continue
            
            if not surveys:
                raise UserError(_(
                    "Impossible de récupérer la liste des sondages.\n"
                    "Dernière erreur : %s"
                ) % list_error)
            
            _logger.info("Sondages trouvés: %s", surveys)
                
            FormTemplate = self.env['admission.form.template']
            synced_count = 0
            
            for survey in surveys:
                sid = str(survey.get('sid', ''))
                if not sid:
                    continue
                
                # Formats de get_survey_properties à essayer
                property_formats = [
                    lambda: server.get_survey_properties(session_key, int(sid), None),
                    lambda: server.get_survey_properties(session_key, int(sid), ['active', 'expires', 'startdate']),
                ]
                
                survey_properties = None
                for prop_attempt in property_formats:
                    try:
                        survey_properties = prop_attempt()
                        if survey_properties:
                            break
                    except Exception as e:
                        _logger.warning("Tentative de get_survey_properties échouée: %s", str(e))
                        continue
                
                if not survey_properties:
                    _logger.warning("Impossible de récupérer les propriétés du sondage %s", sid)
                    continue
                
                vals = {
                    'sid': sid,
                    'title': survey.get('surveyls_title', ''),
                    'description': survey.get('surveyls_description', ''),
                    'is_active': survey_properties.get('active') == 'Y',
                    'owner': str(survey.get('owner_id', '')),
                    'server_config_id': self.id,
                    'sync_status': 'synced',
                }
                
                # Création ou mise à jour du template
                existing_template = FormTemplate.search([
                    ('sid', '=', sid),
                    ('server_config_id', '=', self.id)
                ])
                
                if existing_template:
                    existing_template.write(vals)
                else:
                    FormTemplate.create(vals)
                
                synced_count += 1
                    
            self.last_sync_date = fields.Datetime.now()
            
            if synced_count == 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Attention'),
                        'message': _('Aucun formulaire n\'a pu être synchronisé. Vérifiez les permissions et l\'existence des formulaires.'),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Succès'),
                    'message': _('%d formulaire(s) synchronisé(s) avec succès') % synced_count,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation des formulaires: %s", str(e))
            # Marquer tous les formulaires comme "error"
            self.env['admission.form.template'].search([
                ('server_config_id', '=', self.id)
            ]).write({'sync_status': 'error'})
            
            raise UserError(_("Erreur de synchronisation: %s") % str(e))
            
        finally:
            # Formats de release_session_key à essayer
            if session_key:
                release_formats = [
                    lambda: server.release_session_key(session_key),
                    lambda: server.release_session_key({'sSessionKey': session_key}),
                    lambda: server.release_session_key(sSessionKey=session_key)
                ]
                
                for release_attempt in release_formats:
                    try:
                        release_attempt()
                        break
                    except Exception as e:
                        _logger.warning("Tentative de libération de session échouée: %s", str(e))
                        continue

    def generate_webhook_token(self):
        """Génère un nouveau token pour le webhook."""
        import secrets
        self.ensure_one()
        self.webhook_token = secrets.token_urlsafe(32)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Token Généré'),
                'message': _('Un nouveau token a été généré avec succès.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_force_delete(self):
        """Supprime définitivement la configuration, même si elle a des templates liés."""
        self.ensure_one()
        if self.active:
            raise UserError(_("Impossible de supprimer une configuration active. Veuillez d'abord l'archiver."))
            
        # Archiver d'abord tous les templates liés
        self.form_template_ids.write({'active': False})
        
        # Suppression définitive
        self.unlink()
        
        # Retourner une action pour rafraîchir la vue
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _compute_empty_templates(self):
        """Retourne toujours une liste vide pour masquer les templates."""
        for record in self:
            record.form_template_ids = [(5, 0, 0)]  # Vide la liste 