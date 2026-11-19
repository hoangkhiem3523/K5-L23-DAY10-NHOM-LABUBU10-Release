$dir = "d:\CODE\TrainAI\lab\K5-L23-DAY10-NHOM-LABUBU10-Release\data_source\cache\chunks_panoptic"
$target = "d:\CODE\TrainAI\lab\K5-L23-DAY10-NHOM-LABUBU10-Release\data_source\cache\panoptic_annotations_trainval2017.zip"
$total = 860725834
$prevBytes = 0
$prevTime = [DateTime]::Now

Write-Host "Dang ket noi toi tien do tai 16 luong... (Nhan Ctrl+C de thoat)"

while ($true) {
    if (Test-Path $target) {
        $finalSize = (Get-Item $target).Length
        if ($finalSize -eq $total) {
            Clear-Host
            Write-Host "==========================================================" -ForegroundColor Green
            Write-Host " [HOAN TAT 100%] Da ghep thanh cong $finalSize bytes!" -ForegroundColor Green
            Write-Host "==========================================================" -ForegroundColor Green
            break
        }
    }

    if (Test-Path $dir) {
        $chunks = Get-ChildItem $dir -Filter "*.tmp" -ErrorAction SilentlyContinue
        $now = [DateTime]::Now
        $sum = ($chunks | ForEach-Object { $_.Refresh(); $_.Length } | Measure-Object -Sum).Sum
        if (-not $sum) { $sum = 0 }
        
        $elapsed = ($now - $prevTime).TotalSeconds
        $speedMB = 0
        if ($elapsed -gt 0 -and $prevBytes -gt 0 -and $sum -ge $prevBytes) {
            $speedMB = [math]::Round(($sum - $prevBytes) / $elapsed / 1MB, 2)
        }
        $prevBytes = $sum
        $prevTime = $now

        $pct = [math]::Round($sum / $total * 100, 1)
        $mb = [math]::Round($sum / 1MB, 1)
        $barWidth = 32
        $filled = [math]::Floor($pct / 100 * $barWidth)
        $bar = ("=" * $filled) + ("." * ($barWidth - $filled))

        Clear-Host
        Write-Host "=====================================================================" -ForegroundColor Cyan
        Write-Host "           TIEN DO TAI COCO PANOPTIC (16 LUONG SONG SONG)            " -ForegroundColor Yellow
        Write-Host "=====================================================================" -ForegroundColor Cyan
        Write-Host " Tien do: [$bar] $pct%" -ForegroundColor Green
        Write-Host " Dung luong: $mb MB / 820.8 MB | Toc do: ~$speedMB MB/s" -ForegroundColor White
        Write-Host " So luong dang chay: $($chunks.Count) / 16 chunks" -ForegroundColor Gray
        Write-Host "---------------------------------------------------------------------"
        
        $chunkLines = @()
        for ($i = 0; $i -lt 16; $i += 4) {
            $row = @()
            for ($j = 0; $j -lt 4; $j++) {
                $idx = $i + $j
                $c = $chunks | Where-Object { $_.Name -eq ("chunk_{0:D2}.tmp" -f $idx) }
                $sz = if ($c) { [math]::Round($c.Length / 1MB, 1) } else { 0 }
                $row += ("C{0:D2}: {1,4}M" -f $idx, $sz)
            }
            Write-Host ($row -join "  |  ")
        }
        Write-Host "=====================================================================" -ForegroundColor Cyan
        Write-Host "(Nhan Ctrl + C bat cu luc nao de quay lai shell)" -ForegroundColor DarkGray
    }
    Start-Sleep -Seconds 2
}
