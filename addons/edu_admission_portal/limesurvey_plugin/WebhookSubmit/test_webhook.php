<?php
// Configuration
$webhook_url = 'http://192.168.11.150:8069/admission/webhook/submit';  // Ajustez selon votre configuration
$token = ''; // Mettez votre token ici

// Données de test
$payload = [
    'form_id' => 'TEST123',
    'response_id' => 'TEST456',
    'response_data' => [
        'nom' => 'Test Webhook',
        'email' => 'test@example.com'
    ],
    'attachments' => []
];

// Logs
echo "=== DÉBUT TEST WEBHOOK ===\n";
echo date('Y-m-d H:i:s') . "\n";
echo "URL: $webhook_url\n";

// Test d'accessibilité
$test_ch = curl_init($webhook_url);
curl_setopt($test_ch, CURLOPT_NOBODY, true);
curl_setopt($test_ch, CURLOPT_RETURNTRANSFER, true);
curl_exec($test_ch);
$test_code = curl_getinfo($test_ch, CURLINFO_HTTP_CODE);
curl_close($test_ch);
echo "Test d'accessibilité: Code HTTP $test_code\n";

// Envoi du webhook
$ch = curl_init($webhook_url);
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'X-Webhook-Token: ' . $token
]);

// Debug cURL
$debug = fopen('php://output', 'w+');
curl_setopt($ch, CURLOPT_VERBOSE, true);
curl_setopt($ch, CURLOPT_STDERR, $debug);

// Envoi
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

echo "\nCode HTTP: $http_code\n";
echo "Réponse: $response\n";

if ($response === false) {
    echo "Erreur cURL: " . curl_error($ch) . "\n";
}

curl_close($ch);
echo "=== FIN TEST WEBHOOK ===\n"; 