# MT4 数据导出指南

## 导出步骤

### 方法一：MT4 账户历史导出（推荐）

1. 打开 MT4 交易平台
2. 在底部工具栏点击「账户历史」标签（Account History）
3. 在历史记录区域**右键单击**
4. 选择「自定义时段」（Custom Period）→ 选择全部历史
5. 再次右键 → **「保存为详细账户历史」**（Save as Detailed Account History）
6. 保存类型选择 **CSV 文件（*.csv）**
7. 保存完成后，在系统的「导入数据」页面上传该文件

### 方法二：MT4 报告导出

1. MT4 终端 → 文件 → 生成报告（Generate Report）
2. 选择 HTML 格式保存
3. 但本系统推荐使用方法一的 CSV 导出

## 支持的列名格式

系统支持以下列名（含中英文）：

| 英文列名 | 中文列名 | 说明 |
|---------|---------|------|
| Ticket | 订单号 | 必填 |
| Open Time | 开仓时间 | 必填 |
| Close Time | 平仓时间 | 已平仓单 |
| Symbol | 品种 | 必填，如 EURUSD |
| Type | 类型 | buy/sell |
| Volume / Lots | 手数 | 如 0.10 |
| Open Price | 开仓价 | |
| Close Price | 平仓价 | |
| SL / Stop Loss | 止损价 | |
| TP / Take Profit | 止盈价 | |
| Commission | 手续费 | |
| Swap | 库存费 | |
| Profit | 盈亏 | |
| Balance | 余额 | 用于资金曲线 |
| Comment | 注释 | |

## 注意事项

- 确保 CSV 文件是 **UTF-8 编码**（MT4 导出的中文文件通常是 UTF-8 BOM）
- 如果导入失败，请检查列名是否在支持列表中
- 系统会自动跳过已存在的订单号（Ticket），重复导入安全
- 如需重新导入，请先清理数据库

## 样例数据

可在系统页面下载样例 CSV 文件参考格式。
