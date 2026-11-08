# SRS 2019 开发环境核验报告

> **2026-11-07 16:20 更新**：本文第 2、4 节的"最高 8.12"结论已被推翻——SRS 2019.8.1 实际可创建 **8.15.3Cs9_BS3337** 仿真控制器（证据：新建 cell `D:\6_SRSFiles\DeepSeek_AI_work1\Controller1`）。以 `staubli\docs\01-版本与控制器对齐.md` 为准。

核验时间：2026-11-07 16:00 左右 ｜ 核验方式：本机文件系统、注册表、服务、日志、网络实测

---

## 1. 软件与许可（已核实）

| 项 | 实测结果 |
|---|---|
| 安装路径 | `C:\Program Files\Staubli\SRS 2019\` |
| 版本 | **2019.8.1.18628**（ProductName: SRS 2019 - STAUBLI Robotics Suite） |
| 安装时间 | 2026-08-04 16:33–16:36 |
| 许可 | **Sentinel LDK License Manager (hasplms) 服务运行中**；未检测到 USB 加密狗 → 是**软授权（已激活）** |
| 已装模块 | VAL3 Studio、Debugger（+Soap）、Emulator、3DView、UserPage、RemoteMaintenance、PhysicalIO（Applicom / CoDeSys / Hilscher / StaubliIO / Cs9）、Safety、DataEditor、IoMapEditor、Recorder |
| 附带工具 | TransferManager.exe、RemoteAccess.exe、LicenseMgr.exe、ModbusIoConfig.exe、EncryptTools.exe |
| 运行记录 | 今天 15:59:13 启动一次，初始化日志正常结束；Windows 事件日志无 SRS 崩溃记录；当前进程已退出 |
| 附带文档 | `etc\zh\SRS 2019.pdf`（8 种语言）、`ChangeLog.pdf`、`readme.pdf` |
| **缺失文档** | **VAL3 参考手册 / 编程指南不在本机**（SRS 只带 SRS 自身手册） |

## 2. 本机 SRS 支持的 SRC/VAL3 版本

来自 `RobotInfo.json` 的 `SrcVersions`：

```
s8.12Cs9_BS2378        ← CS9，VAL3 8.12
s7.11.2                ← CS9，VAL3 7.11.2
s6.9.1                 ← CS8，VAL3 6.9.1
s5.6.1                 ← 更老的 SRC
```

## 3. 机器上已经存在的 VAL3 资产（重要）

| # | 资产 | 路径 | 机器人/控制器 | 工程声明版本 | 内容 |
|---|---|---|---|---|---|
| A | 控制器备份（2026-04） | `D:\3_个人\3_wechatFile\xwechat_files\wt547087874_c7ec\msg\file\2026-04\机器人程序` | **TX2-90L**（arm 配置 `tx2_90l-S2`，floor），SN `F_21_0027014_C_004` | **s8.12.1cs9_BS2449** | usrapp: `ValSolar_SP2`、`HMI_SP2`、`data`、`io`、`motion`、`prog_Advance`、`LicenceCode`；含 `doc\safetyStop.csv`、`arm/controller/cell/network.cfx` |
| B | 控制器备份（2026-08-06，带 backup_OK 日志） | `D:\0_HX\F17_5AEXD1_C_01\Y-2026_M-08_D-06_13h54m` | 控制器 `F17_5AEXD1_C_01`（CS9） | **s7.11.2** | usrapp: `Paoguang`（抛光）、`V800_D_paoguang`、`saveData`、`V800_D_savedate`、`userPage`；含 sys/log 全量 |
| C | 源码级应用工程（桌面，2026-08-27） | `C:\Users\kingw\Desktop\usrapp_dr` | CS9（配套 A 的网络） | **s8.15.3cs9_BS3337** | MAIN（约 50 个 `.pgx`：HMI/PLC/init/motion/signal/simulation/taskManager/userProg1-5…）、Motion、Products、io、config、robotStatus、vision、source（TRAJ/HMI/libDynamicData/limitTorqueAndVel/Recorder）、test、xukang1 |
| D | RoboDK 激光切割工程 | `C:\Users\kingw\Documents\RoboDK\...` | — | — | `Laser_cutting_part_v2*`、`Programs\P1`（含 .pjx，来自 RoboDK 后处理） |

### TX2-90L 控制器关键配置（来自资产 A，可直接用）

```
arm            : tx2_90l-S2, mount = floor, oil = STD
serialNumber   : F_21_0027014_C_004
hostname       : F-21-0027014-C-004
ipAddress      : 192.168.0.254 / 255.255.255.0     (第二地址 172.31.0.1/16)
端口           : SOAP 5653, REST 2400, OPC UA 4880, userpage 10101
autoStart      : ValSolar_SP2
language       : chinese
```

### 本机网络现状

- 本机以太网：**192.168.0.29 / 255.255.255.0**，网关 192.168.0.1 → **与控制器 192.168.0.254 同网段**
- 实测：ping 192.168.0.254 = 不通；TCP 5653 = 不通；TCP 21 = 不通
- 结论：**控制器当前未上电/未接线**（网络配置本身是对的，接上即可连）

## 4. 版本兼容性风险（必须先决策）

| 资产 | 声明版本 | SRS 2019.8.1 内置 | 判断 |
|---|---|---|---|
| B：Paoguang 备份 | s7.11.2 | s7.11.2 | ✅ 完全匹配，可开可编译 |
| A：ValSolar 备份 | s8.12.1_BS2449 | s8.12 (BS2378) | ⚠️ 主版本一致、构建号不同，大概率能开；若提示版本不匹配需实测确认 |
| C：usrapp_dr 桌面工程 | **s8.15.3_BS3337** | 最高 s8.12 | ❌ **高于本机 SRS**，很可能只能只读或拒绝编译 |

> 这三套代码的版本是**三个不同代**（8.12 / 7.11 / 8.15），不是同一套代码的三个副本。要先确定以哪一套为准，否则后面全是版本返工。

## 5. 结论

**环境本身是齐的**：安装、许可、仿真器、调试器、3D 视图、IO 编辑器都在，能开 cell、能仿真、能连真机。
**真正缺的只有 4 件事**：

1. **目标定义** —— 你要写的是哪台机器、哪套程序（A/B/C/全新）。
2. **版本策略** —— 以 8.12 为基线（SRS 2019 可编译），还是升级 SRS 以支持 8.15.3。
3. **VAL3 参考手册**（7.11 / 8.12 / 8.15 对应版本）—— 写新代码必须照手册，现有代码只能当"用法样例"。
4. **控制器在线**（TX2-90L，192.168.0.254）—— 只有它上线，才能做到"改完即下载验证"。

## 6. 不需要你提供的（已在手）

- ❌ 不需要 SRS 安装包（已装已授权）
- ❌ 不需要机器人型号/坐标系/IO 表（备份里有 arm.cfx / system.zfx / sio.cfx）
- ❌ 不需要网络参数（network.cfx 里有）
