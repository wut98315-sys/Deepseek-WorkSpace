# 06 - P1 基础层 API（io / Motion）

> 状态：**未编译验证**。写于 SRC 8.15.3Cs9_BS3337（TX2-90L），手册依据为 VAL3 8.0 文本版
> `docs\ref\txt\VAL3_s8_English.txt`（页码为该 pdf 的打印页码）。
> 约定：参数 `x_` 前缀；输出参数一律 `use="reference"`，用 num 返回码（VAL3 的 `return` 不能带值，
> 所以"返回值"只能靠引用参数）。

## 1. io 应用（`app\io\`，对应 cell 里的 `usr\usrapp\io`）

源码是 cell 里的副本：`io.pjx` / `io.dtx` / `start.pgx` / `stop.pgx` 从
`D:\6_SRSFiles\DeepSeek_AI_work1\Controller1\usr\usrapp\io\` 原样复制（含 UTF-8 BOM），
`io.dtx` 一个字节都没改（**没有任何 link**，也就是还没绑定物理通道）。

| 程序 | 签名 | 返回码 |
|---|---|---|
| `getDigIO` | `(num x_nIndex, bool& x_bValue, num& x_nResult)` | 0 正常 / -1 越界 / -2 未绑定 |
| `setDigOutput` | `(num x_nIndex, bool x_bValue, num& x_nResult)` | 同上 |
| `waitDigInput` | `(num x_nIndex, bool x_bLevel, num x_nTimeout, bool& x_bDone, num& x_nResult)` | 0 到达 / -1 越界 / -2 未绑定 / -3 超时 / -4 超时参数 ≤0；超时 `x_bDone=false` |
| `getAnaIO` | `(num x_nIndex, num& x_nValue, num& x_nResult)` | 0 / -1 / -2 |
| `setAnaOutput` | `(num x_nIndex, num x_nValue, num& x_nResult)` | 0 / -1 / -2 |

调用示例（在 NewApp 里）：

```val3
call io:getDigIO(12,bVal,nRes)
call io:setDigOutput(3,true,nRes)
if io:waitDigInput(4,true,5.0,bDone,nRes)==0
  //到位
endIf
```

### 为什么先用 ioStatus 再读写

手册明确写着：**未 link 的 dio/aio 一旦参与运算就触发 runtime error**
（3.5.1 第 59 页、3.5.2 第 59 页、3.6.1 第 63 页），而 `ioStatus` 返回
`-1 = link（物理地址）未定义`（3.5.3 第 61 页）。
所以现在（还没做物理 IO 导入）：
- 读到的值就是恒 0 的占位值；
- 直接读会报运行时错误 → 封装里先 `ioStatus()` 拦截，返回 `-2`，把"没绑"翻译成返回码。

**要真正用：先在 SRS 里做物理 IO 导入**（`docs\05-IO绑定方法.md`），让 `io.dtx` 里出现 `link=`。

## 2. Motion 应用（`app\Motion\`）

引用 `Disk://io/io.pjx`（`autoload="true"`，照抄真实工程 `usrapp_dr\Motion\Motion.pjx` 的写法）。
`stackSize="200000"` 也照抄该工程（运动类应用默认值 5000 偏小）。

### 数据（`Motion.dtx`）

| 数据 | 类型 | 说明 |
|---|---|---|
| `mNomSpeed` | mdesc | 常规运动参数，vel=20% / accel=decel=25% / blend=off / leave=reach=0 |
| `mFine` | mdesc | 精定位参数，vel=10% / accel=decel=10% / blend=off（不混接，到位停稳） |
| `jHome` | joint | **全 0 占位**（joint 默认全 0，手册 9.2 第 131 页）→ TODO 示教真实 Home |
| `tTool` | tool | **flange 占位**（`fatherId="flange[0]"`，抄 `usrapp_dr\saveData\saveData.dtx`）→ TODO 做 TCP |
| `pStandby` | point | **坐标为 0 的占位点**（只给了 `fatherId="world[0]"`）→ TODO 示教，禁止直接运动 |

### 程序

| 程序 | 签名 | 说明 |
|---|---|---|
| `moveToPoint` | `(point x_pTarget, tool x_tTool, mdesc x_mDesc, num& x_nResult)` | `waitEndMove()` → `movel()` → `wait(getMoveId()>=id)` → `getMoveDone()` |
| `home` | `(num& x_nResult)` | `isInRange(jHome)` 校验 → `movej(jHome,tTool,mFine)` → 等到位 |
| `setSpeed` | `(num x_nPercent, num& x_nResult)` | 改 `mNomSpeed`：vel=百分比，accel/decel=vel²/100，blend=off |
| `getMoveDone` | `(num& x_nResult)` | `waitEndMove()` + `isSettled()` 轮询（2 s 上限，超时返回 1 不抛错） |

`moveToPoint` 的返回码：0=到位停稳，1=指令完但仍在抖，2=预留（中断）。

## 3. 手册依据（页码 = VAL3 8.0 手册打印页码）

| 用到的指令 | 位置 |
|---|---|
| `num size(*)` | 2.5.4 变量指令，第 31 页 |
| `num ioStatus(dio)` / `(dio,string&,string&)` | 3.5.3，第 61 / 62 页 |
| `dio` 类型与未 link 报错 | 3.5.1 / 3.5.2，第 59 页 |
| `num aioGet(aio)` | 3.6.2，第 63 页 |
| `num aioSet(aio,num)` / `num ioStatus(aio)` | 3.6.2，第 64 页 |
| `aio` 未 link 报错 | 3.6.1，第 63 页 |
| `bool watch(bool,num)` / `void delay(num)` / `num clock()` | 第 5 章，第 103 / 102 页 |
| `num movej(joint, tool, mdesc)` | 10.6，第 173 页（含"不能用 `{0,0,0,0,0,0}` 字面量"的告警） |
| `num movel(point, tool, mdesc)` | 10.6，第 174 页（含"不等待执行完"的 CAUTION） |
| `void waitEndMove()` | 10.6，第 177 页 |
| `bool isSettled()` | 10.6，第 178 页 |
| `num getMoveId()`（只能 `>=` 比较） | 10.4，第 180 页 |
| `bool isInRange(joint)` | 9.2，第 133 页 |
| `mdesc` 字段（accel/vel/decel/tvel/rvel/blend/leave/reach） | 10.5，第 172 页 |
| `joint` 类型（默认全 0） | 9.2，第 131 页 |
| `tool` 类型 | 9.5，第 143 页 |
| `point` 类型（trsf + config + 参考系） | 9.6，第 146 页 |

## 4. 已知风险

1. **全部未编译**：`.pgx` 只做了 XML 解析 + 引用完整性检查，语法要等 SRS 编译。
2. `.dtx` 里 `<Value .../>` 的属性名（`accel/vel/decel/blend/leave/reach`、`fatherId`）
   来自真实工程的 dtx，不是 8.0 手册；`joint` 全 0 与 `point` 占位没写 Value 数值。
3. 8.15 的 `pointRx/pointRs` 类型没采用（8.0 手册没有），用的是手册里的 `point`。
4. `waitDigInput` 的超时用 `watch()`，它只保证"条件 n 秒内成真"，不保证毫秒级精度。
