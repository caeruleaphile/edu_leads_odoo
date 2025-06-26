<?php

class CsrfHelper
{
    /**
     * Check if the current request should be exempt from CSRF validation
     * @return bool
     */
    public static function shouldExemptRequest()
    {
        // Get the current request URL
        $requestUri = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '';
        
        // List of paths that should be exempt from CSRF
        $exemptPaths = [
            '/index.php/admin/pluginhelper',  // Plugin helper path
            '/index.php/admin/pluginfunction' // Plugin function path
        ];
        
        // Check if the current path should be exempt
        foreach ($exemptPaths as $path) {
            if (strpos($requestUri, $path) !== false) {
                return true;
            }
        }
        
        return false;
    }
} 