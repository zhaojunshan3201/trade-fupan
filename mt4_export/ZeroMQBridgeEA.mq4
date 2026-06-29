//+------------------------------------------------------------------+
//|                                           ZeroMQBridgeEA.mq4      |
//| Publishes MT4 account and closed orders to local ZeroMQ bridge.   |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <Zmq/Zmq.mqh>

input int PublishPort = 5555;
input int AccountIntervalSeconds = 5;
input int OrdersIntervalSeconds = 30;

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

string Mt4Time(datetime value)
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
   string payload = "{";
   payload += "\"type\":\"ACCOUNT\",";
   payload += "\"number\":" + IntegerToString(AccountNumber()) + ",";
   payload += "\"name\":" + JsonString(AccountName()) + ",";
   payload += "\"company\":" + JsonString(AccountCompany()) + ",";
   payload += "\"server\":" + JsonString(AccountServer()) + ",";
   payload += "\"currency\":" + JsonString(AccountCurrency()) + ",";
   payload += "\"leverage\":" + IntegerToString(AccountLeverage()) + ",";
   payload += "\"balance\":" + DoubleToString(AccountBalance(), 2) + ",";
   payload += "\"equity\":" + DoubleToString(AccountEquity(), 2) + ",";
   payload += "\"free_margin\":" + DoubleToString(AccountFreeMargin(), 2) + ",";
   payload += "\"margin\":" + DoubleToString(AccountMargin(), 2) + ",";
   payload += "\"profit\":" + DoubleToString(AccountProfit(), 2) + ",";
   payload += "\"is_demo\":" + (IsDemo() ? "true" : "false");
   payload += "}";

   Publish("ACCOUNT", payload);
}

string OrderTypeText(int orderType)
{
   if(orderType == OP_BUY)
      return "buy";
   if(orderType == OP_SELL)
      return "sell";
   if(orderType == OP_BUYLIMIT)
      return "buy limit";
   if(orderType == OP_SELLLIMIT)
      return "sell limit";
   if(orderType == OP_BUYSTOP)
      return "buy stop";
   if(orderType == OP_SELLSTOP)
      return "sell stop";
   return IntegerToString(orderType);
}

void PublishOrder()
{
   string payload = "{";
   payload += "\"ticket\":" + IntegerToString(OrderTicket()) + ",";
   payload += "\"symbol\":" + JsonString(OrderSymbol()) + ",";
   payload += "\"Type\":" + JsonString(OrderTypeText(OrderType())) + ",";
   payload += "\"volume\":" + DoubleToString(OrderLots(), 2) + ",";
   payload += "\"open_price\":" + DoubleToString(OrderOpenPrice(), Digits) + ",";
   payload += "\"close_price\":" + DoubleToString(OrderClosePrice(), Digits) + ",";
   payload += "\"open_time\":" + JsonString(Mt4Time(OrderOpenTime())) + ",";
   payload += "\"close_time\":" + JsonString(Mt4Time(OrderCloseTime())) + ",";
   payload += "\"profit\":" + DoubleToString(OrderProfit(), 2) + ",";
   payload += "\"sl\":" + DoubleToString(OrderStopLoss(), Digits) + ",";
   payload += "\"tp\":" + DoubleToString(OrderTakeProfit(), Digits) + ",";
   payload += "\"commission\":" + DoubleToString(OrderCommission(), 2) + ",";
   payload += "\"swap\":" + DoubleToString(OrderSwap(), 2) + ",";
   payload += "\"comment\":" + JsonString(OrderComment()) + ",";
   payload += "\"magic\":" + IntegerToString(OrderMagicNumber()) + ",";
   payload += "\"account_number\":" + IntegerToString(AccountNumber());
   payload += "}";

   Publish("ORDER", payload);
}

void PublishClosedOrders()
{
   int total = OrdersHistoryTotal();
   for(int i = 0; i < total; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
         continue;

      if(OrderCloseTime() <= 0)
         continue;

      int type = OrderType();
      if(type != OP_BUY && type != OP_SELL)
         continue;

      PublishOrder();
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
   Print("ZeroMQBridgeEA started at ", address);
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

   Print("ZeroMQBridgeEA stopped.");
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
      PublishClosedOrders();
      g_lastOrdersPublish = now;
   }
}

void OnTimer()
{
   OnTick();
}
