# WebhookSubmit - Plugin LimeSurvey pour Odoo

## Description

Ce plugin permet d'envoyer automatiquement les réponses des sondages LimeSurvey vers Odoo via un webhook. Il est spécialement conçu pour le module d'admission Odoo et prend en charge :

- L'envoi automatique des réponses après complétion du sondage
- La gestion des fichiers uploadés (conversion en base64)
- La sécurisation via token
- La gestion des erreurs et tentatives multiples
- La configuration via l'interface d'administration

## Installation

1. Créez un dossier `WebhookSubmit` dans le répertoire `plugins` de votre installation LimeSurvey
2. Copiez tous les fichiers du plugin dans ce dossier
3. Connectez-vous à l'interface d'administration LimeSurvey
4. Allez dans Configuration > Plugins
5. Trouvez "WebhookSubmit" et cliquez sur "Activer"

## Structure des Fichiers

```
WebhookSubmit/
├── config.xml           # Configuration du plugin
├── WebhookSubmit.php   # Code principal du plugin
├── README.md           # Documentation
└── locale/             # Traductions (optionnel)
```

## Configuration

Dans l'interface d'administration LimeSurvey, configurez les paramètres suivants :

- **URL du Webhook** : URL complète de l'endpoint Odoo (ex: https://example.com/admission/webhook/submit)
- **Token de Sécurité** : Token d'authentification partagé avec Odoo
- **Inclure les Fichiers** : Activer/désactiver l'envoi des fichiers uploadés
- **Logger les Erreurs** : Activer/désactiver le logging des erreurs
- **Nombre de Tentatives** : Nombre de tentatives en cas d'échec d'envoi

## Format du Payload

Le webhook envoie un payload JSON avec la structure suivante :

```json
{
    "form_id": "123",
    "response_id": "456",
    "response_data": {
        "question1": "réponse1",
        "question2": "réponse2"
    },
    "attachments": [
        {
            "name": "document.pdf",
            "content": "base64_encoded_content",
            "question_code": "Q1"
        }
    ],
    "token": "votre_token_secret"
}
```

## Sécurité

- Le plugin utilise HTTPS pour les communications
- L'authentification se fait via un token dans les headers
- Les fichiers sont encodés en base64
- Les erreurs sont logguées de manière sécurisée

## Compatibilité

- LimeSurvey 6.0+
- PHP 7.4+
- Testé avec LimeSurvey 6.13.0

## Support

Pour toute question ou problème :
1. Vérifiez les logs LimeSurvey
2. Assurez-vous que l'URL et le token sont corrects
3. Vérifiez la connectivité réseau
4. Contactez le support Odoo si nécessaire

## Licence

Ce plugin est distribué sous licence GPL v3. 