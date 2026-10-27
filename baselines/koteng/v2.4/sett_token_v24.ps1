$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$path=Join-Path $root '.ministaut-token'
Write-Host 'RBK KVINNER - KOTENG 2.4 - SIKKER TOKEN-KONFIGURERING'
Write-Host 'Bruk det eksisterende MINISTAUT_TOKEN fra den gamle PC-en.'
Write-Host 'Tokenet lagres kun i lokal .ministaut-token, aldri i Git eller skanningsrapportene.'
if (Test-Path -LiteralPath $path) {
    $answer=Read-Host 'Tokenfil finnes allerede. Vil du ERSTATTE den? (skriv JA)'
    if ($answer -cne 'JA') { Write-Host 'Ingen endringer gjort.'; exit 0 }
}
$secret=Read-Host 'Lim inn token (tegn vises ikke)' -AsSecureString
if ($null -eq $secret -or $secret.Length -eq 0) { Write-Host 'Ingen token angitt.'; exit 2 }
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $token=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    if ($token -notmatch '^(?:[a-f0-9]{64}|[A-Za-z0-9_-]{30,200})$') {
        Write-Host 'Token har feil format. Ingen fil skrevet.'; exit 2
    }
    [System.IO.File]::WriteAllText($path,$token,[System.Text.UTF8Encoding]::new($false))
    Write-Host 'Token lagret lokalt. Det er ikke kontrollert mot serveren enna.' -ForegroundColor Green
    exit 0
}
finally {
    if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $secret.Dispose()
}
