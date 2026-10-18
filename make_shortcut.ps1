
$WshShell = New-Object -ComObject WScript.Shell
$desktopPaths = @(
    [Environment]::GetFolderPath("Desktop"),
    "C:\Users\KHANH THI\Desktop",
    "C:\Users\KHANH THI\OneDrive\Desktop"
) | Select-Object -Unique

$exePath = "D:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang\dist\Theo-doi-hanh-trinh-don-hang\Theo-doi-hanh-trinh-don-hang.exe"
$iconPath = "D:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang\resources\hello_kitty.ico"
$workingDir = "D:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang"

foreach ($dp in $desktopPaths) {
    if (Test-Path $dp) {
        # Xoa shortcut cu
        $oldFiles = @(
            (Join-Path $dp "Theo dõi hành trình đơn hàng.lnk"),
            (Join-Path $dp "THEO DOI DON HANG.lnk")
        )
        foreach ($f in $oldFiles) {
            if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
        }

        # Tao shortcut THEO DÕI ĐƠN HÀNG
        $targetLnk = Join-Path $dp "THEO DÕI ĐƠN HÀNG.lnk"
        $s = $WshShell.CreateShortcut($targetLnk)
        $s.TargetPath = $exePath
        $s.WorkingDirectory = $workingDir
        $s.IconLocation = "$iconPath,0"
        $s.Description = "Theo dõi hành trình đơn hàng Hello Kitty"
        $s.Save()
        Write-Host "Success created: $targetLnk"
    }
}
