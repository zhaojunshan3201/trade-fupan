//+------------------------------------------------------------------+
//|                                            TradeExport.mq4       |
//| 自动导出MT4交易历史到复盘系统                                      |
//| 使用方式: 编译后拖拽到任意图表运行一次即可                          |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

// ---- 输入参数 ----
input string FlaskURL    = "http://127.0.0.1:5000";  // Flask 服务器地址
input bool   UseHTTP     = true;                      // true=HTTP推送, false=导出CSV到本地
input string ExportFile  = "trade_history.csv";       // CSV模式: 导出文件名

//+------------------------------------------------------------------+
//| 程序入口                                                          |
//+------------------------------------------------------------------+
void OnStart()
{
    // 确保至少执行了一条交易
    int total = OrdersHistoryTotal();
    if(total == 0)
    {
        MessageBox("账户历史中没有已平仓订单。\n请确保已选择正确的账户且有交易记录。", "TradeExport", MB_ICONINFORMATION);
        return;
    }

    // 构建数据
    string jsonBody = BuildOrdersJson(total);
    string csvBody = BuildOrdersCsv(total);

    bool success = false;

    if(UseHTTP)
    {
        success = PushToServer(jsonBody);
        if(success)
            MessageBox(StringFormat("成功推送 %d 笔交易到复盘系统！", total), "✅ TradeExport", MB_ICONINFORMATION);
        else
        {
            int ret = MessageBox("HTTP推送失败，是否导出CSV文件到本地？", "❌ 推送失败", MB_YESNO | MB_ICONQUESTION);
            if(ret == IDYES)
                success = ExportCsvLocal(csvBody);
        }
    }
    else
    {
        success = ExportCsvLocal(csvBody);
        if(success)
            MessageBox(StringFormat("成功导出 %d 笔交易到:\n%s\\Files\\%s",
                        total, TerminalInfoString(TERMINAL_COMMONDATA_PATH), ExportFile),
                        "✅ TradeExport", MB_ICONINFORMATION);
    }

    if(!success)
        MessageBox("导出失败，请检查:\n1. Flask 服务器是否运行\n2. MT4 工具→选项→EA交易→允许WebRequest\n3. 防火墙设置", "❌ 错误", MB_ICONERROR);
}

//+------------------------------------------------------------------+
//| 构建 JSON 数据                                                    |
//+------------------------------------------------------------------+
string BuildOrdersJson(int total)
{
    string json = "[";
    for(int i = 0; i < total; i++)
    {
        if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
        if(OrderCloseTime() == 0) continue; // 跳过持仓单

        string comma = (i < total - 1) ? "," : "";
        json += StringFormat(
            "{%s"
            "\"ticket\":%d,%s"
            "\"symbol\":\"%s\",%s"
            "\"type\":\"%s\",%s"
            "\"volume\":%g,%s"
            "\"open_time\":\"%s\",%s"
            "\"close_time\":\"%s\",%s"
            "\"open_price\":%g,%s"
            "\"close_price\":%g,%s"
            "\"sl\":%s,%s"
            "\"tp\":%s,%s"
            "\"commission\":%g,%s"
            "\"swap\":%g,%s"
            "\"profit\":%g,%s"
            "\"balance\":%g,%s"
            "\"comment\":\"%s\",%s"
            "\"magic\":%d%s"
            "}%s",
            "\n",
            OrderTicket(), "\n",
            EscapeJson(OrderSymbol()), "\n",
            OrderTypeDescription(OrderType()), "\n",
            OrderLots(), "\n",
            TimeToStr(OrderOpenTime()), "\n",
            TimeToStr(OrderCloseTime()), "\n",
            OrderOpenPrice(), "\n",
            OrderClosePrice(), "\n",
            (OrderStopLoss() == 0 ? "null" : StringFormat("%g", OrderStopLoss())), "\n",
            (OrderTakeProfit() == 0 ? "null" : StringFormat("%g", OrderTakeProfit())), "\n",
            OrderCommission(), "\n",
            OrderSwap(), "\n",
            OrderProfit(), "\n",
            AccountBalance(), "\n",
            EscapeJson(OrderComment()), "\n",
            OrderMagicNumber(),
            "\n",
            comma
        );
    }
    json += "]";
    return json;
}

//+------------------------------------------------------------------+
//| 构建 CSV 数据                                                    |
//+------------------------------------------------------------------+
string BuildOrdersCsv(int total)
{
    string csv = "Ticket,Open Time,Close Time,Symbol,Type,Volume,Open Price,Close Price,SL,TP,Commission,Swap,Profit,Balance,Comment\n";
    for(int i = 0; i < total; i++)
    {
        if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
        if(OrderCloseTime() == 0) continue;

        csv += StringFormat("%d,%s,%s,%s,%s,%g,%g,%g,%s,%s,%g,%g,%g,%g,\"%s\"\n",
            OrderTicket(),
            TimeToStr(OrderOpenTime()),
            TimeToStr(OrderCloseTime()),
            OrderSymbol(),
            OrderTypeDescription(OrderType()),
            OrderLots(),
            OrderOpenPrice(),
            OrderClosePrice(),
            (OrderStopLoss() == 0 ? "" : StringFormat("%g", OrderStopLoss())),
            (OrderTakeProfit() == 0 ? "" : StringFormat("%g", OrderTakeProfit())),
            OrderCommission(),
            OrderSwap(),
            OrderProfit(),
            AccountBalance(),
            OrderComment()
        );
    }
    return csv;
}

//+------------------------------------------------------------------+
//| HTTP 推送到 Flask 服务器                                          |
//+------------------------------------------------------------------+
bool PushToServer(string jsonData)
{
    string url = FlaskURL + "/import/api/mql4_push";

    // 准备 headers
    string headers = "Content-Type: application/json\r\n";

    // 准备 POST 数据（string → char[]）
    uchar data[];
    StringToCharArray(jsonData, data, 0, StringLen(jsonData));
    ArrayResize(data, StringLen(jsonData)); // 去掉结尾null

    // 发送请求
    uchar result[];
    string resultHeaders;
    int timeout = 15000; // 15秒

    int res = WebRequest("POST", url, headers, timeout, data, result, resultHeaders);

    if(res == -1)
    {
        int err = GetLastError();
        Print("WebRequest 错误 #", err, " — ", ErrorDescription(err));
        if(err == 4060)
            Print("请添加 '", url, "' 到 MT4 工具→选项→EA交易→允许WebRequest列表");
        return false;
    }

    // 解析返回内容
    string response = CharArrayToString(result);
    Print("服务器响应: ", response, " (HTTP ", res, ")");
    return (res == 200);
}

//+------------------------------------------------------------------+
//| 导出 CSV 到 MT4 本地目录                                          |
//+------------------------------------------------------------------+
bool ExportCsvLocal(string csvData)
{
    int handle = FileOpen(ExportFile, FILE_WRITE|FILE_CSV|FILE_COMMON, ",");
    if(handle == INVALID_HANDLE)
    {
        Print("文件打开失败 #", GetLastError());
        return false;
    }

    // 逐行写入
    string lines[];
    int count = StringSplit(csvData, '\n', lines);
    for(int i = 0; i < count; i++)
    {
        if(StringLen(lines[i]) > 0)
            FileWrite(handle, lines[i]);
    }

    FileClose(handle);
    return true;
}

//+------------------------------------------------------------------+
//| 辅助函数                                                          |
//+------------------------------------------------------------------+
string OrderTypeDescription(int type)
{
    switch(type)
    {
        case OP_BUY:       return "buy";
        case OP_SELL:      return "sell";
        case OP_BUYLIMIT:  return "buy";
        case OP_SELLLIMIT: return "sell";
        case OP_BUYSTOP:   return "buy";
        case OP_SELLSTOP:  return "sell";
        default:           return "unknown";
    }
}

string EscapeJson(string str)
{
    // JSON 字符串转义
    str = StringReplace(str, "\\", "\\\\");
    str = StringReplace(str, "\"", "\\\"");
    str = StringReplace(str, "\n", "\\n");
    str = StringReplace(str, "\r", "\\r");
    str = StringReplace(str, "\t", "\\t");
    return str;
}

//+------------------------------------------------------------------+
//| 错误码描述                                                        |
//+------------------------------------------------------------------+
string ErrorDescription(int err)
{
    switch(err)
    {
        case 4060: return "WebRequest 未允许 — 请在 MT4 工具→选项→EA交易中添加服务器地址";
        case 4062: return "连接超时 — 请检查 Flask 是否运行";
        case 4063: return "域名解析失败";
        default:   return StringFormat("未知错误 #%d", err);
    }
}
//+------------------------------------------------------------------+
