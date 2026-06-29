//+------------------------------------------------------------------+
//|                                           ZeroMQBridgeEA.mq5      |
//| Publishes MT5 account and closed deals to local ZeroMQ bridge.    |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <Zmq/Zmq.mqh>

input int PublishPort = 5556;
input int AccountIntervalSeconds = 5;
input int OrdersIntervalSeconds = 30;
input int HistoryDaysBack = 7;

Context *g_context = NULL;
Socket *g_publisher = NULL;
datetime g_lastAccountPublish = 0;
datetime g_lastOrdersPublish = 0;

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   return value;
}

string JsonString(string value)
{
   return "\"" + JsonEscape(value) + "\"";
}

string Mt5Time(datetime value)
{
   if(value <= 0)
      return "";
   return TimeToString(value, TIME_DATE | TIME_SECONDS);
}

bool Publish(string topic, string payload)
{
   if(g_publisher == NULL)
      return false;

   if(!g_publisher.sendMore(topic))
   {
      Print("ZeroMQ topic send failed: ", Zmq::errorMessage());
      return false;
   }

   if(!g_publisher.send(payload))
   {
      Print("ZeroMQ payload send failed: ", Zmq::errorMessage());
      return false;
   }

   return true;
}

void PublishAccount()
{
   long tradeMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   string payload = "{";
   payload += "\"type\":\"ACCOUNT\",";
   payload += "\"number\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ",";
   payload += "\"name\":" + JsonString(AccountInfoString(ACCOUNT_NAME)) + ",";
   payload += "\"company\":" + JsonString(AccountInfoString(ACCOUNT_COMPANY)) + ",";
   payload += "\"server\":" + JsonString(AccountInfoString(ACCOUNT_SERVER)) + ",";
   payload += "\"currency\":" + JsonString(AccountInfoString(ACCOUNT_CURRENCY)) + ",";
   payload += "\"leverage\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
   payload += "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   payload += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   payload += "\"free_margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
   payload += "\"margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
   payload += "\"profit\":" + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
   payload += "\"is_demo\":" + (tradeMode == ACCOUNT_TRADE_MODE_DEMO ? "true" : "false");
   payload += "}";

   Publish("ACCOUNT", payload);
}

string DealTypeText(long dealType)
{
   if(dealType == DEAL_TYPE_BUY)
      return "buy";
   if(dealType == DEAL_TYPE_SELL)
      return "sell";
   return IntegerToString(dealType);
}

void PublishDeal(ulong ticket)
{
   string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   ulong orderTicket = (ulong)HistoryDealGetInteger(ticket, DEAL_ORDER);
   datetime closeTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
   datetime openTime = 0;
   double openPrice = HistoryDealGetDouble(ticket, DEAL_PRICE);
   double sl = 0.0;
   double tp = 0.0;

   if(orderTicket > 0 && HistoryOrderSelect(orderTicket))
   {
      openTime = (datetime)HistoryOrderGetInteger(orderTicket, ORDER_TIME_SETUP);
      openPrice = HistoryOrderGetDouble(orderTicket, ORDER_PRICE_OPEN);
      sl = HistoryOrderGetDouble(orderTicket, ORDER_SL);
      tp = HistoryOrderGetDouble(orderTicket, ORDER_TP);
   }

   string payload = "{";
   payload += "\"type\":\"DEAL\",";
   payload += "\"ticket\":" + IntegerToString(ticket) + ",";
   payload += "\"symbol\":" + JsonString(symbol) + ",";
   payload += "\"Type\":" + JsonString(DealTypeText(HistoryDealGetInteger(ticket, DEAL_TYPE))) + ",";
   payload += "\"volume\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_VOLUME), 2) + ",";
   payload += "\"open_price\":" + DoubleToString(openPrice, digits) + ",";
   payload += "\"close_price\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PRICE), digits) + ",";
   payload += "\"open_time\":" + JsonString(Mt5Time(openTime)) + ",";
   payload += "\"close_time\":" + JsonString(Mt5Time(closeTime)) + ",";
   payload += "\"profit\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PROFIT), 2) + ",";
   payload += "\"sl\":" + DoubleToString(sl, digits) + ",";
   payload += "\"tp\":" + DoubleToString(tp, digits) + ",";
   payload += "\"commission\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_COMMISSION), 2) + ",";
   payload += "\"swap\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_SWAP), 2) + ",";
   payload += "\"comment\":" + JsonString(HistoryDealGetString(ticket, DEAL_COMMENT)) + ",";
   payload += "\"magic\":" + IntegerToString(HistoryDealGetInteger(ticket, DEAL_MAGIC)) + ",";
   payload += "\"account_number\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   payload += "}";

   Publish("DEAL", payload);
}

void PublishClosedDeals()
{
   datetime toTime = TimeCurrent();
   datetime fromTime = toTime - HistoryDaysBack * 86400;

   if(!HistorySelect(fromTime, toTime))
      return;

   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0)
         continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT)
         continue;

      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL)
         continue;

      PublishDeal(ticket);
   }
}

int OnInit()
{
   string address = "tcp://*:" + IntegerToString(PublishPort);

   g_context = new Context();
   g_publisher = new Socket(g_context, ZMQ_PUB);

   if(!g_publisher.bind(address))
   {
      Print("ZeroMQ bind failed: ", address, " error=", Zmq::errorMessage());
      return INIT_FAILED;
   }

   EventSetTimer(1);
   Print("MT5 ZeroMQBridgeEA started at ", address);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();

   if(g_publisher != NULL)
   {
      delete g_publisher;
      g_publisher = NULL;
   }

   if(g_context != NULL)
   {
      delete g_context;
      g_context = NULL;
   }

   Print("MT5 ZeroMQBridgeEA stopped.");
}

void OnTick()
{
   datetime now = TimeCurrent();

   if(now - g_lastAccountPublish >= AccountIntervalSeconds)
   {
      PublishAccount();
      g_lastAccountPublish = now;
   }

   if(now - g_lastOrdersPublish >= OrdersIntervalSeconds)
   {
      PublishClosedDeals();
      g_lastOrdersPublish = now;
   }
}

void OnTimer()
{
   OnTick();
}
