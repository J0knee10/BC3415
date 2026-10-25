# Makes TagUI v6.110 (last release, June 2022) work with current Chrome and Windows 11.
# Run once after unzipping TagUI:
#   powershell -ExecutionPolicy Bypass -File tools\patch_tagui_2026.ps1 -TagUISrc C:\tagui\src
# Safe to run again: each fix is skipped if already applied. Originals are kept as *.orig.
#
# Fixes, each found while building this bot:
#   1. Chrome 111+ refuses DevTools websocket connections from TagUI's PHP bridge
#      unless started with --remote-allow-origins=*  (symptom: hangs at "listening for inputs")
#   2. wmic.exe was removed in Windows 11 24H2+; TagUI used it to find and close its Chrome
#      -> replaced with a PowerShell helper (tagui_pid.ps1)
#   3. the casperjs PATH check looks for "casperjs" but the Windows package ships "casperjs.exe"
#      (symptom: 'casperjs' is not recognized)
#   4. "find /i" can resolve to Git's Unix find.exe and scan the whole drive
#      -> pinned to %SystemRoot%\System32\find.exe
#   5. element screenshots were clipped with viewport coordinates and came out blank
#      for anything below the fold -> page coordinates + captureBeyondViewport
param([Parameter(Mandatory = $true)][string]$TagUISrc)

$ErrorActionPreference = 'Stop'
$latin1 = [Text.Encoding]::GetEncoding(28591)
$cmd = Join-Path $TagUISrc 'tagui.cmd'
$hdr = Join-Path $TagUISrc 'tagui_header.js'
foreach ($f in $cmd, $hdr) {
    if (-not (Test-Path $f)) { throw "Not a TagUI src folder: $f missing" }
    if (-not (Test-Path "$f.orig")) { Copy-Item $f "$f.orig" }
}

$s = [IO.File]::ReadAllText($cmd, $latin1)

# 1
$s = $s.Replace('set chrome_switches=--remote-debugging-port=9222 about:blank',
                'set chrome_switches=--remote-debugging-port=9222 --remote-allow-origins=* about:blank')

# 2
$wmic = [regex]"``wmic process where ""caption like '%%(chrome|msedge)\.exe%%' and commandline like '%%tagui_user_profile_ --remote-debugging-port=9222%%' and not commandline like '%%--type=renderer%%'"" get processid[^``]*``"
$s = $wmic.Replace($s, { param($m) '`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tagui_pid.ps1" ' + $m.Groups[1].Value + '.exe`' })
@'
# Replacement for wmic (removed in Windows 11 24H2+): print the PID of TagUI's own
# browser process (the one started with the TagUI profile and debugging port).
param([string]$Name = 'chrome.exe')
Get-CimInstance Win32_Process -Filter "Name='$Name'" |
  Where-Object { $_.CommandLine -like '*tagui_user_profile*' -and $_.CommandLine -like '*--remote-debugging-port=9222*' -and $_.CommandLine -notlike '*--type=*' } |
  Sort-Object ProcessId -Descending | Select-Object -First 1 -ExpandProperty ProcessId
'@ | Set-Content -Path (Join-Path $TagUISrc 'tagui_pid.ps1') -Encoding ascii

# 3
$s = $s.Replace('if exist "%~dp0casperjs\bin\casperjs" set', 'if exist "%~dp0casperjs\bin\casperjs.exe" set')

# 4
$s = [regex]::Replace($s, '(?<!\\)find /i /c', '%SystemRoot%\System32\find.exe /i /c')

[IO.File]::WriteAllText($cmd, $s, $latin1)

# 5
$h = [IO.File]::ReadAllText($hdr, [Text.Encoding]::UTF8)
$oldClip = 'var clip = {x:selector_rect.left, y:selector_rect.top, width:selector_rect.width, height:selector_rect.height, scale:1};'
if ($h.Contains($oldClip)) {
    $h = $h.Replace($oldClip,
        "var scroll_xy = {x: 0, y: 0}; try {scroll_xy = JSON.parse(chrome_step('Runtime.evaluate',{expression: '({x: window.scrollX, y: window.scrollY})', returnByValue: true})).result.result.value;} catch(e) {} " +
        "// patched: CDP clip wants page coordinates, getBoundingClientRect gives viewport ones`n" +
        'var clip = {x:selector_rect.left + scroll_xy.x, y:selector_rect.top + scroll_xy.y, width:selector_rect.width, height:selector_rect.height, scale:1};')
    $h = $h.Replace('clip: clip, fromSurface: fromSurface});', 'clip: clip, fromSurface: fromSurface, captureBeyondViewport: true});')
    [IO.File]::WriteAllText($hdr, $h, (New-Object Text.UTF8Encoding $false))
}

$checks = [ordered]@{
    '1 Chrome origin flag'      = $s.Contains('--remote-allow-origins=*')
    '2 wmic replaced'           = -not $s.Contains('wmic process where "caption like ''%%chrome.exe%%'' and commandline like ''%%tagui_user_profile_')
    '3 casperjs.exe check'      = $s.Contains('casperjs\bin\casperjs.exe" set')
    '4 Windows find pinned'     = -not ([regex]::IsMatch($s, '(?<!\\)find /i /c'))
    '5 element snapshot fix'    = $h.Contains('captureBeyondViewport: true')
}
$checks.GetEnumerator() | ForEach-Object { '{0,-26} {1}' -f $_.Key, $(if ($_.Value) { 'OK' } else { 'NOT APPLIED' }) }
