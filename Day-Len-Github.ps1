$Host.UI.RawUI.WindowTitle = "Day ma nguon len GitHub"
$env:Path = "$env:LOCALAPPDATA\Programs\MinGit\cmd;$env:Path"
Set-Location "D:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang"
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  🎀 DANG KET NOI VA DAY MA NGUON LEN GITHUB 🎀" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "Target: https://github.com/phamkhanhthi55-spec/THEO-D-I-H-NH-TR-NH-N-H-NG.git" -ForegroundColor Gray
Write-Host ""
git push -u origin main
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "HOAN TAT! Nhan phim bat ky de dong cua so nay..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
