# Tạo shortcut ứng dụng trên Desktop
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Theo dõi hành trình đơn hàng.lnk"

$ExePath = "d:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang\dist\Theo-doi-hanh-trinh-don-hang\Theo-doi-hanh-trinh-don-hang.exe"
$IconPath = "d:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang\resources\icon.ico"
$WorkingDir = "d:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.IconLocation = $IconPath
$Shortcut.Description = "Ứng dụng Theo dõi hành trình đơn hàng SPX và GHN"
$Shortcut.Save()

Write-Host "Đã tạo shortcut thành công trên Desktop: $ShortcutPath"
