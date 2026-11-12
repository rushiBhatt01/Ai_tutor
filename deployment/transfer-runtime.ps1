param(
    [Parameter(Mandatory = $true)] [string] $HostName,
    [Parameter(Mandatory = $true)] [string] $RuntimeFile,
    [string] $UserName = 'ubuntu',
    [string] $SshKey = (Join-Path $env:USERPROFILE '.ssh\oci-ai-tutor-20261107-151654\ssh-key-2026-11-07.key')
)

$ErrorActionPreference = 'Stop'
if ($UserName -notmatch '^[a-z_][a-z0-9_-]{0,30}$' -or $HostName -notmatch '^[a-zA-Z0-9.:-]+$') {
    throw 'Host or username contains unsupported characters.'
}
$runtimePath = (Resolve-Path -LiteralPath $RuntimeFile).Path
$keyPath = (Resolve-Path -LiteralPath $SshKey).Path
if ($env:OneDrive) {
    $oneDrivePath = [System.IO.Path]::GetFullPath($env:OneDrive).TrimEnd('\') + '\'
    if ($runtimePath.StartsWith($oneDrivePath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Move the runtime file to a user-only local directory outside OneDrive before transfer.'
    }
}
$currentUser = "$env:USERDOMAIN\$env:USERNAME"
$acl = Get-Acl -LiteralPath $runtimePath
$unexpected = @($acl.Access | Where-Object { $_.IdentityReference.Value -notin @($currentUser, 'NT AUTHORITY\SYSTEM') })
if ($unexpected.Count -gt 0) {
    throw 'Runtime file ACL grants access beyond the current user and SYSTEM; restrict it before transfer.'
}

$remote = "$UserName@$HostName"
$staging = "/home/$UserName/.local-secrets-transfer/runtime.env.pending"
$sshOptions = @('-i', $keyPath, '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes')
& ssh @sshOptions $remote "umask 077 && install -d -m 700 /home/$UserName/.local-secrets-transfer"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the private remote staging directory.' }
& scp @sshOptions $runtimePath "${remote}:$staging"
if ($LASTEXITCODE -ne 0) { throw 'Secure copy failed.' }
& ssh @sshOptions $remote "sudo install -d -o root -g root -m 700 /etc/ai-tutor && sudo install -o root -g root -m 600 $staging /etc/ai-tutor/runtime.env && rm -f $staging"
if ($LASTEXITCODE -ne 0) { throw 'Remote installation failed; inspect and remove the private staging file over SSH.' }
Write-Output 'Runtime configuration transferred over verified SSH and installed root-only at /etc/ai-tutor/runtime.env. No secret values were printed.'
