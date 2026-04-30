<?php
require_once 'db.php';
setCorsHeaders(['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']);
http_response_code(200);
exit;
