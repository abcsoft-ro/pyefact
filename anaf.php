<?php
//https://lorand.work/autentificare-oauth-si-obtinere-token-jwt-de-la-anaf-folosind-php/
// It's better to use an autoloader (like Composer's) than manual includes.
// include "../admin/connect_db.php"; // This seems unused in the class.

declare(strict_types=1); // Enforce strict types for better code quality.

class Anaf
{
    // Class properties with type hints and visibility.
    private string $clientId;
    private string $clientSecret;
    private string $redirectUri;
    private string $code;

    private string $debugInfo = '';

    private const AUTHORIZE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize";
    private const TOKEN_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/token";
    private const REVOKE_URL = "https://logincert.anaf.ro/anaf-oauth2/v1/revoke";

    /**
     * Constructor with dependency injection for configuration.
     *
     * @param string $clientId
     * @param string $clientSecret
     * @param string $redirectUri
     */
    public function __construct(string $clientId, string $clientSecret, string $redirectUri)
    {
        // SUGGESTION: Load these from environment variables or a secure config file, not hardcoded.
        // Example:
        // $this->clientId = $_ENV['ANAF_CLIENT_ID'];
        // $this->clientSecret = $_ENV['ANAF_CLIENT_SECRET'];
        // $this->redirectUri = $_ENV['ANAF_REDIRECT_URI'];
        $this->clientId = $clientId;
        $this->clientSecret = $clientSecret;
        $this->redirectUri = $redirectUri;
    }

    /**
     * Generates the authorization link for the user to click.
     *
     * @return string
     */
    public function getAuthorizationLink(): string
    {
        $queryParams = http_build_query([
            'response_type' => 'code',
            'token_content_type' => 'jwt',
            'client_id' => $this->clientId,
            'redirect_uri' => $this->redirectUri,
        ]);
        return self::AUTHORIZE_URL . '?' . $queryParams;
    }

    public function setCode(string $code): void
    {
        $this->code = $code;
    }

    /**
     * Exchanges the authorization code for an access token.
     *
     * @return array The token information from ANAF.
     * @throws \RuntimeException on cURL or API errors.
     */
    public function getToken(): array
    {
        if (empty($this->code)) {
            throw new \InvalidArgumentException("Authorization code has not been set.");
        }

        $ch = curl_init();

        $postData = http_build_query([
            'code' => $this->code,
            'grant_type' => 'authorization_code',
            'redirect_uri' => $this->redirectUri,
            'token_content_type' => 'jwt'
        ]);

        $headers = [
            'Cache-control: no-cache',
            'Content-type: application/x-www-form-urlencoded',
            'Authorization: Basic ' . base64_encode($this->clientId . ":" . $this->clientSecret)
        ];

        curl_setopt($ch, CURLOPT_URL, self::TOKEN_URL);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        // SECURITY: Do not disable SSL verification in production.
        // Set this to true and configure CURLOPT_CAINFO if needed.
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        // Verbose logging for debugging
        curl_setopt($ch, CURLOPT_VERBOSE, true);
        $verbose = fopen('php://temp', 'w+');
        curl_setopt($ch, CURLOPT_STDERR, $verbose);

        $response = curl_exec($ch);

        rewind($verbose);
        $this->debugInfo = stream_get_contents($verbose) ?: 'Could not read verbose log.';
        fclose($verbose);

        if ($response === false) {
            $error = curl_error($ch);
            $errno = curl_errno($ch);
            curl_close($ch);
            throw new \RuntimeException(sprintf('cURL Error (#%d): %s', $errno, $error));
        }

        curl_close($ch);

        $tokenInfo = json_decode($response, true);

        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \RuntimeException('Failed to decode JSON response from ANAF.');
        }

        if (isset($tokenInfo['error'])) {
            $errorDescription = $tokenInfo['error_description'] ?? 'Unknown API error';
            throw new \RuntimeException(sprintf('ANAF API Error: %s (%s)', $errorDescription, $tokenInfo['error']));
        }

        return $tokenInfo;
    }

    public function getDebugInfo(): string
    {
        return $this->debugInfo;
    }
}