//+------------------------------------------------------------------+
//|                                             AccountInfo.mq4       |
//| 获取MT4账户信息并推送到复盘系统                                    |
//| 使用方式: 编译后拖拽到任意图表运行一次即可                          |
//+------------------------------------------------------------------+
#property strict
#property script_show_inputs

// ---- 输入参数 ----
input string FlaskURL   = "http://127.0.0.1:5000";  // Flask 服务器地址
input bool   ShowMsgBox = true;                      // 是否显示信息弹窗

//+------------------------------------------------------------------+
//| 程序入口                                                          |
//+------------------------------------------------------------------+
void OnStart()
{
    // 收集账户信息
    string infoJson = BuildAccountJson();

    // 本地显示
    if(ShowMsgBox)
    {
        string info = "";
        info += "📊 MT4 账户信息\n\n";
        info += StringFormat("账号:     %d\n", AccountNumber());
        info += StringFormat("名称:     %s\n", AccountName());
        info += StringFormat("公司:     %s\n", AccountCompany());
        info += StringFormat("服务器:   %s\n", AccountServer());
        info += StringFormat("币种:     %s\n", AccountCurrency());
        info += StringFormat("杠杆:     1:%d\n", AccountLeverage());
        info += StringFormat("余额:     %.2f\n", AccountBalance());
        info += StringFormat("净值:     %.2f\n", AccountEquity());
        info += StringFormat("可用保证金: %.2f\n", AccountFreeMargin());
        info += StringFormat("已用保证金: %.2f\n", AccountMargin());
        info += StringFormat("浮动盈亏: %.2f", AccountProfit());
        MessageBox(info, "📊 MT4 账户信息", MB_ICONINFORMATION);
    }

    // 推送信息到服务器
    string url = FlaskURL + "/import/api/mql4_push_account";
    string headers = "Content-Type: application/json\r\n";

    uchar data[];
    StringToCharArray(infoJson, data, 0, StringLen(infoJson));
    ArrayResize(data, StringLen(infoJson));

    uchar result[];
    string resultHeaders;

    int res = WebRequest("POST", url, headers, 10000, data, result, resultHeaders);

    if(res == 200)
    {
        Print("账户信息推送成功");
    }
    else
    {
        int err = GetLastError();
        Print("推送失败 #", err);
        if(err == 4060)
            Print("请添加 '", FlaskURL, "' 到 MT4 工具→选项→EA交易→允许WebRequest列表");
    }
}

//+------------------------------------------------------------------+
//| 构建账户信息 JSON                                                 |
//+------------------------------------------------------------------+
string BuildAccountJson()
{
    return StringFormat(
        "{"
        "\"number\":%d,"
        "\"name\":\"%s\","
        "\"company\":\"%s\","
        "\"server\":\"%s\","
        "\"currency\":\"%s\","
        "\"leverage\":%d,"
        "\"balance\":%.2f,"
        "\"equity\":%.2f,"
        "\"free_margin\":%.2f,"
        "\"margin\":%.2f,"
        "\"profit\":%.2f,"
        "\"is_demo\":%s,"
        "\"broker\":\"%s\","
        "\"terminal\":\"%s\","
        "\"timestamp\":\"%s\""
        "}",
        AccountNumber(),
        EscapeJson(AccountName()),
        EscapeJson(AccountCompany()),
        EscapeJson(AccountServer()),
        AccountCurrency(),
        AccountLeverage(),
        AccountBalance(),
        AccountEquity(),
        AccountFreeMargin(),
        AccountMargin(),
        AccountProfit(),
        IsDemo() ? "true" : "false",
        EscapeJson(TerminalInfoString(TERMINAL_COMPANY)),
        EscapeJson(TerminalInfoString(TERMINAL_NAME)),
        TimeToStr(TimeCurrent())
    );
}

//+------------------------------------------------------------------+
//| 辅助函数                                                          |
//+------------------------------------------------------------------+
string EscapeJson(string str)
{
    str = StringReplace(str, "\\", "\\\\");
    str = StringReplace(str, "\"", "\\\"");
    str = StringReplace(str, "\n", "\\n");
    str = StringReplace(str, "\r", "\\r");
    return str;
}

bool IsDemo()
{
    // MT4 没有直接检测模拟盘的函数，通过公司名/账号特征判断
    string server = AccountServer();
    string company = AccountCompany();
    // 大多数模拟盘服务器包含 "demo" 或 "practice"
    StringToLower(server);
    StringToLower(company);
    return (StringFind(server, "demo") >= 0 || StringFind(company, "demo") >= 0);
}
//+------------------------------------------------------------------+
