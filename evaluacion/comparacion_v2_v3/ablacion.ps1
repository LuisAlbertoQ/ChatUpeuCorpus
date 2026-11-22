# ablacion.ps1 — Corre el banco de 17 Q (y opcionalmente las 6 negativas) con un conjunto
# de variables de entorno del backend, para comparar mejoras con todo lo demás fijo.
#
# Uso (desde la raíz de oe5_chatbot_upeu):
#   .\evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta M0_s42 -Vars @{RAG_RECORTE_LEGACY_700="1"; OLLAMA_SEED="42"}
#   .\evaluacion\comparacion_v2_v3\ablacion.ps1 -Etiqueta M1_s42 -Vars @{OLLAMA_SEED="42"} -Negativas
# Al terminar restaura el backend con los valores por defecto del docker-compose.yml.
param(
    [Parameter(Mandatory)] [string]$Etiqueta,
    [hashtable]$Vars = @{},
    [switch]$Negativas,
    [switch]$NoRestaurar
)

function Esperar-Backend {
    $t = 0
    while ($t -lt 600) {
        $s = docker inspect -f "{{.State.Health.Status}}" oe5-backend
        if ($s -eq "healthy") { return }
        Start-Sleep 5; $t += 5
    }
    throw "oe5-backend no quedó healthy en 600 s"
}

foreach ($k in $Vars.Keys) { Set-Item -Path "Env:$k" -Value $Vars[$k] }
docker compose up -d backend 2>&1 | Out-Null
Esperar-Backend
# Verificación: cada variable pedida debe llegar al contenedor (una variable fija en el
# docker-compose.yml, sin ${VAR:-...}, NO se puede sobrescribir y la corrida sería inválida).
foreach ($k in $Vars.Keys) {
    $real = (docker exec oe5-backend printenv $k)
    if ($real -ne $Vars[$k]) {
        foreach ($j in $Vars.Keys) { Remove-Item -Path "Env:$j" -ErrorAction SilentlyContinue }
        throw "La variable $k vale '$real' en el contenedor, se pidió '$($Vars[$k])'. ¿Está fija en docker-compose.yml?"
    }
}
Write-Host "== $Etiqueta  vars: $(($Vars.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', ')"
docker exec oe5-backend python /data/evaluacion/comparacion_v2_v3/correr_17q_e2e.py --etiqueta $Etiqueta 2>&1 |
    Select-String -NotMatch -Pattern "warn|deprecat|telemetry|Loading|^\s*$"
if ($Negativas) {
    docker exec oe5-backend python /data/evaluacion/comparacion_v2_v3/correr_17q_e2e.py --etiqueta "${Etiqueta}_NEG" --banco v31_no_answer 2>&1 |
        Select-String -Pattern "RESUMEN|tipo_mensaje"
}
foreach ($k in $Vars.Keys) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
if (-not $NoRestaurar) {
    docker compose up -d backend 2>&1 | Out-Null
    Esperar-Backend
}
