# Визначає стать героя з найсвіжішого збереження Starfield (*.sfs).
# Код виходу: 10 = чоловік, 11 = жінка, 0 = не вдалося визначити.
param([string]$Saves)
try {
    $f = Get-ChildItem -Path (Join-Path $Saves '*.sfs') -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { exit 0 }
    $fs = [IO.File]::OpenRead($f.FullName)
    $b = New-Object byte[] 65536
    $n = $fs.Read($b, 0, $b.Length); $fs.Close()
    $i = [Text.Encoding]::ASCII.GetString($b, 0, $n).IndexOf('ZIP ')
    if ($i -lt 0) { exit 0 }
    $j = $i   # початок zlib-потоку: 0x78 і (CMF*256+FLG) кратне 31
    while ($j -lt $n - 1 -and -not ($b[$j] -eq 0x78 -and ((0x78 * 256 + $b[$j + 1]) % 31) -eq 0)) { $j++ }
    $ms = [IO.MemoryStream]::new($b, ($j + 2), ($n - $j - 2))
    $ds = [IO.Compression.DeflateStream]::new($ms, [IO.Compression.CompressionMode]::Decompress)
    $d = New-Object byte[] 4096; $got = 0
    while ($got -lt $d.Length) { $r = $ds.Read($d, $got, $d.Length - $got); if ($r -le 0) { break }; $got += $r }
    if ([Text.Encoding]::ASCII.GetString($d, 0, 12) -ne 'SFS_SAVEGAME') { exit 0 }
    $o = 12 + 4 + 4 + 4 + 1
    function Skip-Str { $script:o += 2 + [BitConverter]::ToUInt16($d, $script:o) }
    Skip-Str; $o += 4; Skip-Str; Skip-Str; Skip-Str        # ім'я, рівень, локація, час гри, раса
    $sex = [BitConverter]::ToUInt16($d, $o)
    if ($sex -eq 0) { exit 10 } elseif ($sex -eq 1) { exit 11 } else { exit 0 }
} catch { exit 0 }
