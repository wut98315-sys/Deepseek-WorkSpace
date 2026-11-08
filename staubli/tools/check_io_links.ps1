# 检查 VAL3 应用的 IO 绑定状态（link 是否填好、是否有重复、和虚拟板通道数是否对得上）
# 用法：
#   check_io_links.cmd
#   check_io_links.cmd -Dtx "D:\...\usrapp\io\io.dtx" -Board "D:\...\usr\configs\virtualIOBoards.cfx"
param(
    [string]$Dtx   = "D:\6_SRSFiles\DeepSeek_AI_work1\Controller1\usr\usrapp\io\io.dtx",
    [string]$Board = "D:\6_SRSFiles\DeepSeek_AI_work1\Controller1\usr\configs\virtualIOBoards.cfx"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Dtx)) { throw "找不到 $Dtx" }

[xml]$d = Get-Content $Dtx -Raw
$nsm = New-Object System.Xml.XmlNamespaceManager($d.NameTable)
$nsm.AddNamespace("v", "http://www.staubli.com/robotics/VAL3/Data/2")

$rows = @()
foreach ($node in $d.SelectNodes("/v:Database/v:Datas/v:Data", $nsm)) {
    $type = $node.GetAttribute("type")
    if ($type -ne "dio" -and $type -ne "aio") { continue }

    $size  = [int]$node.GetAttribute("size")
    $links = @($node.SelectNodes("v:Value", $nsm) |
               ForEach-Object { $_.GetAttribute("link") } |
               Where-Object { $_ -and $_.Trim() -ne "" })

    $rows += [pscustomobject]@{
        Name    = $node.GetAttribute("name")
        Type    = $type
        Size    = $size
        Bound   = $links.Count
        Missing = $size - $links.Count
        Pct     = if ($size -gt 0) { [math]::Round(100 * $links.Count / $size) } else { 0 }
        Dup     = @($links | Group-Object | Where-Object Count -gt 1).Count
    }
}

"===== 应用侧：$Dtx ====="
if ($rows.Count -eq 0) {
    "（该应用没有 dio/aio 变量）"
} else {
    $rows | Format-Table Name, Type, Size, Bound, Missing, Pct, Dup -AutoSize | Out-String -Width 80
}

if (Test-Path $Board) {
    [xml]$bx = Get-Content $Board -Raw
    $root  = $bx.DocumentElement          # <VirtualIOBoards>
    $bEl   = $root.SelectSingleNode("Board")
    "===== 物理侧：$($bEl.GetAttribute('name')) ====="
    [pscustomobject]@{
        DInputs  = @($bEl.SelectNodes("DInputs/Dio")).Count
        DOutputs = @($bEl.SelectNodes("DOutputs/Dio")).Count
        AInputs  = @($bEl.SelectNodes("AInputs/Aio")).Count
        AOutputs = @($bEl.SelectNodes("AOutputs/Aio")).Count
    } | Format-Table -AutoSize | Out-String -Width 60
}

"===== 结论 ====="
if ($rows.Count -eq 0) {
    "没有可检查的 IO 变量。"
} else {
    $missing = ($rows | Measure-Object Missing -Sum).Sum
    $dup     = ($rows | Measure-Object Dup -Sum).Sum
    if ($missing -eq 0 -and $dup -eq 0) { "全部已绑定，无重复。" }
    else { "未绑定通道数：$missing；重复绑定数：$dup" }
}
