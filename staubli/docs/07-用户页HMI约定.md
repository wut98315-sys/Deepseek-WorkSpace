# 用户页（HMI）约定 —— 从真实工程反推

> 样本来源：`D:\3_个人\...\2026-04\机器人程序\usrapp\data\HMI_SP2`（16 个页面，生产在用）。
> 手册依据：VAL3 RM 8.0 第 75–82 页（userPage 系列）、第 83 页（getProfile/setProfile）、第 124 页（getVersion）。

## 1. 文件布局

```
usrapp/<应用名>/
├─ <应用名>.pjx
├─ <应用名>.dtx
├─ Page_<页面>.pgx        ← 页面初始化/绑定（每个页面一个）
├─ _<动作>.pgx            ← 事件回调（无参数程序）
├─ taskHmi.pgx            ← 常驻任务：开页面 + 绑事件
└─ interface/
   ├─ <页面>.html          ← 页面本体
   └─ <页面>.bindings.json ← 绑定表（SRS 设计器读它）
```

## 2. HTML 骨架（必须原样保留）

```html
<!DOCTYPE html SYSTEM "-//W3C//DTD VALHTML Strict//EN">
  <html xmlns="http://www.staubli.com/robotics/2016/03/valhtml">
    <head>
      <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></meta>
      <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"></meta>
      <meta http-equiv="Pragma" content="no-cache"></meta>
      <meta http-equiv="Expires" content="0"></meta>
      <script type="text/javascript" src="/vendor/libs/stblUserPage.min.js"></script>
      <link href="/vendor/libs/up.min.css" rel="stylesheet" media="all" type="text/css"></link>
      <link rel="stylesheet" href="../userPage/CSS/USR.css"></link>
      <link rel="stylesheet" href="../userPage/font-awesome-4.7.0/css/font-awesome.css"></link>
    </head>
    <body style="width: 480px; height: 690px; margin: 0; background-color: #FFFFFF">
```

- 画布固定 **480 × 690**（SP2 屏幕），元素用 `position: absolute` + `left/top` 摆放（真实工程就是这么干的，不用 flex）
- `class="USR-btn"` / `"USR-select"` 是框架的交互样式，按钮/可选块要带上
- 按钮文本不要写死在 HTML 里，交给 bindings 的 `innerHTML`（便于多语言/改词）
- 文件必须 **UTF-8 无 BOM**

## 3. `<页面>.bindings.json`

```json
{
  "version": "1.0",
  "bindings": [
    { "id": "lbl_model", "attribute": "innerHTML", "data": "sRobotModel[0]", "size": 1, "direction": "r", "refresh": 1 },
    { "id": "btn_1",     "attribute": "disabled",  "data": "bBtnDisable[0]",   "size": 1, "direction": "r", "refresh": 1 }
  ],
  "callbacks": [
    { "id": "btn_1", "event": "click", "data": "_clickFunc1", "priority": 10 }
  ]
}
```

- `data` 是 **VAL3 表达式字符串**，可带库前缀：`io:sRunningStatus[0]`、`data:nRealBoatSize[0]`、`sHmiTxt["page_Simulation"]`
- `direction`：`"r"` 只读（VAL3 → 页面）、`"w"` 只写、`"rw"` 双向
- `attribute` 可以是 `innerHTML`、`disabled`、`style.backgroundColor`、`style.visibility`、`value` 等
- `callbacks.data` = **VAL3 程序名**，该程序必须无参数、同属本应用；`event` 目前见到的只有 `"click"`

## 4. 运行时 API（手册 75–82 页）

| 指令 | 用途 |
|---|---|
| `num userPage(string sPage)` | 打开页面（路径为 `interface/` 下的页面名） |
| `userPageBind(page, id, attrib, var, size, direction, refresh)` | 运行时绑定属性 |
| `userPageBindClick(page, id, bool& bVar, bool bValue)` | **把点击直接绑到 bool 变量**（9 个功能按钮最省事的写法） |
| `userPageUnbind(...)` / `userPageUnbindClick(...)` | 解绑 |
| `userPageSet(page, id, attrib, value)` | 直接设置属性 |
| `userPageAlert(sMsg)` / `bool userPageConfirm(sMsg)` | 弹窗 |
| `bool userPagePrompt(sMsg, string& sEntry)` / `(sMsg, num& nNum)` | 输入框 |

真实工程写法（`taskHmi.pgx`）：

```
userPage("home")
userPageBindClick("home","btn_Simulation",bPage_select["btn_Simulation"],true)
```

## 5. 取设备信息（手册 124 页 getVersion）

| 参数 | 返回示例 |
|---|---|
| `getVersion("Arm Type")` | `tx2_90-S1` |
| `getVersion("Arm S/N")` | `F07_12R3A1_A_01` |
| `getVersion("Controller S/N")` | `F07_12R3A1_C_01` |
| `getVersion("System")` | `s8.0cs9_B587` |
| `getVersion("Arm Mounting")` | `floor` |

## 6. 用户权限（手册 83 页）

| 指令 | 说明 |
|---|---|
| `string getProfile()` | 当前用户 profile 名（如 `operator` / `programmer` / `maintainer`） |
| `num setProfile(sLogin, sPassword)` | 切换 profile，返回 `0` 成功；`-1` 未定义；`-3` 不允许 staubli；`-4` 当前是 staubli 不能改 |

## 7. 坑

0. **页面资源必须随应用一起复制**（踩过）：`../userPage/CSS/USR.css`、`../userPage/font-awesome-4.7.0/...` 是**每个应用自己目录下**的副本，不是全局的。新建应用的 `interface/` 里只有 html/json 时，页面会 404 且样式全丢。做法：从已有应用（如 `HMI_SP2\userPage\`，37 个文件 1.26 MB）整目录拷过来。
   另外 `USR.css` 内部还引用了 `../../interface/images/dropdown.png` 和 `../../interface/JPG/lock.png`，缺了也会 404（`dropdown.png` 连生产工程里都没有，属于历史遗留，补个占位图即可）。
   注意 `/vendor/libs/*` 是**控制器全局**资源，由模拟器/控制器 web 服务提供（实测 `https://localhost:850/vendor/libs/up.min.css` 返回 200），不需要拷。
1. 中文必须 UTF-8；用 PowerShell 处理 HTML/JSON 时务必 `-Encoding UTF8`，否则会写进乱码（本机 PS 5.1 默认 ANSI）
2. `interface/` 必须与 `.pjx` 同目录；改完页面要重新 `userPage()` 才生效
3. 回调程序不能有参数，否则下拉里选不到
4. 页面里不要引外网 CDN，控制器离线
5. `bindings.json` 只是设计器的元数据，**运行时以 `.pgx` 里的 bind 调用为准**；两边不一致时以代码为准
