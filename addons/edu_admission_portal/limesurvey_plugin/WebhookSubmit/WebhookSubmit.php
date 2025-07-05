<?php
/**
 * WebhookSubmit - Plugin LimeSurvey pour l'envoi des réponses à Odoo
 *
 * @author Odoo Admission Portal
 * @copyright 2024
 * @license GPL v3
 * @version 1.0.0
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

use LimeSurvey\PluginManager\PluginBase;

class WebhookSubmit extends PluginBase
{
    protected $storage = 'DbStorage';
    
    protected static $description = 'Envoie les réponses du sondage à Odoo via webhook';
    protected static $name = 'WebhookSubmit';

    /** @var array Stockage des erreurs pour le logging */
    private $errors = [];

    /** @var int Nombre de tentatives d'envoi restantes */
    private $retryCount;

    /**
     * Configuration par défaut du plugin
     */
    protected $settings = [
        'webhook_url' => [
            'type' => 'string',
            'label' => 'URL du Webhook',
            'default' => 'http://localhost:8069/admission/webhook/submit',
            'help' => 'URL complète du endpoint webhook Odoo'
        ],
        'webhook_token' => [
            'type' => 'string',
            'label' => 'Token de Sécurité',
            'default' => '',
            'help' => 'Token de sécurité généré dans Odoo'
        ],
        'include_files' => [
            'type' => 'boolean',
            'label' => 'Inclure les Fichiers',
            'default' => true,
            'help' => 'Envoyer les fichiers joints avec la réponse'
        ],
        'log_errors' => [
            'type' => 'boolean',
            'label' => 'Logger les Erreurs',
            'default' => true,
            'help' => 'Enregistrer les erreurs dans les logs'
        ],
        'retry_count' => [
            'type' => 'int',
            'label' => 'Nombre de Tentatives',
            'default' => 3,
            'help' => 'Nombre de tentatives en cas d\'échec'
        ],
    ];

    /**
     * Constructor
     */
    public function __construct($manager, $id)
    {
        parent::__construct($manager, $id);
        
        // Initialize plugin
        $this->subscribe('afterSurveyComplete');
        $this->subscribe('beforeRequest');
        $this->subscribe('beforeSurveySettings');
        $this->subscribe('newSurveySettings');
        $this->retryCount = $this->get('retry_count', null, null, 3);
    }

    /**
     * Handle CSRF exemption for plugin requests
     */
    public function beforeRequest()
    {
        // Désactivation du CSRF pour les requêtes du plugin
        if (isset($_REQUEST['plugin']) && $_REQUEST['plugin'] === 'WebhookSubmit') {
            Yii::app()->request->enableCsrfValidation = false;
        }
    }

    /**
     * Applique les paramètres par défaut au sondage
     */
    public function beforeSurveySettings()
    {
        $event = $this->getEvent();
        $surveyId = $event->get('survey');
        
        try {
            // Paramètres à appliquer
            $settings = [
                'usecookie' => 'N',
                'allowregister' => 'N',
                'allowsave' => 'Y',
                'anonymized' => 'N',
                'tokenanswerspersistence' => 'N',
                'usecaptcha' => 'N',
                'listpublic' => 'Y',
                'publicstatistics' => 'N',
                'printanswers' => 'N',
                'publicgraphs' => 'N',
                'assessments' => 'N',
                'usetokens' => 'N',
                'showwelcome' => 'N',
                'showprogress' => 'Y',
                'questionindex' => '0',
                'navigationdelay' => '0',
                'nokeyboard' => 'N',
                'allowprev' => 'Y',
                'format' => 'G',
                'template' => 'default',
                'surveymode' => 'open'
            ];
            
            // Mise à jour des paramètres dans la base de données
            $survey = \Survey::model()->findByPk($surveyId);
            if ($survey) {
                foreach ($settings as $key => $value) {
                    $survey->$key = $value;
                }
                $survey->save();
                
                // Suppression de la table des tokens si elle existe
                $tableName = "{{tokens_$surveyId}}";
                try {
                    \Yii::app()->db->createCommand()->dropTable($tableName);
                } catch (Exception $e) {
                    // La table n'existe peut-être pas, on ignore l'erreur
                }
                
                // Mise à jour des permissions
                $command = \Yii::app()->db->createCommand();
                $command->update('{{surveys_rights}}', 
                    ['use_tokens' => 0],
                    'sid = :sid',
                    [':sid' => $surveyId]
                );

                // Désactiver complètement les tokens dans la base de données
                $this->disableTokensInDatabase($surveyId);
                
                $this->log("Paramètres appliqués au sondage $surveyId");
            }
        } catch (Exception $e) {
            $this->log("Erreur lors de l'application des paramètres: " . $e->getMessage());
        }
    }

    /**
     * Désactive complètement les tokens dans la base de données
     */
    protected function disableTokensInDatabase($surveyId)
    {
        try {
            $db = \Yii::app()->db;
            $transaction = $db->beginTransaction();

            try {
                // 1. Vérifier si la table des tokens existe
                $tokenTableName = "{{tokens_$surveyId}}";
                $tableExists = $db->createCommand("
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_name = " . $db->quoteValue("lime_tokens_$surveyId")
                )->queryScalar();

                if ($tableExists) {
                    // Supprimer la table des tokens si elle existe
                    $db->createCommand()->dropTable($tokenTableName);
                    $this->log("Table des tokens supprimée pour le sondage $surveyId");
                }

                // 2. Mise à jour de la table surveys avec tous les paramètres nécessaires
                $command = $db->createCommand();
                $command->update('{{surveys}}', 
                    [
                        'usetokens' => 'N',
                        'tokenanswerspersistence' => 'N',
                        'allowregister' => 'N',
                        'listpublic' => 'Y',
                        'publicsurvey' => 'Y',
                        'usecookie' => 'N',
                        'alloweditaftercompletion' => 'N',
                        'anonymized' => 'N',
                        'surveymode' => 'open',
                        'template' => 'fruity',
                        'format' => 'G',
                        'showwelcome' => 'N',
                        'showprogress' => 'Y',
                        'questionindex' => 0,
                        'navigationdelay' => 0,
                        'nokeyboard' => 'N',
                        'allowprev' => 'Y',
                        'printanswers' => 'N',
                        'publicstatistics' => 'N',
                        'publicgraphs' => 'N',
                        'assessments' => 'N',
                        'usecaptcha' => 'N',
                        'allowsave' => 'N',
                        'showgroupinfo' => 'N',
                        'showqnumcode' => 'N'
                    ],
                    'sid = :sid',
                    [':sid' => $surveyId]
                );

                // 3. Mise à jour des paramètres de langue pour supprimer tous les messages liés aux tokens et à l'inscription
                $command->update('{{surveys_languagesettings}}',
                    [
                        'surveyls_message_accesscode' => '',
                        'surveyls_message_notoken' => '',
                        'surveyls_message_registererror' => '',
                        'surveyls_message_register' => '',
                        'surveyls_message_registermsg' => '',
                        'surveyls_message_registersuccessmsg' => '',
                        'surveyls_message_registersuccessmsg2' => '',
                        'surveyls_email_register_subj' => '',
                        'surveyls_email_register' => '',
                        'surveyls_email_confirm_subj' => '',
                        'surveyls_email_confirm' => '',
                        'surveyls_email_invite_subj' => '',
                        'surveyls_email_invite' => '',
                        'surveyls_email_remind_subj' => '',
                        'surveyls_email_remind' => '',
                        'surveyls_welcometext' => '',
                        'surveyls_endtext' => ''
                    ],
                    'surveyls_survey_id = :sid',
                    [':sid' => $surveyId]
                );

                // 4. Suppression des entrées dans survey_url_parameters
                $command->delete('{{survey_url_parameters}}',
                    'sid = :sid AND (parameter LIKE :pattern1 OR parameter LIKE :pattern2)',
                    [
                        ':sid' => $surveyId,
                        ':pattern1' => '%token%',
                        ':pattern2' => '%register%'
                    ]
                );

                // 5. Mise à jour des permissions
                $command->update('{{surveys_rights}}',
                    [
                        'use_tokens' => 0,
                        'create_token' => 0,
                        'delete_token' => 0,
                        'export' => 0,
                        'import' => 0
                    ],
                    'sid = :sid',
                    [':sid' => $surveyId]
                );

                // 6. Suppression des conditions basées sur les tokens
                $command->delete('{{conditions}}',
                    'cfield LIKE :pattern AND qid IN (SELECT qid FROM {{questions}} WHERE sid = :sid)',
                    [
                        ':pattern' => '%TOKEN:%',
                        ':sid' => $surveyId
                    ]
                );

                // 7. Mise à jour des paramètres de template
                $command->update('{{template_configuration}}',
                    [
                        'options' => json_encode([
                            'ajaxmode' => 'off',
                            'brandlogo' => 'off',
                            'container' => 'on',
                            'hideprivacyinfo' => 'on',
                            'showpopups' => 'off',
                            'showclearall' => 'off',
                            'questionhelptextposition' => 'none'
                        ])
                    ],
                    'template_name = :template AND sid = :sid',
                    [
                        ':template' => 'fruity',
                        ':sid' => $surveyId
                    ]
                );

                $transaction->commit();
                $this->log("Configuration complètement mise à jour pour le sondage $surveyId");
            } catch (Exception $e) {
                $transaction->rollback();
                $this->log("Erreur lors de la mise à jour de la configuration: " . $e->getMessage());
                throw $e;
            }
        } catch (Exception $e) {
            $this->log("Erreur critique lors de la mise à jour de la configuration: " . $e->getMessage());
            throw $e;
        }
    }

    /**
     * Supprime les messages liés aux tokens dans les templates
     */
    protected function removeTokenMessages($surveyId)
    {
        try {
            $db = \Yii::app()->db;
            
            // 1. Mise à jour des messages dans les traductions de sondage
            $command = $db->createCommand();
            
            // Liste des messages à supprimer ou remplacer
            $messagesToRemove = [
                'tokenentry' => '',  // Page de saisie du token
                'tokenemailnotifications' => '',  // Notifications par email des tokens
                'tokenemailregisterconfirm' => '',  // Confirmation d'inscription
                'tokenemailregister' => '',  // Email d'inscription
                'token' => '',  // Champ token
                'captcharegexp' => ''  // Expression régulière du captcha
            ];
            
            // Mise à jour pour chaque langue du sondage
            $languages = \Survey::model()->findByPk($surveyId)->additionalLanguages;
            $languages[] = \Survey::model()->findByPk($surveyId)->language;
            
            foreach ($languages as $language) {
                foreach ($messagesToRemove as $messageKey => $newValue) {
                    $command->update('{{surveys_languagesettings}}',
                        [$messageKey => $newValue],
                        'surveyls_survey_id = :sid AND surveyls_language = :language',
                        [
                            ':sid' => $surveyId,
                            ':language' => $language
                        ]
                    );
                }
            }

            // 2. Suppression des messages d'erreur liés aux tokens
            $command->update('{{surveys_languagesettings}}',
                [
                    'surveyls_email_register_subj' => '',
                    'surveyls_email_register' => '',
                    'surveyls_email_confirm_subj' => '',
                    'surveyls_email_confirm' => '',
                    'email_register_subj' => '',
                    'email_register' => '',
                    'email_confirm_subj' => '',
                    'email_confirm' => ''
                ],
                'surveyls_survey_id = :sid',
                [':sid' => $surveyId]
            );

            // 3. Mise à jour des paramètres globaux du sondage
            $command->update('{{surveys}}',
                [
                    'tokenencryptionoptions' => '{"enabled":"N"}',  // Désactive le cryptage des tokens
                    'showwelcome' => 'N',  // Désactive la page de bienvenue qui peut contenir des messages de token
                    'showsurveypolicynotice' => '0',  // Désactive la notice de politique qui peut mentionner les tokens
                    'showdatapolicybutton' => '0',  // Désactive le bouton de politique de données
                    'showprivacyinfo' => '0'  // Désactive les infos de confidentialité
                ],
                'sid = :sid',
                [':sid' => $surveyId]
            );

            $this->log("Messages liés aux tokens supprimés pour le sondage $surveyId");
            return true;
        } catch (Exception $e) {
            $this->log("Erreur lors de la suppression des messages liés aux tokens: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Applique les paramètres lors de la création d'un nouveau sondage
     */
    public function newSurveySettings()
    {
        $event = $this->getEvent();
        $surveyId = $event->get('surveyid');
        
        try {
            // Paramètres à appliquer
            $settings = [
                'usecookie' => 'N',
                'allowregister' => 'N',
                'allowsave' => 'Y',
                'anonymized' => 'N',
                'tokenanswerspersistence' => 'N',
                'usecaptcha' => 'N',
                'listpublic' => 'Y',
                'publicstatistics' => 'N',
                'printanswers' => 'N',
                'publicgraphs' => 'N',
                'assessments' => 'N',
                'usetokens' => 'N',
                'showwelcome' => 'N',
                'showprogress' => 'Y',
                'questionindex' => '0',
                'navigationdelay' => '0',
                'nokeyboard' => 'N',
                'allowprev' => 'Y',
                'format' => 'G',
                'template' => 'default',
                'surveymode' => 'open'
            ];
            
            // Mise à jour des paramètres dans la base de données
            $survey = \Survey::model()->findByPk($surveyId);
            if ($survey) {
                foreach ($settings as $key => $value) {
                    $survey->$key = $value;
                }
                $survey->save();
                
                // Suppression de la table des tokens si elle existe
                $tableName = "{{tokens_$surveyId}}";
                try {
                    \Yii::app()->db->createCommand()->dropTable($tableName);
                } catch (Exception $e) {
                    // La table n'existe peut-être pas, on ignore l'erreur
                }
                
                // Mise à jour des permissions
                $command = \Yii::app()->db->createCommand();
                $command->update('{{surveys_rights}}', 
                    ['use_tokens' => 0],
                    'sid = :sid',
                    [':sid' => $surveyId]
                );
                
                $this->log("Paramètres appliqués au nouveau sondage $surveyId");
            }
        } catch (Exception $e) {
            $this->log("Erreur lors de l'application des paramètres: " . $e->getMessage());
        }
    }

    /**
     * Gestionnaire de l'événement afterSurveyComplete
     */
    public function afterSurveyComplete()
    {
        $event = $this->getEvent();
        $surveyId = $event->get('surveyId');
        $responseId = $event->get('responseId');
        
        try {
            // Vérification de la configuration
            $webhookUrl = $this->get('webhook_url', 'Survey', $surveyId, $this->settings['webhook_url']['default']);
            $webhookToken = $this->get('webhook_token', 'Survey', $surveyId, '');
            
            if (empty($webhookUrl) || empty($webhookToken)) {
                throw new Exception('Configuration du webhook incomplète. URL et token requis.');
            }

            // Préparation des données
            $responseData = $this->getResponseData($surveyId, $responseId);
            if (empty($responseData)) {
                throw new Exception('Aucune donnée de réponse trouvée.');
            }

            // Préparation du payload
            $payload = [
                'form_id' => $surveyId,
                'response_id' => $responseId,
                'response_data' => $responseData,
            ];

            // Ajout des fichiers si activé
            if ($this->get('include_files', 'Survey', $surveyId, true)) {
                $files = $this->getUploadedFiles($surveyId, $responseId);
                if (!empty($files)) {
                    $payload['attachments'] = $files;
                }
            }

            // Envoi au webhook avec retry
            $this->retryCount = $this->get('retry_count', 'Survey', $surveyId, 3);
            $success = false;
            $lastError = null;

            while ($this->retryCount > 0 && !$success) {
                try {
                    $response = $this->sendWebhook($payload);
                    if ($response && $response['status'] === 'success') {
                        $success = true;
                        $this->log("Réponse envoyée avec succès (Survey: $surveyId, Response: $responseId)");
                        break;
                    }
                } catch (Exception $e) {
                    $lastError = $e;
                    $this->retryCount--;
                    if ($this->retryCount > 0) {
                        sleep(2); // Attente entre les tentatives
                    }
                }
            }

            if (!$success) {
                throw new Exception(
                    "Échec de l'envoi après plusieurs tentatives. " .
                    ($lastError ? "Dernière erreur: " . $lastError->getMessage() : "")
                );
            }

        } catch (Exception $e) {
            $this->log("Erreur lors du traitement de la réponse: " . $e->getMessage(), \CLogger::LEVEL_ERROR);
            if ($this->get('log_errors', 'Survey', $surveyId, true)) {
                $this->errors[] = $e->getMessage();
            }
        }
    }

    /**
     * Récupère les données de la réponse
     */
    protected function getResponseData($surveyId, $responseId)
    {
        $survey = \Survey::model()->findByPk($surveyId);
        $response = \Response::model($surveyId)->findByPk($responseId);
        
        if (!$survey || !$response) {
            throw new Exception("Sondage ou réponse non trouvé");
        }

        $data = [];
        foreach ($response->attributes as $key => $value) {
            if (strpos($key, $surveyId . 'X') === 0) {
                $questionCode = $this->getQuestionCode($key, $surveyId);
                $data[$questionCode] = $value;
            }
        }

        return $data;
    }

    /**
     * Récupère les fichiers uploadés
     */
    protected function getUploadedFiles($surveyId, $responseId)
    {
        $files = [];
        $uploadQuestions = \Question::model()->findAllByAttributes([
            'sid' => $surveyId,
            'type' => 'file_upload'
        ]);

        foreach ($uploadQuestions as $question) {
            $response = \Response::model($surveyId)->findByPk($responseId);
            $fileInfo = json_decode($response->getAttribute($question->sid . 'X' . $question->gid . 'X' . $question->qid));
            
            if ($fileInfo) {
                $filePath = \Yii::app()->getConfig('uploaddir') . "/surveys/" . $surveyId . "/files/" . $fileInfo->filename;
                if (file_exists($filePath)) {
                    $files[] = [
                        'name' => $fileInfo->filename,
                        'content' => base64_encode(file_get_contents($filePath)),
                        'question_code' => $question->title
                    ];
                }
            }
        }

        return $files;
    }

    /**
     * Envoie les données au webhook
     */
    protected function sendWebhook($payload)
    {
        $event = $this->getEvent();
        $surveyId = $event->get('surveyId');
        
        // Récupération des paramètres
        $webhookUrl = $this->get('webhook_url', 'Survey', $surveyId, $this->settings['webhook_url']['default']);
        $webhookToken = $this->get('webhook_token', 'Survey', $surveyId, '');

        // Préparation de la requête
        $ch = curl_init($webhookUrl);
        
        // Configuration de cURL
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'X-Webhook-Token: ' . $webhookToken
            ],
            CURLOPT_POSTFIELDS => json_encode($payload),
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_SSL_VERIFYHOST => false,
            CURLOPT_TIMEOUT => 30,
        ]);

        // Debug log
        $this->debugLog("Envoi au webhook: " . json_encode([
            'url' => $webhookUrl,
            'payload' => $payload,
            'headers' => [
                'X-Webhook-Token' => $webhookToken
            ]
        ]));

        // Exécution de la requête
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        
        curl_close($ch);

        // Log de la réponse
        $this->debugLog("Réponse du webhook: " . $response);
        $this->debugLog("Code HTTP: " . $httpCode);
        
        if ($error) {
            $this->log("Erreur cURL: " . $error, \CLogger::LEVEL_ERROR);
            throw new Exception("Erreur lors de l'envoi au webhook: " . $error);
        }

        if ($httpCode >= 400) {
            $this->log("Erreur HTTP $httpCode: " . $response, \CLogger::LEVEL_ERROR);
            throw new Exception("Le serveur a retourné une erreur: " . $response);
        }

        $responseData = json_decode($response, true);
        if (!$responseData) {
            throw new Exception("Réponse invalide du serveur");
        }

        return $responseData;
    }

    /**
     * Convertit une clé de réponse en code de question
     */
    protected function getQuestionCode($key, $surveyId)
    {
        $parts = explode('X', $key);
        if (count($parts) >= 3) {
            $gid = $parts[1];
            $qid = $parts[2];
            
            $question = \Question::model()->findByAttributes([
                'sid' => $surveyId,
                'gid' => $gid,
                'qid' => $qid
            ]);
            
            if ($question && $question->title) {
                return $question->title;
            }
        }
        
        return $key;
    }

    /**
     * Enregistre un message dans les logs
     */
    public function log($message, $level = \CLogger::LEVEL_TRACE)
    {
        if ($this->get('log_errors', null, null, true)) {
            \Yii::log($message, $level, 'WebhookSubmit');
        }
    }

    /**
     * Enregistre un message de debug
     */
    protected function debugLog($message)
    {
        if ($this->get('log_errors', null, null, true)) {
            file_put_contents('/tmp/webhook_debug.log', date('Y-m-d H:i:s') . " - " . $message . "\n", FILE_APPEND);
        }
    }
} 