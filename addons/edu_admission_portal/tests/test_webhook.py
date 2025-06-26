import requests
import json
import base64
import os

def test_webhook_submission(base_url, webhook_token, form_id):
    """
    Test de soumission d'une candidature via le webhook.
    
    Args:
        base_url: URL de base d'Odoo (ex: http://localhost:8069)
        webhook_token: Token de sécurité du webhook
        form_id: ID du formulaire LimeSurvey
    """
    
    # Données de test
    test_data = {
        "form_id": form_id,
        "response_id": "TEST_123",
        "response_data": {
            "nom": "Test Candidat",
            "email": "test@example.com",
            "telephone": "+1234567890",
            "niveau": "Master",
            "motivation": "Test de soumission automatique"
        }
    }
    
    # En-têtes de la requête
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Token': webhook_token,
        'Accept': 'application/json'
    }
    
    # URL du webhook
    webhook_url = f"{base_url}/admission/webhook/submit"
    
    try:
        # Envoi de la requête
        response = requests.post(
            webhook_url,
            json=test_data,
            headers=headers,
            verify=False  # Pour le développement local uniquement
        )
        
        # Affichage des résultats
        print("\n=== Résultats du Test ===")
        print(f"Status Code: {response.status_code}")
        print("\nRéponse:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
    except Exception as e:
        print("\n=== Erreur ===")
        print(str(e))

if __name__ == "__main__":
    # Configuration du test
    BASE_URL = "http://localhost:8069"  # Modifier selon votre configuration
    WEBHOOK_TOKEN = "votre_token_ici"   # Remplacer par votre token
    FORM_ID = "123"                     # Remplacer par l'ID de votre formulaire
    
    # Exécution du test
    test_webhook_submission(BASE_URL, WEBHOOK_TOKEN, FORM_ID) 