$php = "C:\xampp\php\php.exe"
$root = "C:\Users\kjmg2\Documents\LaCasaDelJean"

if (!(Test-Path $php)) {
  Write-Error "No se encontro php.exe en C:\xampp\php\php.exe"
  exit 1
}

Write-Host "Iniciando backend PHP en http://localhost:8000 ..."
& $php -S localhost:8000 -t $root
