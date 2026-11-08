# Stäubli VAL3 应用工作区

**开发路径（唯一）**

```
D:\6_SRSFiles\DeepSeek_AI_work1\Controller1\usr\usrapp\<应用名>\
```

应用直接写在 SRS cell 的 usrapp 里，不再有"工作区源码 + 部署"两套副本。

| 项 | 值 |
|---|---|
| Cell | `D:\6_SRSFiles\DeepSeek_AI_work1\Controller1` |
| SRC 版本 | **s8.15.3cs9_BS3337** |
| 机器人 | TX2-90L（`TX2_90L-HB-L-WS`，floor） |
| 虚拟板 | VirtualBoard0：64 DI / 64 DO / 16 AI / 16 AO |

## 现有应用

| 应用 | 内容 |
|---|---|
| `NewApp` | 状态机骨架：init / start / stop / taskManager / stateMachine（0/10/20/30/90） |
| `io` | `dInput[64]` `dOutput[64]` `aInput[16]` `aOutput[16]` + 5 个封装（getDigIO / setDigOutput / waitDigInput / getAnaIO / setAnaOutput） |
| `Motion` | 运动基元：moveToPoint（movel）/ home（movej）/ getMoveDone / setSpeed；`mNomSpeed` `mFine` |
| `appStart` | 启动主界面：MainApp 标题、型号/S/N、权限切换（生产员/工程师）、9 个功能按钮 |

## 目录（工作区只放资料与工具）

```
staubli\
├─ README.md
├─ agent\VAL3_DEV_AGENT.md        助手作业规范（换会话先读这个）
├─ docs\
│  ├─ 01-版本与控制器对齐.md
│  ├─ 02-应用架构与编码约定.md
│  ├─ 03-需求输入清单.md
│  ├─ 05-IO绑定方法.md
│  ├─ 06-IO与运动基元API.md
│  ├─ 07-用户页HMI约定.md
│  └─ ref\                        手册 PDF + 转出的 txt（可全文检索）
├─ tools\
│  ├─ check_io_links.cmd          IO link 绑定自检
│  ├─ backup_apps.cmd             usrapp → backup 快照（保留最近 15 份）
│  └─ pdf2txt.py                  PDF 手册转文本
└─ backup\usrapp_<时间戳>\        自动备份
```

## 日常工作流

```
1. 改 ...\usrapp\<应用>\ 下的文件
2. 自检（XML/JSON 能解析、.pjx 引用齐全、IO 是否绑好）
3. 在 SRS 里：关闭该应用 → 重新打开 → 编译
4. 改动较大前先跑一次 backup_apps.cmd
```

> **SRS 开着的时候改文件**：SRS 有内存缓存，改完必须关闭并重新打开应用才生效；否则它保存时会用旧内容覆盖你的修改。

## 当前状态

- ✅ SRS 2019.8.1 已授权，能建 8.15.3 仿真控制器
- ✅ `NewApp` 已在仿真里跑通（任务创建 + 状态机）
- ✅ `io` / `Motion` 已建好，**未编译验证**
- 🚧 `appStart` 在建（HTML 页面 + 绑定 + 权限切换）
- ❌ `io` 的 4 个数组**尚未绑定物理通道**（需要在 SRS 做一次物理 IO 导入，见 docs\05）
- ❌ 工艺逻辑未写（缺 `docs\03-需求输入清单.md` 的工艺动作序列）
