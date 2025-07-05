import logging
import xmlrpc.client
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
import re
import json
import traceback
import ssl

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

    @api.model
    def clean_limesurvey_url(self, url, url_type='base'):
        """
        Nettoie et normalise les URLs LimeSurvey.
        :param url: URL à nettoyer
        :param url_type: Type d'URL ('base', 'survey', 'api')
        :return: URL nettoyée
        """
        if not url:
            return ''
            
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        
        # Retire les espaces
        url = url.strip()
        
        try:
            # Parse l'URL
            parsed = urlparse(url)
            
            # Nettoie le chemin
            path = parsed.path.strip('/')
            
            # Sépare le chemin en segments
            segments = [seg for seg in path.split('/') if seg]
            
            # Construit le chemin selon le type d'URL
            if url_type == 'api':
                # Pour l'API RemoteControl
                clean_path = '/limesurvey/index.php/admin/remotecontrol'
            elif url_type == 'survey':
                # Pour les URLs de sondage, on garde juste l'ID du sondage
                survey_id = next((seg for seg in segments if seg.isdigit()), None)
                if survey_id:
                    clean_path = f'/limesurvey/index.php/{survey_id}'
                else:
                    clean_path = '/limesurvey/index.php'
            else:
                # URL de base
                clean_path = '/limesurvey'
            
            # Préserve les paramètres de requête
            query_params = parse_qs(parsed.query)
            if url_type == 'survey' and 'lang' not in query_params:
                query_params['lang'] = ['fr']
            
            # Reconstruit l'URL
            clean_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                clean_path,
                '',
                urlencode(query_params, doseq=True),
                ''
            ))
            
            _logger.info("URL originale (%s): %s", url_type, url)
            _logger.info("URL nettoyée (%s): %s", url_type, clean_url)
            
            return clean_url
            
        except Exception as e:
            _logger.error("Erreur lors du nettoyage de l'URL: %s", str(e))
            return url

    def _clean_base_url(self, url):
        """Nettoie l'URL de base en retirant les chemins d'API."""
        return self.clean_limesurvey_url(url, 'base')

    def _check_api_accessibility(self, base_url):
        """Vérifie l'accessibilité de l'API avant la tentative de connexion."""
        try:
            # Test de l'URL de base
            response = requests.get(base_url, timeout=5, verify=False)
            _logger.info("Test URL de base - Status: %s", response.status_code)
            
            # Test des différents chemins d'API
            api_paths = [
                'admin/remotecontrol',
                'index.php/admin/remotecontrol',
                'remotecontrol'
            ]
            
            for path in api_paths:
                api_url = urljoin(base_url + '/', path)
                try:
                    response = requests.post(
                        api_url,
                        json={'method': 'get_session_key', 'params': [self.api_username, self.api_password]},
                        headers={'Content-Type': 'application/json'},
                        timeout=5,
                        verify=False
                    )
                    _logger.info("Test API %s - Status: %s", api_url, response.status_code)
                    if response.status_code in [200, 401]:  # 401 est acceptable car cela signifie que l'API est accessible mais nécessite une authentification
                        return True
                except Exception as e:
                    _logger.warning("Échec du test API %s: %s", api_url, str(e))
                    continue
            
            return False
            
        except Exception as e:
            _logger.error("Erreur lors du test d'accessibilité: %s", str(e))
            return False

    def _get_csrf_token(self, base_url):
        """Récupère le token CSRF de LimeSurvey."""
        import requests
        from urllib.parse import urljoin
        import re
        
        try:
            # Créer une session pour maintenir les cookies
            session = requests.Session()
            
            # Construire l'URL de login
            login_url = urljoin(base_url + '/', 'index.php/admin/authentication/sa/login')
            _logger.info("Tentative d'accès à l'URL de login: %s", login_url)
            
            # Accéder à la page de login pour obtenir le token CSRF
            response = session.get(login_url, verify=False, allow_redirects=True)
            _logger.info("Status code de la réponse: %s", response.status_code)
            
            if response.status_code == 404:
                # Essayer une URL alternative
                login_url = urljoin(base_url + '/', 'admin/authentication/sa/login')
                _logger.info("Tentative avec URL alternative: %s", login_url)
                response = session.get(login_url, verify=False, allow_redirects=True)
            
            # Chercher le token CSRF dans la page
            csrf_token = None
            if response.text:
                # Chercher dans les méta tags
                csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.text)
                if csrf_match:
                    csrf_token = csrf_match.group(1)
                else:
                    # Chercher dans les formulaires
                    csrf_match = re.search(r'name="YII_CSRF_TOKEN" value="([^"]+)"', response.text)
                    if csrf_match:
                        csrf_token = csrf_match.group(1)
                    else:
                        # Chercher dans les scripts
                        csrf_match = re.search(r'csrf_token\s*=\s*[\'"]([^\'"]+)[\'"]', response.text)
                        if csrf_match:
                            csrf_token = csrf_match.group(1)
            
            if csrf_token:
                _logger.info("Token CSRF trouvé: %s", csrf_token)
                return csrf_token, session.cookies
            else:
                _logger.warning("Aucun token CSRF trouvé dans la réponse. Status: %s", response.status_code)
                _logger.debug("Contenu de la réponse: %s", response.text[:500])  # Log des premiers 500 caractères
                return None, None
                
        except Exception as e:
            _logger.error("Erreur lors de la récupération du token CSRF: %s", str(e))
            return None, None

    def _get_rpc_session(self):
        """
        Établit une connexion RPC avec le serveur LimeSurvey.
        Retourne l'objet serveur avec la session_key comme attribut ou None en cas d'échec.
        """
        try:
            # Construction de l'URL de l'API
            api_url = self.clean_limesurvey_url(self.base_url, 'api')
            _logger.info("URL de l'API: %s", api_url)
            
            # Vérification de l'accessibilité
            if not self._check_api_accessibility(self.base_url):
                _logger.error("L'API LimeSurvey n'est pas accessible")
                return None
            
            # Création du serveur RPC
            server = xmlrpc.client.ServerProxy(
                api_url,
                allow_none=True,
                use_datetime=True,
                context=ssl._create_unverified_context()
            )
            
            # S'assurer que les identifiants sont des chaînes
            username = str(self.api_username or '')
            password = str(self.api_password or '')
            
            if not username or not password:
                _logger.error("Les identifiants API ne peuvent pas être vides")
                return None
            
            try:
                # Essai avec la nouvelle méthode (LimeSurvey 5+)
                try:
                    session_key = server.get_session_key(username, password)
                    _logger.info("Connexion réussie avec la nouvelle méthode")
                except xmlrpc.client.Fault as e:
                    if "Calling parameters do not match signature" in str(e):
                        # Fallback pour l'ancienne méthode
                        _logger.info("Tentative avec l'ancienne méthode...")
                        session_key = server.get_session_key(username, password, 'Odoo')
                        _logger.info("Connexion réussie avec l'ancienne méthode")
                    else:
                        _logger.error("Erreur RPC lors de l'authentification: %s", str(e))
                        return None
                except Exception as e:
                    _logger.error("Erreur lors de la tentative de connexion: %s", str(e))
                    return None
            except Exception as e:
                _logger.error("Erreur lors de la tentative de connexion: %s", str(e))
                return None
            
            if not session_key or session_key == 'Invalid user name or password':
                _logger.error("Identifiants LimeSurvey invalides")
                return None
                
            # Ajout de la clé de session comme attribut du serveur
            server.session_key = session_key
            _logger.info("Session LimeSurvey établie avec succès")
            
            return server
            
        except xmlrpc.client.Fault as e:
            _logger.error("Erreur RPC lors de la connexion: %s", str(e))
            return None
        except Exception as e:
            _logger.error("Erreur inattendue lors de la connexion: %s", str(e))
            return None

    def action_test_connection(self):
        """Teste la connexion au serveur LimeSurvey."""
        try:
            # Test de la connexion
            server = self._get_rpc_session()
            
            # Test de l'API avec une requête simple
            try:
                # Essai avec list_surveys qui est plus fiable
                surveys = server.list_surveys(server.session_key)
                _logger.info("Test de connexion réussi avec list_surveys")
            except xmlrpc.client.Fault as e:
                try:
                    # Fallback pour l'ancienne méthode avec paramètres nommés
                    surveys = server.list_surveys({'sSessionKey': server.session_key})
                    _logger.info("Test de connexion réussi avec list_surveys (paramètres nommés)")
                except xmlrpc.client.Fault as e2:
                    _logger.error("Échec de list_surveys: %s, %s", str(e), str(e2))
                    raise ValidationError(_(
                        "Impossible de se connecter au serveur LimeSurvey.\n\n"
                        "Vérifiez que :\n"
                        "1. L'URL du serveur est correcte\n"
                        "2. Les identifiants API sont valides\n"
                        "3. L'API RemoteControl2 est activée\n\n"
                        "Détail de l'erreur : %s"
                    ) % str(e2))
            
            # Mise à jour du statut
            self.write({
                'connection_status': 'connected',
                'last_sync_date': fields.Datetime.now()
            })
            
            # Message de succès
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connexion réussie'),
                    'message': _('Connecté au serveur LimeSurvey'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error("Erreur lors du test de connexion: %s", str(e))
            
            # Mise à jour du statut
            self.write({'connection_status': 'failed'})
            
            # Message d'erreur
            raise ValidationError(_(
                "Impossible de se connecter au serveur LimeSurvey.\n\n"
                "Vérifiez que :\n"
                "1. L'URL du serveur est correcte\n"
                "2. Les identifiants API sont valides\n"
                "3. L'API RemoteControl2 est activée\n\n"
                "Détail de l'erreur : %s"
            ) % str(e))

    def action_sync_forms(self):
        """Synchronise tous les formulaires depuis LimeSurvey."""
        error_details = []
        try:
            server = self._get_rpc_session()
            _logger.info("Session RPC obtenue avec succès")
            
            # Récupération de la liste des sondages
            try:
                surveys = server.list_surveys(server.session_key)
                _logger.info("Liste des sondages récupérée: %s", surveys)
            except Exception as e:
                error_msg = f"Erreur lors de la récupération de la liste des sondages: {str(e)}"
                _logger.error(error_msg)
                error_details.append(error_msg)
                surveys = []
            
            if not surveys:
                _logger.warning("Aucun formulaire trouvé sur le serveur")
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Synchronisation terminée'),
                        'message': _('Aucun formulaire trouvé sur le serveur'),
                        'type': 'warning',
                    }
                }
            
            # Compteurs pour le suivi
            created = 0
            updated = 0
            errors = 0
            skipped = 0
            responses_count = 0
            
            # Traitement de chaque sondage
            for survey in surveys:
                try:
                    sid = str(survey.get('sid'))
                    if not sid:
                        error_msg = "Sondage ignoré: pas de SID"
                        _logger.warning(error_msg)
                        error_details.append(error_msg)
                        skipped += 1
                        continue

                    _logger.info("Traitement du sondage %s", sid)
                    
                    # Vérification si le template existe déjà
                    template = self.env['admission.form.template'].search([
                        ('sid', '=', sid),
                        ('server_config_id', '=', self.id)
                    ], limit=1)
                    
                    # Récupération des propriétés du formulaire
                    survey_properties = self.get_survey_properties(sid)
                    if not survey_properties:
                        error_msg = f"Impossible de récupérer les propriétés du sondage {sid}"
                        _logger.error(error_msg)
                        error_details.append(error_msg)
                        errors += 1
                        continue
                        
                    # Préparation des valeurs
                    vals = {
                        'sid': sid,
                        'server_config_id': self.id,
                        'title': survey_properties.get('surveyls_title', ''),
                        'description': survey_properties.get('surveyls_description', ''),
                        'is_active': survey_properties.get('active', 'N') == 'Y',
                        'owner': survey_properties.get('owner_id'),
                        'metadata': survey_properties,
                    }
                    
                    # Mise à jour ou création du template
                    if template:
                        template.write(vals)
                        updated += 1
                        _logger.info("Template mis à jour: %s", template.name)
                    else:
                        template = self.env['admission.form.template'].create(vals)
                        created += 1
                        _logger.info("Nouveau template créé pour le sondage %s", sid)

                    # Synchronisation des réponses si le template existe
                    if template and survey_properties.get('response_count', 0) > 0:
                        try:
                            # Récupération des réponses
                            responses = server.export_responses(
                                server.session_key,
                                int(sid),
                                'json'
                            )
                            
                            if responses and isinstance(responses, str):
                                responses_data = json.loads(responses)
                                if isinstance(responses_data, dict):
                                    for response in responses_data.get('responses', []):
                                        try:
                                            # Création ou mise à jour du candidat
                                            template._process_survey_response(response)
                                            responses_count += 1
                                        except Exception as e:
                                            error_msg = f"Erreur lors du traitement de la réponse: {str(e)}"
                                            _logger.error(error_msg)
                                            error_details.append(error_msg)
                                            
                        except Exception as e:
                            error_msg = f"Erreur lors de la synchronisation des réponses du sondage {sid}: {str(e)}"
                            _logger.error(error_msg)
                            error_details.append(error_msg)
                            errors += 1
                            
                except Exception as e:
                    error_msg = f"Erreur lors du traitement du sondage {sid}: {str(e)}"
                    _logger.error("%s\n%s", error_msg, traceback.format_exc())
                    error_details.append(error_msg)
                    errors += 1
            # Mise à jour de la date de synchronisation
            self.write({'last_sync_date': fields.Datetime.now()})
            
            # Message de résultat
            message = _(
                'Synchronisation terminée\n\n'
                'Formulaires créés : %(created)d\n'
                'Formulaires mis à jour : %(updated)d\n'
                'Réponses synchronisées : %(responses)d\n'
                'Erreurs : %(errors)d\n'
                'Ignorés : %(skipped)d\n'
                'Total traité : %(total)d\n\n'
            ) % {
                'created': created,
                'updated': updated,
                'responses': responses_count,
                'errors': errors,
                'skipped': skipped,
                'total': len(surveys)
            }
            
            if error_details:
                message += _('Détails des erreurs :\n%s') % '\n'.join(error_details)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisation terminée'),
                    'message': message,
                    'sticky': True if errors > 0 else False,
                    'type': 'success' if errors == 0 else 'warning',
                }
            }
            
        except Exception as e:
            error_msg = f"Erreur lors de la synchronisation: {str(e)}"
            _logger.error("%s\n%s", error_msg, traceback.format_exc())
            self.write({'connection_status': 'failed'})
            
            if error_details:
                error_msg += f"\n\nDétails des erreurs précédentes :\n{chr(10).join(error_details)}"
            
            raise ValidationError(_(
                "Erreur lors de la synchronisation des formulaires.\n\n"
                "Détail : %s"
            ) % error_msg)

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

    def get_survey_properties(self, sid):
        """Récupère les propriétés d'un formulaire LimeSurvey."""
        try:
            # Obtention de la session RPC
            server = self._get_rpc_session()
            if not server:
                raise ValidationError(_("Impossible de se connecter au serveur LimeSurvey"))

            _logger.info("Tentative de récupération des propriétés pour le sondage %s", sid)
            
            # Initialisation des variables
            languages = ['fr']  # Langue par défaut
            default_lang = 'fr'
            survey_properties = {}
            
            # Récupération des langues disponibles
            try:
                lang_result = server.get_survey_languages(server.session_key, int(sid))
                if lang_result and isinstance(lang_result, (list, tuple)):
                    languages = lang_result
                    default_lang = languages[0] if languages else 'fr'
                    _logger.info("Langues disponibles: %s", languages)
            except Exception as e:
                _logger.warning("Impossible de récupérer les langues: %s", str(e))

            # Récupération des propriétés pour chaque langue
            title = None
            for lang in languages:
                try:
                    lang_properties = server.get_language_properties(
                        server.session_key,
                        int(sid),
                        lang
                    )
                    if isinstance(lang_properties, dict):
                        # Récupérer le titre si disponible
                        survey_title = lang_properties.get('surveyls_title', '').strip()
                        if survey_title and survey_title != '' and not survey_title.startswith('Formulaire'):
                            title = survey_title
                            survey_properties['surveyls_title'] = title
                            _logger.info("Titre trouvé en langue %s: %s", lang, title)
                        survey_properties.update(lang_properties)
                        _logger.info("Propriétés de langue %s: %s", lang, lang_properties)
                        
                        # Si c'est la langue par défaut, prioriser son titre
                        if lang == default_lang and survey_title:
                            title = survey_title
                            survey_properties['surveyls_title'] = title
                            
                except Exception as e:
                    _logger.warning("Impossible de récupérer les propriétés pour la langue %s: %s", lang, str(e))

            # Récupération des propriétés de base
            try:
                base_properties = server.get_survey_properties(
                    server.session_key,
                    int(sid)
                )
                if isinstance(base_properties, dict):
                    # Récupérer le titre des propriétés de base si pas encore trouvé
                    if not title:
                        base_title = base_properties.get('surveyls_title', '').strip()
                        if base_title and base_title != '' and not base_title.startswith('Formulaire'):
                            title = base_title
                            survey_properties['surveyls_title'] = title
                            _logger.info("Titre trouvé dans les propriétés de base: %s", title)
                    
                    # Ajouter les autres propriétés sans écraser le titre si déjà trouvé
                    if title:
                        base_properties.pop('surveyls_title', None)
                    survey_properties.update(base_properties)
                    _logger.info("Propriétés de base récupérées avec succès")
            except xmlrpc.client.Fault:
                try:
                    base_properties = server.get_survey_properties(
                        server.session_key,
                        int(sid),
                        None
                    )
                    if isinstance(base_properties, dict):
                        # Récupérer le titre des propriétés de base si pas encore trouvé
                        if not title:
                            base_title = base_properties.get('surveyls_title', '').strip()
                            if base_title and base_title != '' and not base_title.startswith('Formulaire'):
                                title = base_title
                                survey_properties['surveyls_title'] = title
                                _logger.info("Titre trouvé dans les propriétés de base (signature étendue): %s", title)
                        
                        # Ajouter les autres propriétés sans écraser le titre si déjà trouvé
                        if title:
                            base_properties.pop('surveyls_title', None)
                        survey_properties.update(base_properties)
                        _logger.info("Propriétés de base récupérées avec succès (signature étendue)")
                except xmlrpc.client.Fault:
                    try:
                        json_properties = server.get_survey_properties_json(
                            server.session_key,
                            int(sid)
                        )
                        if isinstance(json_properties, str):
                            json_properties = json.loads(json_properties)
                        if isinstance(json_properties, dict):
                            # Récupérer le titre des propriétés JSON si pas encore trouvé
                            if not title:
                                json_title = json_properties.get('surveyls_title', '').strip()
                                if json_title and json_title != '' and not json_title.startswith('Formulaire'):
                                    title = json_title
                                    survey_properties['surveyls_title'] = title
                                    _logger.info("Titre trouvé dans les propriétés JSON: %s", title)
                            
                            # Ajouter les autres propriétés sans écraser le titre si déjà trouvé
                            if title:
                                json_properties.pop('surveyls_title', None)
                            survey_properties.update(json_properties)
                            _logger.info("Propriétés JSON récupérées avec succès")
                    except Exception as e:
                        _logger.error("Toutes les tentatives ont échoué: %s", str(e))

            # Si toujours pas de titre, utiliser un titre par défaut amélioré
            if not title or not survey_properties.get('surveyls_title'):
                # Essayer de récupérer le nom du sondage directement
                try:
                    surveys_list = server.list_surveys(server.session_key)
                    if surveys_list:
                        matching_survey = next((s for s in surveys_list if str(s.get('sid')) == str(sid)), None)
                        if matching_survey:
                            survey_name = matching_survey.get('surveyls_title', '').strip()
                            if survey_name and survey_name != '':
                                title = survey_name
                                survey_properties['surveyls_title'] = title
                                _logger.info("Titre récupéré depuis la liste des sondages: %s", title)
                except Exception as e:
                    _logger.warning("Impossible de récupérer le titre depuis la liste des sondages: %s", str(e))
                    
                # Si toujours pas de titre, utiliser un titre par défaut
                if not title:
                    title = f"Sondage {sid}"
                    survey_properties['surveyls_title'] = title
                    _logger.warning("Aucun titre trouvé, utilisation du titre par défaut: %s", title)

            # Récupération des réponses
            try:
                responses = server.export_responses(
                    server.session_key,
                    int(sid),
                    'json'
                )
                if isinstance(responses, str):
                    try:
                        responses_data = json.loads(responses)
                        if isinstance(responses_data, dict):
                            survey_properties['response_count'] = len(responses_data.get('responses', []))
                    except json.JSONDecodeError:
                        _logger.warning("Impossible de décoder les réponses JSON")
                        survey_properties['response_count'] = 0
            except Exception as e:
                _logger.warning("Impossible de récupérer les réponses: %s", str(e))
                survey_properties['response_count'] = 0

            # Récupération de la structure des groupes et questions
            groups = []
            all_questions = []  # Initialisation de la variable
            try:
                groups_list = server.list_groups(
                    server.session_key,
                    int(sid)
                ) or []
                
                # Pour chaque groupe, récupérer ses questions
                for group in groups_list:
                    group_id = group.get('gid')
                    if group_id:
                        try:
                            questions = server.list_questions(
                                server.session_key,
                        int(sid),
                                int(group_id)
                            ) or []
                            
                            # Ajouter les questions au groupe
                            group['questions'] = questions
                            groups.append(group)
                            
                            # Ajouter les questions à la liste globale
                            all_questions.extend(questions)
                        except Exception as e:
                            _logger.warning(
                                "Impossible de récupérer les questions du groupe %s: %s",
                                group_id, str(e)
                            )
            except Exception as e:
                _logger.warning("Impossible de récupérer les groupes: %s", str(e))
                # Si pas de groupes, essayer de récupérer toutes les questions
                try:
                    all_questions = server.list_questions(
                        server.session_key,
                        int(sid)
                    ) or []
                except Exception as e:
                    _logger.warning("Impossible de récupérer les questions: %s", str(e))
                    all_questions = []
                    if all_questions:
                        # Créer un groupe par défaut
                        groups.append({
                            'gid': 0,
                            'group_name': 'Questions',
                            'questions': all_questions
                        })
            except Exception as e:
                _logger.warning(
                        "Impossible de récupérer les questions: %s",
                    str(e)
                )
            
            # Ajout des données structurelles
            survey_properties['groups'] = groups
            survey_properties['questions'] = all_questions
            survey_properties['languages'] = languages
            survey_properties['default_language'] = default_lang

            _logger.info("Propriétés récupérées avec succès pour le sondage %s", sid)
            return survey_properties
            
        except Exception as e:
            _logger.error(
                "Erreur lors de la récupération des propriétés du sondage %s: %s\n%s",
                sid, str(e), traceback.format_exc()
            )
            raise ValidationError(_(
                "Erreur lors de la récupération des propriétés du formulaire.\n\n"
                "Détail : %s"
            ) % str(e))

    def action_force_delete(self):
        """Force la suppression de la configuration."""
        return super(LimeSurveyServerConfig, self).unlink() 
    
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

    def sync_specific_form(self, sid):
        """Synchronise un formulaire spécifique depuis LimeSurvey."""
        try:
            _logger.info("=== Début de la synchronisation du formulaire %s ===", sid)
            _logger.info("Tentative de connexion au serveur LimeSurvey...")
            
            server = self._get_rpc_session()
            _logger.info("Connexion réussie avec la clé de session: %s", server.session_key)
            
            # Obtenir les propriétés du sondage
            _logger.info("Récupération des propriétés du sondage %s...", sid)
            survey_properties = self.get_survey_properties(sid)
            if not survey_properties:
                raise Exception("Impossible de récupérer les propriétés du sondage")
            _logger.info("Propriétés du sondage récupérées: %s", survey_properties)
            
            # S'assurer d'avoir un titre valide
            title = survey_properties.get('surveyls_title')
            if not title:
                title = f"Sondage {sid}"
            _logger.info("Titre du sondage: %s", title)
            
            # Récupérer la langue du sondage
            language = survey_properties.get('language', 'fr')
            _logger.info("Langue du sondage: %s", language)
            
            # Récupérer les groupes de questions
            _logger.info("Récupération des groupes de questions...")
            try:
                groups = server.list_groups(server.session_key, int(sid), language)
                _logger.info("Groupes de questions récupérés: %s", groups)
            except Exception as e:
                _logger.error("Erreur lors de la récupération des groupes: %s", str(e), exc_info=True)
                groups = []
            
            # Récupérer les questions pour chaque groupe
            all_questions = []
            if groups:
                _logger.info("Récupération des questions par groupe...")
                for group in groups:
                    try:
                        group_id = group.get('gid')
                        _logger.info("Récupération des questions du groupe %s...", group_id)
                        questions = server.list_questions(
                            server.session_key, 
                            int(sid),
                            group_id,
                            language
                        )
                        _logger.info("Questions du groupe %s récupérées: %s", group_id, questions)
                        if questions:
                            all_questions.extend(questions)
                    except Exception as e:
                        _logger.error("Erreur lors de la récupération des questions du groupe %s: %s", group_id, str(e), exc_info=True)
            else:
                # Si pas de groupes, essayer de récupérer toutes les questions
                _logger.info("Aucun groupe trouvé, tentative de récupération de toutes les questions...")
                try:
                    questions = server.list_questions(
                        server.session_key, 
                        int(sid),
                        None,
                        language
                    )
                    _logger.info("Questions sans groupe récupérées: %s", questions)
                    if questions:
                        all_questions.extend(questions)
                except Exception as e:
                    _logger.error("Erreur lors de la récupération des questions: %s", str(e), exc_info=True)
            
            _logger.info("Nombre total de questions trouvées: %d", len(all_questions))
            
            # Retourner les données pour le template
            return {
                'sid': sid,
                'title': title,
                'description': survey_properties.get('surveyls_description', ''),
                'is_active': survey_properties.get('active') == 'Y',
                'owner': str(survey_properties.get('owner_id', '')),
                'server_config_id': self.id,
                'sync_status': 'synced',
                'metadata': survey_properties,
                'questions': all_questions,
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation du formulaire %s: %s", sid, str(e), exc_info=True)
            raise ValidationError(_(
                "Erreur lors de la synchronisation du formulaire %s.\n\n"
                "Détail : %s"
            ) % (sid, str(e)))

    def action_sync_form(self):
        """Synchronise un formulaire spécifique depuis LimeSurvey."""
        try:
            _logger.info("=== Début de la synchronisation du formulaire ===")
            _logger.info("Tentative de connexion au serveur LimeSurvey...")
            
            server = self._get_rpc_session()
            _logger.info("Connexion réussie avec la clé de session: %s", server.session_key)
            
            # Obtenir les propriétés du sondage
            _logger.info("Récupération des propriétés du sondage %s...", self.sid)
            survey_properties = self.get_survey_properties(self.sid)
            if not survey_properties:
                raise Exception("Impossible de récupérer les propriétés du sondage")
            _logger.info("Propriétés du sondage récupérées: %s", survey_properties)
            
            # S'assurer d'avoir un titre valide
            title = survey_properties.get('surveyls_title')
            if not title:
                title = f"Sondage {self.sid}"
            _logger.info("Titre du sondage: %s", title)
            
            # Récupérer la langue du sondage
            language = survey_properties.get('language', 'fr')
            _logger.info("Langue du sondage: %s", language)
            
            # Récupérer les groupes de questions
            _logger.info("Récupération des groupes de questions...")
            try:
                groups = server.list_groups(server.session_key, int(self.sid), language)
                _logger.info("Groupes de questions récupérés: %s", groups)
            except Exception as e:
                _logger.error("Erreur lors de la récupération des groupes: %s", str(e), exc_info=True)
                groups = []
            
            # Récupérer les questions pour chaque groupe
            all_questions = []
            if groups:
                _logger.info("Récupération des questions par groupe...")
                for group in groups:
                    try:
                        group_id = group.get('gid')
                        _logger.info("Récupération des questions du groupe %s...", group_id)
                        questions = server.list_questions(
                            server.session_key, 
                            int(self.sid),
                            group_id,
                            language
                        )
                        _logger.info("Questions du groupe %s récupérées: %s", group_id, questions)
                        if questions:
                            all_questions.extend(questions)
                    except Exception as e:
                        _logger.error("Erreur lors de la récupération des questions du groupe %s: %s", group_id, str(e), exc_info=True)
            else:
                # Si pas de groupes, essayer de récupérer toutes les questions
                _logger.info("Aucun groupe trouvé, tentative de récupération de toutes les questions...")
                try:
                    questions = server.list_questions(
                        server.session_key, 
                        int(self.sid),
                        None,
                        language
                    )
                    _logger.info("Questions sans groupe récupérées: %s", questions)
                    if questions:
                        all_questions.extend(questions)
                except Exception as e:
                    _logger.error("Erreur lors de la récupération des questions: %s", str(e), exc_info=True)
            
            _logger.info("Nombre total de questions trouvées: %d", len(all_questions))
            
            # Créer/Mettre à jour le template
            vals = {
                'sid': self.sid,
                'title': title,
                'description': survey_properties.get('surveyls_description', ''),
                'is_active': survey_properties.get('active') == 'Y',
                'owner': str(survey_properties.get('owner_id', '')),
                'server_config_id': self.id,
                'sync_status': 'synced',
                'metadata': survey_properties,
            }
            _logger.info("Mise à jour du template avec les valeurs: %s", vals)
            
            # Créer d'abord le mapping principal
            mapping = self.env['admission.form.mapping'].create({
                'form_template_id': self.id,  # Référence au template
                'state': 'draft',
                'notes': f'Mapping généré automatiquement pour {title}',
            })
            _logger.info("Mapping principal créé avec l'ID: %s", mapping.id)
            
            # Créer les lignes de mapping pour chaque question
            if all_questions:
                _logger.info("Création des mappings pour %d questions...", len(all_questions))
                for question in all_questions:
                    try:
                        # Déterminer le type de question et si c'est une pièce jointe
                        question_type = question.get('type', 'text')
                        is_attachment = False
                        
                        if question_type in ['S', 'T', 'U']:
                            mapped_type = 'text'
                        elif question_type in ['N', 'K']:
                            mapped_type = 'numeric'
                        elif question_type in ['D']:
                            mapped_type = 'date'
                        elif question_type in ['L', 'O', 'R', '!']:
                            mapped_type = 'choice'
                        elif question_type in ['M', 'P']:
                            mapped_type = 'multiple'
                        elif question_type in ['|', '*']:  # '|' est le type pour upload dans LimeSurvey
                            mapped_type = 'upload'
                            is_attachment = True
                        elif question_type in ['Y']:  # Yes/No questions
                            mapped_type = 'choice'
                        elif question_type in [';']:  # Array questions (moyennes par semestre)
                            mapped_type = 'text'
                        elif question_type in ['X']:  # Boilerplate text (non-question)
                            mapped_type = 'text'
                        else:
                            mapped_type = 'text'
                        
                        # Déterminer si la question est requise (True/False ou 'Y'/'N')
                        mandatory = question.get('mandatory', False)
                        if isinstance(mandatory, str):
                            is_required = mandatory.upper() == 'Y'
                        else:
                            is_required = bool(mandatory)
                        
                        mapping_line_vals = {
                            'mapping_id': mapping.id,
                            'question_code': question.get('title', ''),
                            'question_text': self._clean_html_text(question.get('question', '')),
                            'question_type': mapped_type,
                            'is_required': is_required,
                            'is_attachment': is_attachment,
                            'group_name': question.get('group_name', ''),
                            'attributes': json.dumps(question.get('attributes', {})),
                            'status': 'draft',
                            'odoo_field': '',  # À mapper manuellement
                            'confidence_score': 0,
                        }
                        _logger.info("Création de la ligne de mapping: %s", mapping_line_vals)
                        self.env['admission.mapping.line'].create(mapping_line_vals)
                    except Exception as e:
                        _logger.error("Erreur lors de la création du mapping pour la question %s: %s", question.get('title'), str(e), exc_info=True)
                        continue
            
            return vals
            
        except Exception as e:
            _logger.error("Erreur lors de la synchronisation du formulaire: %s", str(e), exc_info=True)
            raise ValidationError(_(
                "Erreur lors de la synchronisation du formulaire.\n\n"
                "Détail : %s"
            ) % str(e))

    def get_survey_responses(self, sid):
        """
        Récupère les réponses d'un sondage avec gestion d'erreur améliorée.
        :param sid: ID du sondage
        :return: Liste des réponses ou [] en cas d'erreur
        """
        _logger.info("Récupération des réponses pour le sondage %s", sid)
        
        try:
            # Validation du SID
            if not sid or not str(sid).isdigit():
                _logger.error("L'ID du sondage doit être un nombre valide: %s", sid)
                return []

            # Obtention de la session RPC
            server = self._get_rpc_session()
            if not server:
                _logger.error("Impossible de se connecter au serveur LimeSurvey")
                return []

            # Préparation des paramètres selon la version de LimeSurvey
            try:
                # Essai avec la nouvelle signature (LimeSurvey 5+)
                responses = server.export_responses(
                    sSessionKey=server.session_key,
                    iSurveyID=sid,
                    sDocumentType='json',
                    sLanguageCode='fr',
                    sCompletionStatus='complete',
                    sHeadingType='code',
                    sResponseType='long'
                )
            except xmlrpc.client.Fault as e:
                if "Calling parameters do not match signature" in str(e):
                    # Fallback pour l'ancienne signature
                    _logger.info("Utilisation de l'ancienne signature API pour le sondage %s", sid)
                    responses = server.export_responses(
                        server.session_key,
                        sid,
                        'json',
                        'fr',
                        'complete',
                        'code',
                        'long'
                    )
                else:
                    _logger.error("Erreur RPC lors de la récupération des réponses: %s", str(e))
                    return []

            # Traitement de la réponse
            if not responses:
                _logger.warning("Aucune réponse trouvée pour le sondage %s", sid)
                return []
                
            # Décodage des réponses
            try:
                if isinstance(responses, str):
                    decoded_responses = json.loads(responses)
                elif isinstance(responses, bytes):
                    decoded_responses = json.loads(responses.decode('utf-8'))
                else:
                    decoded_responses = responses

                if not isinstance(decoded_responses, (list, dict)):
                    _logger.error("Format de réponse invalide pour le sondage %s", sid)
                    return []

                # Normalisation du format
                if isinstance(decoded_responses, dict):
                    decoded_responses = [decoded_responses]

                _logger.info("Récupération réussie de %d réponses pour le sondage %s",
                            len(decoded_responses), sid)
                return decoded_responses

            except json.JSONDecodeError as e:
                _logger.error("Erreur de décodage JSON pour le sondage %s: %s", sid, str(e))
                return []

        except Exception as e:
            _logger.error("Erreur inattendue lors de la récupération des réponses du sondage %s: %s\n%s",
                         sid, str(e), traceback.format_exc())
            return []