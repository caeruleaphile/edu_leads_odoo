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
                
                $this->log("Paramètres appliqués au sondage $surveyId");
            }
        } catch (Exception $e) {
            $this->log("Erreur lors de l'application des paramètres: " . $e->getMessage());
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
        try {
            // Log de démarrage
            file_put_contents('/tmp/webhook_debug.log', "=== DÉBUT TRAITEMENT WEBHOOK ===\n", FILE_APPEND);
            file_put_contents('/tmp/webhook_debug.log', date('Y-m-d H:i:s') . "\n", FILE_APPEND);
            
            $event = $this->getEvent();
            $surveyId = $event->get('surveyId');
            $responseId = $event->get('responseId');

            file_put_contents('/tmp/webhook_debug.log', "Survey ID: $surveyId\nResponse ID: $responseId\n", FILE_APPEND);

            // Récupération des données de la réponse
            $responseData = $this->getResponseData($surveyId, $responseId);
            file_put_contents('/tmp/webhook_debug.log', "Données de réponse récupérées\n", FILE_APPEND);
            
            // Récupération des fichiers si activé
            $files = [];
            if ($this->get('include_files', null, null, true)) {
                $files = $this->getUploadedFiles($surveyId, $responseId);
                file_put_contents('/tmp/webhook_debug.log', "Fichiers récupérés: " . count($files) . "\n", FILE_APPEND);
            }

            // Préparation du payload
            $payload = [
                'form_id' => $surveyId,
                'response_id' => $responseId,
                'response_data' => $responseData,
                'attachments' => $files
            ];

            file_put_contents('/tmp/webhook_debug.log', "Payload préparé: " . json_encode($payload, JSON_PRETTY_PRINT) . "\n", FILE_APPEND);

            // Envoi au webhook
            $this->sendWebhook($payload);

        } catch (Exception $e) {
            file_put_contents('/tmp/webhook_debug.log', "ERREUR: " . $e->getMessage() . "\n" . $e->getTraceAsString() . "\n", FILE_APPEND);
            $this->log('Erreur lors du traitement: ' . $e->getMessage());
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
        $webhook_url = $this->get('webhook_url', null, null, 'http://localhost:8069/admission/webhook/submit');
        $token = $this->get('webhook_token');
        
        file_put_contents('/tmp/webhook_debug.log', "URL Webhook: $webhook_url\n", FILE_APPEND);
        
        if (empty($token)) {
            throw new Exception("Token de sécurité non configuré");
        }
        
        // Test d'accessibilité de l'URL
        file_put_contents('/tmp/webhook_debug.log', "Test d'accessibilité de l'URL...\n", FILE_APPEND);
        $test_ch = curl_init($webhook_url);
        curl_setopt($test_ch, CURLOPT_NOBODY, true);
        curl_setopt($test_ch, CURLOPT_RETURNTRANSFER, true);
        curl_exec($test_ch);
        $test_code = curl_getinfo($test_ch, CURLINFO_HTTP_CODE);
        curl_close($test_ch);
        file_put_contents('/tmp/webhook_debug.log', "Code de test HTTP: $test_code\n", FILE_APPEND);
        
        // Préparation de la requête cURL
        $ch = curl_init($webhook_url);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        
        // Configuration des headers
        $headers = [
            'Content-Type: application/json',
            'X-Webhook-Token: ' . $token
        ];
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        file_put_contents('/tmp/webhook_debug.log', "Headers: " . implode(", ", $headers) . "\n", FILE_APPEND);
        
        // Activation du debug cURL
        $debug = fopen('/tmp/curl_debug.log', 'a+');
        curl_setopt($ch, CURLOPT_VERBOSE, true);
        curl_setopt($ch, CURLOPT_STDERR, $debug);
        
        // Envoi de la requête avec retry
        $response = null;
        $attempt = 0;
        $success = false;
        
        while (!$success && $attempt < $this->retryCount) {
            $attempt++;
            file_put_contents('/tmp/webhook_debug.log', "Tentative d'envoi #$attempt\n", FILE_APPEND);
            
            $response = curl_exec($ch);
            $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            
            file_put_contents('/tmp/webhook_debug.log', "Code HTTP: $http_code\n", FILE_APPEND);
            file_put_contents('/tmp/webhook_debug.log', "Réponse: $response\n", FILE_APPEND);
            
            if ($response === false) {
                $error = curl_error($ch);
                file_put_contents('/tmp/webhook_debug.log', "Erreur cURL: $error\n", FILE_APPEND);
                
                if ($attempt < $this->retryCount) {
                    sleep(pow(2, $attempt)); // Exponential backoff
                    continue;
                }
                
                throw new Exception("Erreur lors de l'envoi au webhook: " . $error);
            }
            
            $success = true;
        }
        
        curl_close($ch);
        fclose($debug);
        
        if (!$success) {
            throw new Exception("Échec de l'envoi au webhook après {$this->retryCount} tentatives");
        }
        
        return $response;
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