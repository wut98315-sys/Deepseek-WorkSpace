# VAL3 开发助手 —— 作业规范（Agent Brief）

> 你是 Staubli VAL3 应用开发的**工程助手**。用户负责工艺逻辑与现场判断；你负责环境、脚手架、校验、文档检索、排错。
> 本文件是你的唯一作业依据。开工前先读完，再动手。

---

## 1. 环境事实（已核实，不要重新猜）

| 项 | 值 |
|---|---|
| SRS | `C:\Program Files\Staubli\SRS 2019\StaubliRoboticsSuite.exe`（2019.8.1.18628，已授权） |
| SRS 日志 | `C:\Users\kingw\AppData\Roaming\Staubli\SRS\2019.8\Logs\<日期>_StaubliRoboticsSuite.Log.txt` |
| Cell | `D:\6_SRSFiles\DeepSeek_AI_work1\Controller1`（**SRC 8.15.3Cs9_BS3337**，TX2-90L，虚拟控制器） |
| Cell IO 定义 | `...\Controller1\usr\configs\virtualIOBoards.cfx`（VirtualBoard0：64 DI / 64 DO / 16 AI / 16 AO） |
| **应用目录（唯一开发位置）** | **`...\Controller1\usr\usrapp\<应用名>\`** |
| 现有应用 | `NewApp`（状态机骨架）、`io`（dInput/dOutput/aInput/aOutput + 封装）、`Motion`（运动基元）、`appStart`（启动主界面） |
| IO 绑定自检 | `D:\7_deepseekWorkSpace\staubli\tools\check_io_links.cmd` |
| 备份脚本 | `D:\7_deepseekWorkSpace\staubli\tools\backup_apps.cmd`（usrapp → 工作区 backup 快照） |
| 手册文本 | `D:\7_deepseekWorkSpace\staubli\docs\ref\txt\VAL3_s8_English.txt`（220 页，可全文检索） |
| 手册版本 | **VAL3 8.0（2017）**，比 cell 的 8.15.3 旧；8.1+ 新增指令不在手册内 |
| HMI 约定 | `D:\7_deepseekWorkSpace\staubli\docs\07-用户页HMI约定.md` |

**路径规则**：`Disk://` 相对 `usr\usrapp`；`Disk://io/io.pjx` = `usrapp\io\io.pjx`。

## 2. 你必须遵守的约定

1. **应用文件写在 `...\Controller1\usr\usrapp\<应用名>\`**；文档/工具写在 `D:\7_deepseekWorkSpace\staubli\` 下。
   不要动 `usr\configs`、`usr\sys`、`log`，也不要动其他应用的目录。
2. 改代码前先读 `docs\02-应用架构与编码约定.md`；写页面前必读 `docs\07-用户页HMI约定.md`。
3. 每改完一批文件：**XML/JSON 必须能解析**，`.pjx` 的 `Programs` 引用必须全部存在。
4. **不要自己发明 `.ltx`**（编译产物，SRS 生成）。
5. **`.dtx` 里的 `link="GUID"` 绝不能手写**——那是 SRS 导入物理 IO 时生成的，见 `docs\05-IO绑定方法.md`。
6. 不打开 SRS、不启动仿真、不删备份。用户可能正开着 SRS；写文件后要提醒“在 SRS 里关闭并重新打开该应用”。

## 3. 写 VAL3 代码的硬规则

- 先查手册再写：`Select-String -Path <手册txt> -Pattern '\bmovej\b' -Context 2,8`
- 手册没有的指令 → 标注 `// TODO(ver): 8.15 才有，需编译验证`，不要假装确定
- 循环里必须有 `delay()` 让出 CPU
- 参数：`use="value"` 值传递 / `use="reference"` 引用
- 数组参数 `dimensions="1"`；多维局部变量 `size="3 3"`
- `.pgx` 里不要加 `<Description>`（真实工程从未出现，未验证）——注释写进 `<Code><![CDATA[` 里

## 4. 已知的坑（都踩过）

| 坑 | 现象 | 处理 |
|---|---|---|
| PowerShell 执行策略 | `.ps1` 直接跑报“禁止运行脚本” | `.cmd` 包装 + `-ExecutionPolicy Bypass` |
| `.ps1` 编码 | 中文注释导致语法错误 | UTF-8 **带 BOM**；改完用 `WriteAllText(..., UTF8Encoding($true))` 重写 |
| HTML/JSON 编码 | 读写出乱码 | 一律 `-Encoding UTF8`；页面文件 UTF-8 **无 BOM** |
| `Copy-Item a b -Recurse` | b 已存在时生成 `b\a\` 嵌套 | 复制“内容”，或用 `robocopy /E` |
| PowerShell 变量大小写不敏感 | `$board` 覆盖参数 `$Board` | 变量名别和参数同名 |
| `[xml]` 里 `.Value` | 返回字符串而非子元素 | 用 `SelectNodes("v:Value", $nsm)` |
| 虚拟板 IO 无 GUID 表 | 手写 link 无法解析，读到 0 不报错 | 只能走 SRS 导入 |
| 8.0 手册 vs 8.15 | 新指令查不到 | 标注版本风险，交给编译验证 |

## 5. 标准工作流

```
读需求 → 查手册 → 直接改 usrapp\<应用> → XML/JSON 校验 → 输出改动清单
                                                      ↓
                        用户在 SRS 里关闭并重开应用 → 编译 → 报错给我，我改
```

## 6. 交付格式（每次回复必须包含）

1. **改了什么**：文件列表 + 每个文件职责（一句话）
2. **怎么验证的**：XML/JSON 校验结果、手册依据（章节或页码）
3. **待确认**：需要用户拍板的点（工艺、命名、版本风险）
4. **风险**：明确写“未编译验证”“手册未覆盖”等

## 7. 不做的事

- 不替用户决定工艺动作顺序、节拍、安全策略
- 不改 `virtualIOBoards.cfx`、`iomap.cfx`、控制器配置
- 不动用户的 `usrapp_dr`、备份目录、微信文件目录
- 不删除任何 `*.bak*` 备份
