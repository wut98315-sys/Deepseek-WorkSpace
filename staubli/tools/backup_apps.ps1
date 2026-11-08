# 备份 cell 的 usrapp 到工作区快照（只读备份，不反向同步）
# 用法：backup_apps.cmd   或   backup_apps.cmd -Keep 20
param(
    [string]$Usrapp = "D:\6_SRSFiles\DeepSeek_AI_work1\Controller1\usr\usrapp",
    [string]$Out    = "D:\7_deepseekWorkSpace\staubli\backup",
    [int]$Keep      = 15
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Usrapp)) { throw "找不到 usrapp：$Usrapp" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dst = Join-Path $Out "usrapp_$stamp"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

# /E 递归；备份只留源码，排掉 SRS 生成的 .ltx
robocopy $Usrapp $dst /E /XF *.ltx /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 失败，exit=$LASTEXITCODE" }

$files = Get-ChildItem $dst -Recurse -File -Force
$mb = [math]::Round((($files | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ("备份完成: {0}  ({1} 个文件, {2} MB)" -f $dst, $files.Count, $mb)

# 只保留最近 N 份
$all = Get-ChildItem $Out -Directory -Filter "usrapp_*" | Sort-Object Name -Descending
if ($all.Count -gt $Keep) {
    $all | Select-Object -Skip $Keep | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force
        Write-Host "清理旧备份: $($_.Name)"
    }
}
