# MQL4 脚本自动连接配置指南

## 原理

MT4 没有对外公开的 REST API，但可以运行 **MQL4 脚本** 直接读取账户数据并通过 HTTP 推送到复盘系统。

工作流程：

```
MT4 客户端  ──运行脚本──→  MQL4 脚本读取历史订单  ──HTTP POST──→  复盘系统 Flask 服务器
(拖拽到图表)               (OrdersHistoryTotal)                (http://127.0.0.1:5000)
```

## 第一步：安装 MQL4 脚本

### 复制脚本文件

将以下两个文件复制到 MT4 的 `Experts\Scripts\` 目录：

```
TradeExport.mq4   →   %MT4_DATA_DIR%\MQL4\Scripts\TradeExport.mq4
AccountInfo.mq4   →   %MT4_DATA_DIR%\MQL4\Scripts\AccountInfo.mq4
```

两种方式找到你的 MT4 数据目录：

- **打开 MT4 → 文件 → 打开数据文件夹** (Open Data Folder)
- 或者在文件资源管理器中打开:
  - Windows: `%APPDATA%\MetaQuotes\Terminal\[实例ID]\MQL4\Scripts\`

### 编译脚本

1. 打开 MT4 → 工具 → MetaQuotes Language Editor (F4)
2. 在导航器中找到 `Scripts\TradeExport.mq4`
3. 右键 → 编译 (Compile) 或按 F7
4. 编译成功后，同目录会生成 `TradeExport.ex4`
5. 同样的步骤编译 `AccountInfo.mq4`

### (可选) 修改参数

脚本有可配置的输入参数，可在 MT4 中拖拽脚本时修改：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FlaskURL` | `http://127.0.0.1:5000` | 复盘系统地址 |
| `UseHTTP` | `true` | `true`=HTTP推送, `false`=导出CSV到本地 |
| `ExportFile` | `trade_history.csv` | CSV模式导出的文件名 |

## 第二步：配置 WebRequest 白名单

MT4 默认禁止脚本发送 HTTP 请求，需要手动开放权限：

1. **MT4 → 工具 → 选项 → EA 交易** (Tools → Options → Expert Advisors)
2. 勾选 **"允许WebRequest"** (Allow WebRequest for)
3. 在 URL 列表中添加：`http://127.0.0.1:5000`
4. 点击确定保存

![MT4 设置位置](https://i.imgur.com/placeholder.png)

> **注意**: 如果在模拟盘/有密码保护的账户中，还需要勾选 **"允许自动交易"** (虽然脚本不需要自动交易，但某些券商限制)

## 第三步：运行脚本

### 推送交易历史

1. 确保复盘系统 Flask 服务正在运行 (`python app.py`)
2. 打开 MT4，确保已登录要导出的账户
3. 从导航器 (Navigator) 找到 **TradeExport** 脚本
4. **拖拽** 到任意图表上
5. 在弹出的参数窗口中确认设置，点击 OK
6. 脚本运行完毕后会弹出成功提示

![拖拽脚本示意](https://i.imgur.com/placeholder.png)

### 获取账户信息

同样方式，拖拽 **AccountInfo** 脚本到图表运行，会弹出账户信息窗口并自动推送到复盘系统。

## 如果 HTTP 推送失败

### 常见原因

| 错误码 | 原因 | 解决 |
|--------|------|------|
| 4060 | WebRequest 未允许 | 检查 MT4 选项中的白名单 |
| 4062 | 连接超时 | Flask 服务未启动，或 IP/端口错误 |
| 4101 | 无效的输入参数 | 检查 JSON 数据格式 |
| 4200 | 对象已被删除 | 重新编译脚本 |

### 回退方案：CSV 模式

如果 HTTP 推送一直失败，可以将脚本的 `UseHTTP` 参数改为 `false`：

1. 拖拽 TradeExport 到图表
2. 将 `UseHTTP` 从 `true` 改为 `false`
3. 运行后，CSV 文件将导出到 `%APPDATA%\MetaQuotes\Terminal\[实例ID]\Files\trade_history.csv`
4. 然后在复盘系统的「导入数据」页面手动上传该文件

## 自动扫描模式

复盘系统还可以自动扫描 MT4 的公共文件目录：

```
GET http://127.0.0.1:5000/import/api/scan_csv
```

系统会查找 `%APPDATA%\MetaQuotes\Terminal\**\trade_export*.csv` 并自动导入。

可以设置定时任务（Windows 任务计划程序）定期调用此接口实现全自动导入。

### Windows 定时任务示例

```batch
# 创建每天收盘后自动导入的任务
schtasks /create /tn "TradeJournalAutoImport" /tr "curl http://127.0.0.1:5000/import/api/scan_csv" /sc daily /st 20:00
```

## 小技巧

1. **快捷键**: 可以在 MT4 中为脚本设置快捷键 (右键脚本 → 设置快捷键)
2. **批量导入**: 如果有多个账户，复制脚本修改 `FlaskURL` 参数即可
3. **实时监控**: 系统会在仪表盘显示最新账户信息，可定期运行 AccountInfo 脚本更新
4. **防火墙**: 确保 Windows 防火墙没有阻止 5000 端口的本地通信
