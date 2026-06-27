param(
    [string]$Modelo = "llama3",
    [string]$OutputFile = ""
)

if (-not $OutputFile) {
    $OutputFile = "evaluacion\resultados_$($Modelo -replace '[:.]', '_').json"
}

$Preguntas = Get-Content "evaluacion\preguntas_comparacion.json" | ConvertFrom-Json

Write-Host "Evaluando modelo: $Modelo"
Write-Host "Preguntas: $($Preguntas.Count)"
Write-Host ""

$Resultados = @()

foreach ($q in $Preguntas) {
    $sesion_id = "comp-$($Modelo -replace '[:.]', '_')-$($q.id)"
    
    Write-Host "  [$($q.id)] $($q.pregunta)" -NoNewline
    
    $body = @{
        pregunta  = $q.pregunta
        sesion_id = $sesion_id
    } | ConvertTo-Json
    
    $start = Get-Date
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/consulta" `
            -Method Post -Body $body -ContentType "application/json" `
            -ErrorAction Stop
        $elapsed = (Get-Date) - $start
        
        $Resultado = @{
            id_pregunta       = $q.id
            pregunta          = $q.pregunta
            categoria_objetivo = $q.categoria_objetivo
            tema              = $q.tema
            tipo_mensaje      = $resp.tipo_mensaje
            tiempo_seg        = [math]::Round($resp.tiempo_respuesta, 2)
            distancia_min     = if ($resp.debug_distancias) { [math]::Round(($resp.debug_distancias | Measure-Object -Minimum).Minimum, 4) } else { $null }
            distancia_prom    = if ($resp.debug_distancias) { [math]::Round(($resp.debug_distancias | Measure-Object -Average).Average, 4) } else { $null }
            num_fuentes       = @($resp.fuentes).Count
            fuentes           = @($resp.fuentes)
            respuesta         = $resp.respuesta
        }
        
        Write-Host " -> $($resp.tipo_mensaje) | $($Resultado.tiempo_seg)s | d=$($Resultado.distancia_prom)"
    }
    catch {
        Write-Host " -> ERROR: $($_.Exception.Message.Substring(0, 60))"
        $Resultado = @{
            id_pregunta       = $q.id
            pregunta          = $q.pregunta
            categoria_objetivo = $q.categoria_objetivo
            tema              = $q.tema
            tipo_mensaje      = "ERROR"
            tiempo_seg        = 0
            distancia_min     = $null
            distancia_prom    = $null
            num_fuentes       = 0
            fuentes           = @()
            respuesta         = "ERROR: $($_.Exception.Message)"
        }
    }
    
    $Resultados += $Resultado
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Guardando resultados en: $OutputFile"
$Resultados | ConvertTo-Json -Depth 5 | Set-Content $OutputFile

Write-Host ""
Write-Host "=== RESUMEN ==="
$m02 = ($Resultados | Where-Object { $_.tipo_mensaje -eq "M02" }).Count
$m04 = ($Resultados | Where-Object { $_.tipo_mensaje -eq "M04" }).Count
$m03 = ($Resultados | Where-Object { $_.tipo_mensaje -eq "M03" }).Count
$m05 = ($Resultados | Where-Object { $_.tipo_mensaje -eq "M05" }).Count
$m06 = ($Resultados | Where-Object { $_.tipo_mensaje -eq "M06" }).Count
$err = ($Resultados | Where-Object { $_.tipo_mensaje -eq "ERROR" }).Count
$tiempos = $Resultados | Where-Object { $_.tiempo_seg -gt 0 } | Select-Object -ExpandProperty tiempo_seg
$prom_t = if ($tiempos) { [math]::Round(($tiempos | Measure-Object -Average).Average, 2) } else { 0 }

Write-Host "M02: $m02/$($Preguntas.Count) | M04: $m04 | M03: $m03 | M05: $m05 | M06: $m06 | ERROR: $err"
Write-Host "Tiempo promedio: ${prom_t}s"
