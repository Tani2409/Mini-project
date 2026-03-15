//+------------------------------------------------------------------+
//|                              ThreeCandlePattern_EA_v4.mq5        |
//|       Three-Candle Pattern EA — Version 4.5 (Trail Fix)        |
//|                                                                  |
//|  KEY CHANGES v4.5 from v4.4:                                     |
//|  1. FIX: Break-even & trailing stop now work independently       |
//|     of partial close (were gated behind partialClosed flag)      |
//|  2. BE triggers at InpBETriggerRR (R:R reached) instead of       |
//|     only after partial close                                     |
//|  3. Trailing stop activates after profit threshold, not after    |
//|     partial close only                                           |
//+------------------------------------------------------------------+
#property copyright "Three Candle Pattern EA v4 — Pro"
#property version   "4.50"
#property strict
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//=== Input Parameters ====================================================

input group "=== Risk Management ==="
input double   InpRiskPercent          = 0.5;     // Risk Per Trade (% of Equity) — 0 = fixed lot
input double   InpFixedLotSize        = 0.01;    // Fixed Lot Size (if RiskPercent = 0)
input double   InpMaxDailyDrawdownPct = 3.0;     // Max Daily Drawdown (% of Balance) — 0 = off
input double   InpMaxTotalDrawdownPct = 10.0;    // Max Total Drawdown (% of Balance) — 0 = off
input int      InpMaxPositions        = 1;       // Max Open Positions — 0 = unlimited
input int      InpMaxDailyLosses      = 5;       // Max Daily Losses — 0 = unlimited
input int      InpCooldownBars        = 8;       // Cooldown Bars After Loss — 0 = off

input group "=== Trading Sessions ==="
input bool     InpUseLondonSession    = true;    // Trade London Session (07:00-11:00 UTC)
input bool     InpUseNYSession        = true;    // Trade New York Session (12:00-16:00 UTC)
input bool     InpUseAsianSession     = false;   // Trade Asian Session (00:00-03:00 UTC)
input bool     InpUseCustomHours      = false;   // Use Custom Hours Instead
input int      InpStartHour           = 7;       // Custom Start Hour (Server Time)
input int      InpEndHour             = 16;      // Custom End Hour (Server Time)
input int      InpSessionWarmupMin    = 30;      // Skip First N Minutes of Session Start
input bool     InpCloseEndOfDay       = false;   // Close All Positions at End of Day
input int      InpEODHour             = 20;      // End of Day Hour (Server Time)

input group "=== Entry Patterns ==="
input bool     InpUseThreeCandle      = false;   // Use Three-Candle Reversal Pattern (disabled: low WR)
input bool     InpUseEngulfing        = true;    // Use Engulfing Pattern (best WR ~41%)
input bool     InpUsePinBar           = false;   // Use Pin Bar Pattern (disabled: 22-35% WR)
input double   InpPinBarWickRatio     = 2.0;     // Pin Bar: Min Wick/Body Ratio
input double   InpMinCandleBodyPips   = 0.0;     // Min Entry Candle Body (Pips) — 0 = off
input double   InpMinBodyRangeRatio   = 0.4;     // Min Body/Range Ratio (candle quality)
input double   InpEngulfMinBodyRatio  = 1.5;     // Engulfing: Entry body must be > prev body x this

input group "=== Entry Indicators ==="
input int      InpFastEMAPeriod       = 10;      // Fast EMA Period (M5)
input int      InpSlowEMAPeriod       = 21;      // Slow EMA Period (M5) — EMA crossover
input bool     InpUseEMACrossover     = true;    // Require EMA Crossover (Fast vs Slow)
input int      InpTrendEMAPeriod      = 50;      // Trend EMA Period (H1) — 0 = off
input int      InpM15EMAPeriod        = 20;      // M15 Structure EMA — 0 = off
input bool     InpUseTrendFilter      = true;    // Use H1 Trend Filter
input bool     InpUseM15Confluence    = true;    // Use M15 Structure Confirmation

input group "=== Momentum & Trend Filters ==="
input int      InpATRPeriod           = 14;      // ATR Period (M5)
input int      InpRSIPeriod           = 14;      // RSI Period (M5) — 0 = off
input bool     InpUseRSIFilter        = true;    // Use RSI Filter
input double   InpRSIOverbought       = 70.0;    // RSI Overbought Level (skip Buy above)
input double   InpRSIOversold         = 30.0;    // RSI Oversold Level (skip Sell below)
input int      InpMACDFast            = 12;      // MACD Fast Period — 0 = off
input int      InpMACDSlow            = 26;      // MACD Slow Period
input int      InpMACDSignal          = 9;       // MACD Signal Period
input bool     InpUseMACDFilter       = false;   // Use MACD Momentum Confirmation (disabled: causes late entries)
input int      InpADXPeriod           = 14;      // ADX Period — 0 = off
input bool     InpUseADXFilter        = true;    // Use ADX Trend Strength Filter
input double   InpADXMinTrend         = 20.0;    // ADX Min Value for Trend Confirmation
input double   InpADXMaxChop          = 50.0;    // ADX Max Value (avoid overextended trends)

input group "=== Volume Filter ==="
input bool     InpUseVolumeFilter     = true;    // Use Volume Spike Filter (filters low-quality entries)
input double   InpVolumeMultiplier    = 1.2;     // Volume Must Be > Avg x This Multiplier
input int      InpVolumePeriod        = 20;      // Volume Average Period

input group "=== Spread Filter ==="
input double   InpMaxSpreadPips       = 0.0;     // Max Spread (Pips) — 0 = off

input group "=== Stop Loss ==="
input int      InpSLBufferTicks       = 5;       // SL Buffer (Ticks beyond swing/candle)
input double   InpMinSL_ATRMult       = 1.0;     // Min SL = ATR x Mult — 0 = off
input int      InpMinSLPoints         = 50;      // Minimum SL Distance (Points) — safety net
input double   InpMaxSL_ATRMult       = 2.0;     // Max SL = ATR x Mult — caps catastrophic losses
input int      InpSwingLookback       = 7;       // Swing High/Low Lookback Bars for SL
input bool     InpUseSwingSL          = true;    // Use Swing-Based SL (vs candle-based)

input group "=== Take Profit ==="
input double   InpTPMultiplier        = 2.5;     // TP Multiplier (x SL distance) — increased for better R:R
input int      InpFixedTPTicks        = 0;       // Fixed TP (Ticks) — 0 = use multiplier
input double   InpMinRRRatio          = 1.5;     // Min R:R Ratio to Enter (0 = off)

input group "=== Partial Close ==="
input bool     InpUsePartialClose     = false;   // Enable Partial Close (disabled: preserves full R:R)
input double   InpPartialClosePercent = 50.0;    // % of Position to Close
input double   InpPartialCloseRR      = 1.0;     // Close Partial at R:R (e.g. 1.0 = 1:1)

input group "=== Break-Even ==="
input bool     InpUseBreakEven        = true;    // Enable Break-Even
input int      InpBEPlusTicks         = 2;       // BE Lock-in (Ticks above entry)
input double   InpBETriggerRR         = 1.0;     // Move to BE when price reaches this R:R (0 = after partial close only)

input group "=== Trailing Stop ==="
input bool     InpUseTrailingStop     = true;    // Enable Trailing Stop
input double   InpTrailATRMult        = 1.5;     // Trail Distance = ATR x Mult
input int      InpTrailMinProfitTicks = 30;      // Start Trail After (Ticks in profit)
input bool     InpUseSwingTrail       = true;    // Use Swing-Based Trailing (smarter)
input int      InpSwingTrailBars      = 5;       // Swing Trail Lookback Bars

input group "=== EA Settings ==="
input int      InpMagicNumber         = 100004;  // Magic Number
input bool     InpShowDashboard       = true;    // Show Dashboard on Chart

//=== Global Variables ====================================================
CTrade         trade;
int            fastEmaHandle, slowEmaHandle;
int            trendEmaHandle, m15EmaHandle;
int            atrHandle, rsiHandle;
int            macdHandle, adxHandle;
datetime       lastBarTime;
int            dailyLossCount;
int            barsSinceLastLoss;
datetime       currentDay;
double         dayStartBalance;
double         peakBalance;
int            totalTradesDay;
int            totalWinsDay;

//--- Partial close tracking
struct PartialCloseInfo
{
   ulong    ticket;
   bool     partialClosed;
   bool     movedToBE;
   double   originalSL;
   double   originalTP;
   double   entryPrice;
};
PartialCloseInfo partialInfo[];

//+------------------------------------------------------------------+
//| Detect the correct filling mode for the broker                   |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING DetectFillingMode()
{
   long fillPolicy = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fillPolicy & SYMBOL_FILLING_FOK) != 0)
      return ORDER_FILLING_FOK;
   if((fillPolicy & SYMBOL_FILLING_IOC) != 0)
      return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validate inputs
   if(InpRiskPercent < 0)
   {  Alert("Risk percent must be >= 0"); return(INIT_PARAMETERS_INCORRECT); }
   if(InpFixedLotSize <= 0 && InpRiskPercent <= 0)
   {  Alert("Either RiskPercent or FixedLotSize must be > 0"); return(INIT_PARAMETERS_INCORRECT); }
   if(InpFastEMAPeriod < 1)
   {  Alert("Fast EMA period must be >= 1"); return(INIT_PARAMETERS_INCORRECT); }

   //--- Setup trade object
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(DetectFillingMode());

   //--- M5 Fast EMA
   fastEmaHandle = iMA(_Symbol, PERIOD_M5, InpFastEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(fastEmaHandle == INVALID_HANDLE)
   {  Alert("Failed M5 Fast EMA. Err: ", GetLastError()); return(INIT_FAILED); }

   //--- M5 Slow EMA
   slowEmaHandle = INVALID_HANDLE;
   if(InpSlowEMAPeriod > 0)
   {
      slowEmaHandle = iMA(_Symbol, PERIOD_M5, InpSlowEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(slowEmaHandle == INVALID_HANDLE)
      {  Alert("Failed M5 Slow EMA. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- H1 Trend EMA
   trendEmaHandle = INVALID_HANDLE;
   if(InpUseTrendFilter && InpTrendEMAPeriod > 0)
   {
      trendEmaHandle = iMA(_Symbol, PERIOD_H1, InpTrendEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(trendEmaHandle == INVALID_HANDLE)
      {  Alert("Failed H1 EMA. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- M15 Structure EMA
   m15EmaHandle = INVALID_HANDLE;
   if(InpUseM15Confluence && InpM15EMAPeriod > 0)
   {
      m15EmaHandle = iMA(_Symbol, PERIOD_M15, InpM15EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if(m15EmaHandle == INVALID_HANDLE)
      {  Alert("Failed M15 EMA. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- ATR
   atrHandle = INVALID_HANDLE;
   if(InpATRPeriod > 0)
   {
      atrHandle = iATR(_Symbol, PERIOD_M5, InpATRPeriod);
      if(atrHandle == INVALID_HANDLE)
      {  Alert("Failed ATR. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- RSI
   rsiHandle = INVALID_HANDLE;
   if(InpUseRSIFilter && InpRSIPeriod > 0)
   {
      rsiHandle = iRSI(_Symbol, PERIOD_M5, InpRSIPeriod, PRICE_CLOSE);
      if(rsiHandle == INVALID_HANDLE)
      {  Alert("Failed RSI. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- MACD
   macdHandle = INVALID_HANDLE;
   if(InpUseMACDFilter && InpMACDFast > 0)
   {
      macdHandle = iMACD(_Symbol, PERIOD_M5, InpMACDFast, InpMACDSlow, InpMACDSignal, PRICE_CLOSE);
      if(macdHandle == INVALID_HANDLE)
      {  Alert("Failed MACD. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- ADX
   adxHandle = INVALID_HANDLE;
   if(InpUseADXFilter && InpADXPeriod > 0)
   {
      adxHandle = iADX(_Symbol, PERIOD_M5, InpADXPeriod);
      if(adxHandle == INVALID_HANDLE)
      {  Alert("Failed ADX. Err: ", GetLastError()); return(INIT_FAILED); }
   }

   //--- Initialize tracking variables
   lastBarTime       = 0;
   dailyLossCount    = 0;
   barsSinceLastLoss = 999;
   currentDay        = 0;
   dayStartBalance   = AccountInfoDouble(ACCOUNT_BALANCE);
   peakBalance       = AccountInfoDouble(ACCOUNT_BALANCE);
   totalTradesDay    = 0;
   totalWinsDay      = 0;
   ArrayResize(partialInfo, 0);

   Print("=== ThreeCandlePattern EA v4.5 PRO Initialized ===");
   Print("Symbol: ", _Symbol, " | Risk: ", InpRiskPercent > 0 ?
         DoubleToString(InpRiskPercent, 1) + "%" : DoubleToString(InpFixedLotSize, 2) + " lots");
   Print("Patterns: 3CP=", InpUseThreeCandle ? "ON" : "OFF",
         " | Engulfing=", InpUseEngulfing ? "ON" : "OFF",
         " | PinBar=", InpUsePinBar ? "ON" : "OFF");
   Print("Filters: Trend=", InpUseTrendFilter ? "ON" : "OFF",
         " | M15=", InpUseM15Confluence ? "ON" : "OFF",
         " | RSI=", InpUseRSIFilter ? "ON" : "OFF",
         " | MACD=", InpUseMACDFilter ? "ON" : "OFF",
         " | ADX=", InpUseADXFilter ? "ON" : "OFF",
         " | Volume=", InpUseVolumeFilter ? "ON" : "OFF");
   Print("Filling mode: ", EnumToString(DetectFillingMode()));

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(fastEmaHandle != INVALID_HANDLE)   IndicatorRelease(fastEmaHandle);
   if(slowEmaHandle != INVALID_HANDLE)   IndicatorRelease(slowEmaHandle);
   if(trendEmaHandle != INVALID_HANDLE)  IndicatorRelease(trendEmaHandle);
   if(m15EmaHandle != INVALID_HANDLE)    IndicatorRelease(m15EmaHandle);
   if(atrHandle != INVALID_HANDLE)       IndicatorRelease(atrHandle);
   if(rsiHandle != INVALID_HANDLE)       IndicatorRelease(rsiHandle);
   if(macdHandle != INVALID_HANDLE)      IndicatorRelease(macdHandle);
   if(adxHandle != INVALID_HANDLE)       IndicatorRelease(adxHandle);
   if(InpShowDashboard) ObjectsDeleteAll(0, "EA_DASH_");
}

//+------------------------------------------------------------------+
//| Utility functions                                                |
//+------------------------------------------------------------------+
double GetTickSize()   { return SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE); }
double GetPipValue()
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5)
      return SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
   return SymbolInfoDouble(_Symbol, SYMBOL_POINT);
}

//+------------------------------------------------------------------+
//| Session-aware trading hours check                                |
//+------------------------------------------------------------------+
bool IsWithinTradingHours()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;

   if(InpUseCustomHours)
   {
      if(InpStartHour < InpEndHour)
         return (hour >= InpStartHour && hour < InpEndHour);
      else
         return (hour >= InpStartHour || hour < InpEndHour);
   }

   // Session-based trading
   int minute = dt.min;
   bool inSession = false;
   // London session with warmup
   if(InpUseLondonSession)
   {
      if(hour == 7 && minute >= InpSessionWarmupMin) inSession = true;
      else if(hour > 7 && hour < 11) inSession = true;
   }
   // NY session with warmup
   if(InpUseNYSession)
   {
      if(hour == 12 && minute >= InpSessionWarmupMin) inSession = true;
      else if(hour > 12 && hour < 16) inSession = true;
   }
   // Asian session with warmup
   if(InpUseAsianSession)
   {
      if(hour == 0 && minute >= InpSessionWarmupMin) inSession = true;
      else if(hour > 0 && hour < 3) inSession = true;
   }

   return inSession;
}

//+------------------------------------------------------------------+
//| Check for new M5 bar                                             |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);
   if(currentBarTime == 0) return false;
   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Check and reset daily counters                                   |
//+------------------------------------------------------------------+
void CheckNewDay()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime today = StringToTime(IntegerToString(dt.year) + "." +
                                  IntegerToString(dt.mon) + "." +
                                  IntegerToString(dt.day));
   if(today != currentDay)
   {
      currentDay      = today;
      dailyLossCount  = 0;
      totalTradesDay  = 0;
      totalWinsDay    = 0;
      dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   }
}

//+------------------------------------------------------------------+
//| Count open positions for this EA                                 |
//+------------------------------------------------------------------+
int CountPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Spread filter                                                    |
//+------------------------------------------------------------------+
bool IsSpreadOK()
{
   if(InpMaxSpreadPips <= 0) return true;
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return (spread / GetPipValue() <= InpMaxSpreadPips);
}

//+------------------------------------------------------------------+
//| Candle body quality: body must be significant vs total range      |
//+------------------------------------------------------------------+
bool IsCandleQualityOK(double op, double cl, double hi, double lo)
{
   double body  = MathAbs(cl - op);
   double range = hi - lo;
   if(range <= 0) return false;

   // Min body size in pips
   if(InpMinCandleBodyPips > 0 && body / GetPipValue() < InpMinCandleBodyPips)
      return false;

   // Body/range ratio: filters dojis and indecision candles
   if(InpMinBodyRangeRatio > 0 && body / range < InpMinBodyRangeRatio)
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Get H1 trend direction: +1 bullish, -1 bearish, 0 neutral       |
//+------------------------------------------------------------------+
int GetH1TrendDirection()
{
   if(!InpUseTrendFilter || trendEmaHandle == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(trendEmaHandle, 0, 0, 2, buf) < 2) return 0;
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(price > buf[0]) return +1;
   if(price < buf[0]) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Get M15 structure direction: +1 bullish, -1 bearish, 0 neutral   |
//+------------------------------------------------------------------+
int GetM15Direction()
{
   if(!InpUseM15Confluence || m15EmaHandle == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(m15EmaHandle, 0, 0, 2, buf) < 2) return 0;
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(price > buf[0]) return +1;
   if(price < buf[0]) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Get EMA values (fast and slow)                                   |
//+------------------------------------------------------------------+
bool GetEMAValues(double &fastEma, double &slowEma)
{
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(fastEmaHandle, 0, 0, 3, buf) < 3) return false;
   fastEma = buf[1];

   if(slowEmaHandle != INVALID_HANDLE)
   {
      double buf2[];
      ArraySetAsSeries(buf2, true);
      if(CopyBuffer(slowEmaHandle, 0, 0, 3, buf2) < 3) return false;
      slowEma = buf2[1];
   }
   else
      slowEma = fastEma;

   return true;
}

//+------------------------------------------------------------------+
//| Check EMA crossover alignment                                    |
//| BUY: fastEMA > slowEMA, SELL: fastEMA < slowEMA                  |
//+------------------------------------------------------------------+
int GetEMACrossoverDirection()
{
   if(!InpUseEMACrossover || slowEmaHandle == INVALID_HANDLE) return 0;
   double fastBuf[], slowBuf[];
   ArraySetAsSeries(fastBuf, true);
   ArraySetAsSeries(slowBuf, true);
   if(CopyBuffer(fastEmaHandle, 0, 0, 3, fastBuf) < 3) return 0;
   if(CopyBuffer(slowEmaHandle, 0, 0, 3, slowBuf) < 3) return 0;
   if(fastBuf[1] > slowBuf[1]) return +1; // bullish alignment
   if(fastBuf[1] < slowBuf[1]) return -1; // bearish alignment
   return 0;
}

//+------------------------------------------------------------------+
//| Check EMA slope (momentum direction)                             |
//| Returns +1 if fast EMA rising, -1 if falling, 0 if flat          |
//+------------------------------------------------------------------+
int GetEMASlopeDirection()
{
   double fastBuf[];
   ArraySetAsSeries(fastBuf, true);
   if(CopyBuffer(fastEmaHandle, 0, 0, 4, fastBuf) < 4) return 0;
   // Compare current EMA vs 2 bars ago for smoother slope
   double slope = fastBuf[1] - fastBuf[3];
   double atr = GetATR();
   if(atr <= 0) return 0;
   // Slope must be at least 10% of ATR to be meaningful
   if(slope > atr * 0.1) return +1;  // rising
   if(slope < -atr * 0.1) return -1; // falling
   return 0; // flat
}

//+------------------------------------------------------------------+
//| Get RSI value at bar index 1                                     |
//+------------------------------------------------------------------+
double GetRSI()
{
   if(rsiHandle == INVALID_HANDLE) return 50.0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(rsiHandle, 0, 0, 3, buf) < 3) return 50.0;
   return buf[1];
}

//+------------------------------------------------------------------+
//| Get ATR value at bar index 1                                     |
//+------------------------------------------------------------------+
double GetATR()
{
   if(atrHandle == INVALID_HANDLE) return 0;
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(atrHandle, 0, 0, 3, buf) < 3) return 0;
   return buf[1];
}

//+------------------------------------------------------------------+
//| MACD momentum check: +1 bullish, -1 bearish, 0 neutral          |
//+------------------------------------------------------------------+
int GetMACDSignal()
{
   if(!InpUseMACDFilter || macdHandle == INVALID_HANDLE) return 0;
   double macdLine[], signalLine[], histogram[];
   ArraySetAsSeries(macdLine, true);
   ArraySetAsSeries(signalLine, true);
   ArraySetAsSeries(histogram, true);

   if(CopyBuffer(macdHandle, 0, 0, 3, macdLine) < 3) return 0;
   if(CopyBuffer(macdHandle, 1, 0, 3, signalLine) < 3) return 0;

   // Histogram = MACD - Signal
   double hist1 = macdLine[1] - signalLine[1];
   double hist2 = macdLine[2] - signalLine[2];

   // Bullish: histogram increasing (momentum building)
   if(hist1 > hist2 && macdLine[1] > signalLine[1]) return +1;
   // Bearish: histogram decreasing
   if(hist1 < hist2 && macdLine[1] < signalLine[1]) return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| ADX trend strength check                                         |
//+------------------------------------------------------------------+
bool IsADXTrending(int &direction)
{
   direction = 0;
   if(!InpUseADXFilter || adxHandle == INVALID_HANDLE) return true; // pass if disabled
   double adxBuf[], plusDI[], minusDI[];
   ArraySetAsSeries(adxBuf, true);
   ArraySetAsSeries(plusDI, true);
   ArraySetAsSeries(minusDI, true);

   if(CopyBuffer(adxHandle, 0, 0, 3, adxBuf) < 3) return true;
   if(CopyBuffer(adxHandle, 1, 0, 3, plusDI) < 3) return true;
   if(CopyBuffer(adxHandle, 2, 0, 3, minusDI) < 3) return true;

   double adxValue = adxBuf[1];

   // ADX too low = choppy market, skip
   if(adxValue < InpADXMinTrend) return false;
   // ADX too high = overextended, skip
   if(InpADXMaxChop > 0 && adxValue > InpADXMaxChop) return false;

   // DI direction
   if(plusDI[1] > minusDI[1]) direction = +1;
   else if(minusDI[1] > plusDI[1]) direction = -1;

   return true;
}

//+------------------------------------------------------------------+
//| Volume spike confirmation                                        |
//+------------------------------------------------------------------+
bool IsVolumeConfirmed()
{
   if(!InpUseVolumeFilter) return true;

   long volumes[];
   ArraySetAsSeries(volumes, true);
   int barsNeeded = InpVolumePeriod + 2;
   if(CopyTickVolume(_Symbol, PERIOD_M5, 0, barsNeeded, volumes) < barsNeeded)
      return true; // pass if data unavailable

   long entryVol = volumes[1];

   // Calculate average volume (excluding entry bar)
   double avgVol = 0;
   for(int i = 2; i < barsNeeded; i++)
      avgVol += (double)volumes[i];
   avgVol /= InpVolumePeriod;

   return (entryVol >= avgVol * InpVolumeMultiplier);
}

//+------------------------------------------------------------------+
//| Find swing low for BUY SL placement                              |
//+------------------------------------------------------------------+
double FindSwingLow(int lookback)
{
   double lowest = DBL_MAX;
   for(int i = 1; i <= lookback; i++)
   {
      double low = iLow(_Symbol, PERIOD_M5, i);
      if(low > 0 && low < lowest)
         lowest = low;
   }
   return lowest;
}

//+------------------------------------------------------------------+
//| Find swing high for SELL SL placement                            |
//+------------------------------------------------------------------+
double FindSwingHigh(int lookback)
{
   double highest = 0;
   for(int i = 1; i <= lookback; i++)
   {
      double high = iHigh(_Symbol, PERIOD_M5, i);
      if(high > highest)
         highest = high;
   }
   return highest;
}

//+------------------------------------------------------------------+
//| Dynamic position sizing based on risk %                          |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
{
   if(InpRiskPercent <= 0 || slDistance <= 0)
      return InpFixedLotSize;

   double equity       = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount   = equity * InpRiskPercent / 100.0;
   double tickValue    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize     = GetTickSize();

   if(tickValue <= 0 || tickSize <= 0) return InpFixedLotSize;

   double slTicks      = slDistance / tickSize;
   double lotSize      = riskAmount / (slTicks * tickValue);

   // Normalize to broker constraints
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(lotStep > 0)
      lotSize = MathFloor(lotSize / lotStep) * lotStep;

   lotSize = MathMax(lotSize, minLot);
   lotSize = MathMin(lotSize, maxLot);

   return NormalizeDouble(lotSize, 2);
}

//+------------------------------------------------------------------+
//| Check equity drawdown limits                                     |
//+------------------------------------------------------------------+
bool IsDrawdownOK()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);

   // Update peak balance
   if(balance > peakBalance) peakBalance = balance;

   // Daily drawdown check
   if(InpMaxDailyDrawdownPct > 0 && dayStartBalance > 0)
   {
      double dailyDrawdownPct = (dayStartBalance - equity) / dayStartBalance * 100.0;
      if(dailyDrawdownPct >= InpMaxDailyDrawdownPct)
      {
         Print("DAILY DRAWDOWN LIMIT HIT: ", DoubleToString(dailyDrawdownPct, 2),
               "% >= ", DoubleToString(InpMaxDailyDrawdownPct, 1), "%");
         return false;
      }
   }

   // Total drawdown from peak
   if(InpMaxTotalDrawdownPct > 0 && peakBalance > 0)
   {
      double totalDrawdownPct = (peakBalance - equity) / peakBalance * 100.0;
      if(totalDrawdownPct >= InpMaxTotalDrawdownPct)
      {
         Print("TOTAL DRAWDOWN LIMIT HIT: ", DoubleToString(totalDrawdownPct, 2),
               "% >= ", DoubleToString(InpMaxTotalDrawdownPct, 1), "%");
         return false;
      }
   }

   return true;
}

//+------------------------------------------------------------------+
//| Pattern Detection: Three-Candle Reversal                         |
//| BUY: 2 bearish + 1 bullish closing above highs & EMA            |
//| SELL: 2 bullish + 1 bearish closing below lows & EMA            |
//+------------------------------------------------------------------+
int DetectThreeCandlePattern(double fastEma)
{
   if(!InpUseThreeCandle) return 0;

   double open1 = iOpen(_Symbol, PERIOD_M5, 1), close1 = iClose(_Symbol, PERIOD_M5, 1);
   double high1 = iHigh(_Symbol, PERIOD_M5, 1), low1 = iLow(_Symbol, PERIOD_M5, 1);
   double open2 = iOpen(_Symbol, PERIOD_M5, 2), close2 = iClose(_Symbol, PERIOD_M5, 2);
   double high2 = iHigh(_Symbol, PERIOD_M5, 2);
   double open3 = iOpen(_Symbol, PERIOD_M5, 3), close3 = iClose(_Symbol, PERIOD_M5, 3);
   double high3 = iHigh(_Symbol, PERIOD_M5, 3);
   double low2 = iLow(_Symbol, PERIOD_M5, 2), low3 = iLow(_Symbol, PERIOD_M5, 3);

   if(open1 == 0 || open2 == 0 || open3 == 0) return 0;

   // Get slow EMA for stronger confirmation
   double slowEma = fastEma; // fallback
   if(slowEmaHandle != INVALID_HANDLE)
   {
      double buf[];
      ArraySetAsSeries(buf, true);
      if(CopyBuffer(slowEmaHandle, 0, 0, 3, buf) >= 3)
         slowEma = buf[1];
   }

   // Reversal candle must have strong body relative to range
   double body1 = MathAbs(close1 - open1);
   double range1 = high1 - low1;
   if(range1 <= 0 || body1 / range1 < 0.5) return 0; // stricter quality for 3CP

   // Get ATR for pullback distance check
   double atr = GetATR();
   if(atr <= 0) return 0;

   // BUY: 2 bearish + 1 bullish (pullback-to-EMA reversal)
   bool c3Bear = (close3 < open3);
   bool c2Bear = (close2 < open2);
   bool c1Bull = (close1 > open1);

   if(c3Bear && c2Bear && c1Bull)
   {
      double highPrev = MathMax(high3, high2);
      // Must close above previous highs AND above BOTH EMAs
      if(close1 > highPrev && close1 > fastEma && close1 > slowEma)
      {
         // Pullback check: bearish candles must have come NEAR the EMA (within 1.5x ATR)
         // This ensures the pattern is a pullback-to-support, not a random bounce
         double pullbackLow = MathMin(low2, low3);
         if(pullbackLow > fastEma + atr * 1.5) return 0; // price never pulled back to EMA

         if(IsCandleQualityOK(open1, close1, high1, low1))
            return +1; // BUY signal
      }
   }

   // SELL: 2 bullish + 1 bearish (pullback-to-EMA reversal)
   bool c3Bull = (close3 > open3);
   bool c2Bull = (close2 > open2);
   bool c1Bear = (close1 < open1);

   if(c3Bull && c2Bull && c1Bear)
   {
      double lowPrev = MathMin(low3, low2);
      // Must close below previous lows AND below BOTH EMAs
      if(close1 < lowPrev && close1 < fastEma && close1 < slowEma)
      {
         // Pullback check: bullish candles must have come NEAR the EMA (within 1.5x ATR)
         double pullbackHigh = MathMax(high2, high3);
         if(pullbackHigh < fastEma - atr * 1.5) return 0; // price never pulled back to EMA

         if(IsCandleQualityOK(open1, close1, high1, low1))
            return -1; // SELL signal
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Pattern Detection: Engulfing                                     |
//| Bullish: bearish candle 2 fully engulfed by bullish candle 1     |
//| Bearish: bullish candle 2 fully engulfed by bearish candle 1     |
//+------------------------------------------------------------------+
int DetectEngulfingPattern(double fastEma)
{
   if(!InpUseEngulfing) return 0;

   double open1 = iOpen(_Symbol, PERIOD_M5, 1), close1 = iClose(_Symbol, PERIOD_M5, 1);
   double high1 = iHigh(_Symbol, PERIOD_M5, 1), low1 = iLow(_Symbol, PERIOD_M5, 1);
   double open2 = iOpen(_Symbol, PERIOD_M5, 2), close2 = iClose(_Symbol, PERIOD_M5, 2);
   double open3 = iOpen(_Symbol, PERIOD_M5, 3), close3 = iClose(_Symbol, PERIOD_M5, 3);

   if(open1 == 0 || open2 == 0 || open3 == 0) return 0;

   double body1 = MathAbs(close1 - open1);
   double body2 = MathAbs(close2 - open2);

   // Bullish Engulfing — tightened criteria
   if(close2 < open2 && close1 > open1) // bar2 bearish, bar1 bullish
   {
      if(open1 <= close2 && close1 >= open2) // bar1 body engulfs bar2 body
      {
         // Entry body must be significantly larger than previous
         if(body2 > 0 && body1 < body2 * InpEngulfMinBodyRatio) return 0;
         // Require context: bar3 should also be bearish (confirms reversal after downmove)
         if(close3 >= open3) return 0; // bar3 not bearish = weak setup
         if(close1 > fastEma && IsCandleQualityOK(open1, close1, high1, low1))
            return +1;
      }
   }

   // Bearish Engulfing — tightened criteria
   if(close2 > open2 && close1 < open1) // bar2 bullish, bar1 bearish
   {
      if(open1 >= close2 && close1 <= open2) // bar1 body engulfs bar2 body
      {
         // Entry body must be significantly larger than previous
         if(body2 > 0 && body1 < body2 * InpEngulfMinBodyRatio) return 0;
         // Require context: bar3 should also be bullish (confirms reversal after upmove)
         if(close3 <= open3) return 0; // bar3 not bullish = weak setup
         if(close1 < fastEma && IsCandleQualityOK(open1, close1, high1, low1))
            return -1;
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Pattern Detection: Pin Bar (Hammer / Shooting Star)              |
//| Bullish: long lower wick, small body near top                    |
//| Bearish: long upper wick, small body near bottom                 |
//+------------------------------------------------------------------+
int DetectPinBarPattern(double fastEma)
{
   if(!InpUsePinBar) return 0;

   double open1 = iOpen(_Symbol, PERIOD_M5, 1), close1 = iClose(_Symbol, PERIOD_M5, 1);
   double high1 = iHigh(_Symbol, PERIOD_M5, 1), low1 = iLow(_Symbol, PERIOD_M5, 1);

   if(open1 == 0) return 0;

   double body       = MathAbs(close1 - open1);
   double range      = high1 - low1;
   double upperWick  = high1 - MathMax(open1, close1);
   double lowerWick  = MathMin(open1, close1) - low1;
   double atr        = GetATR();

   if(body <= 0 || range <= 0 || atr <= 0) return 0;

   // Pin bar range should be significant (at least 0.5x ATR)
   if(range < atr * 0.5) return 0;

   // Bullish Pin Bar (Hammer): long lower wick near support
   if(lowerWick >= body * InpPinBarWickRatio && upperWick < body)
   {
      // Pin bar low should be near recent swing low (within 1x ATR)
      double swingLow = FindSwingLow(InpSwingLookback);
      if(swingLow > 0 && MathAbs(low1 - swingLow) < atr * 1.0)
      {
         if(close1 > fastEma || MathAbs(close1 - fastEma) / GetPipValue() < 3)
            return +1;
      }
   }

   // Bearish Pin Bar (Shooting Star): long upper wick near resistance
   if(upperWick >= body * InpPinBarWickRatio && lowerWick < body)
   {
      // Pin bar high should be near recent swing high (within 1x ATR)
      double swingHigh = FindSwingHigh(InpSwingLookback);
      if(swingHigh > 0 && MathAbs(high1 - swingHigh) < atr * 1.0)
      {
         if(close1 < fastEma || MathAbs(close1 - fastEma) / GetPipValue() < 3)
            return -1;
      }
   }

   return 0;
}

//+------------------------------------------------------------------+
//| Calculate SL price using swing structure or candle-based          |
//+------------------------------------------------------------------+
double CalculateSLPrice(int direction, double atr, double entryPrice)
{
   double tickSize = GetTickSize();
   double point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double slPrice;

   if(direction > 0) // BUY
   {
      if(InpUseSwingSL)
         slPrice = FindSwingLow(InpSwingLookback) - (InpSLBufferTicks * tickSize);
      else
         slPrice = iLow(_Symbol, PERIOD_M5, 1) - (InpSLBufferTicks * tickSize);

      // ATR minimum SL
      if(atr > 0 && InpMinSL_ATRMult > 0)
      {
         double minSLDist = atr * InpMinSL_ATRMult;
         if((entryPrice - slPrice) < minSLDist)
            slPrice = entryPrice - minSLDist;
      }

      // Absolute minimum SL in points
      if(InpMinSLPoints > 0)
      {
         double minSLDist = InpMinSLPoints * point;
         if((entryPrice - slPrice) < minSLDist)
            slPrice = entryPrice - minSLDist;
      }

      // MAX SL cap — prevent catastrophic losses
      if(atr > 0 && InpMaxSL_ATRMult > 0)
      {
         double maxSLDist = atr * InpMaxSL_ATRMult;
         if((entryPrice - slPrice) > maxSLDist)
            slPrice = entryPrice - maxSLDist;
      }
   }
   else // SELL
   {
      if(InpUseSwingSL)
         slPrice = FindSwingHigh(InpSwingLookback) + (InpSLBufferTicks * tickSize);
      else
         slPrice = iHigh(_Symbol, PERIOD_M5, 1) + (InpSLBufferTicks * tickSize);

      // ATR minimum SL
      if(atr > 0 && InpMinSL_ATRMult > 0)
      {
         double minSLDist = atr * InpMinSL_ATRMult;
         if((slPrice - entryPrice) < minSLDist)
            slPrice = entryPrice + minSLDist;
      }

      // Absolute minimum SL in points
      if(InpMinSLPoints > 0)
      {
         double minSLDist = InpMinSLPoints * point;
         if((slPrice - entryPrice) < minSLDist)
            slPrice = entryPrice + minSLDist;
      }

      // MAX SL cap — prevent catastrophic losses
      if(atr > 0 && InpMaxSL_ATRMult > 0)
      {
         double maxSLDist = atr * InpMaxSL_ATRMult;
         if((slPrice - entryPrice) > maxSLDist)
            slPrice = entryPrice + maxSLDist;
      }
   }

   return NormalizeDouble(slPrice, _Digits);
}

//+------------------------------------------------------------------+
//| Calculate TP price                                               |
//+------------------------------------------------------------------+
double CalculateTPPrice(int direction, double entryPrice, double slDist)
{
   double tickSize = GetTickSize();
   double tpPrice;

   if(direction > 0) // BUY
   {
      if(InpFixedTPTicks > 0)
         tpPrice = entryPrice + (InpFixedTPTicks * tickSize);
      else
         tpPrice = entryPrice + (slDist * InpTPMultiplier);
   }
   else // SELL
   {
      if(InpFixedTPTicks > 0)
         tpPrice = entryPrice - (InpFixedTPTicks * tickSize);
      else
         tpPrice = entryPrice - (slDist * InpTPMultiplier);
   }

   return NormalizeDouble(tpPrice, _Digits);
}

//+------------------------------------------------------------------+
//| Find partial close info for a ticket                             |
//+------------------------------------------------------------------+
int FindPartialInfo(ulong ticket)
{
   for(int i = 0; i < ArraySize(partialInfo); i++)
      if(partialInfo[i].ticket == ticket) return i;
   return -1;
}

//+------------------------------------------------------------------+
//| Add partial close tracking for a new position                    |
//+------------------------------------------------------------------+
void AddPartialInfo(ulong ticket, double sl, double tp, double entry)
{
   int size = ArraySize(partialInfo);
   ArrayResize(partialInfo, size + 1);
   partialInfo[size].ticket        = ticket;
   partialInfo[size].partialClosed = false;
   partialInfo[size].movedToBE     = false;
   partialInfo[size].originalSL    = sl;
   partialInfo[size].originalTP    = tp;
   partialInfo[size].entryPrice    = entry;
}

//+------------------------------------------------------------------+
//| Clean up closed positions from partialInfo                       |
//+------------------------------------------------------------------+
void CleanPartialInfo()
{
   for(int i = ArraySize(partialInfo) - 1; i >= 0; i--)
   {
      bool found = false;
      for(int j = PositionsTotal() - 1; j >= 0; j--)
      {
         ulong ticket = PositionGetTicket(j);
         if(ticket == partialInfo[i].ticket) { found = true; break; }
      }
      if(!found)
      {
         int last = ArraySize(partialInfo) - 1;
         if(i < last) partialInfo[i] = partialInfo[last];
         ArrayResize(partialInfo, last);
      }
   }
}

//+------------------------------------------------------------------+
//| Find swing low for trailing stop (recent bars)                   |
//+------------------------------------------------------------------+
double FindRecentSwingLow(int bars)
{
   double lowest = DBL_MAX;
   for(int i = 1; i <= bars; i++)
   {
      double low = iLow(_Symbol, PERIOD_M5, i);
      if(low > 0 && low < lowest) lowest = low;
   }
   return lowest;
}

//+------------------------------------------------------------------+
//| Find swing high for trailing stop (recent bars)                  |
//+------------------------------------------------------------------+
double FindRecentSwingHigh(int bars)
{
   double highest = 0;
   for(int i = 1; i <= bars; i++)
   {
      double high = iHigh(_Symbol, PERIOD_M5, i);
      if(high > highest) highest = high;
   }
   return highest;
}

//+------------------------------------------------------------------+
//| Manage open positions: partial close, BE, trailing               |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   double tickSize = GetTickSize();
   if(tickSize == 0) return;
   double atr = GetATR();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      long   posType   = PositionGetInteger(POSITION_TYPE);
      double openPx    = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double volume    = PositionGetDouble(POSITION_VOLUME);
      int idx = FindPartialInfo(ticket);

      //=== PARTIAL CLOSE ===
      if(InpUsePartialClose && idx >= 0 && !partialInfo[idx].partialClosed && volume > 0)
      {
         double slDist = MathAbs(openPx - partialInfo[idx].originalSL);
         double partialTarget;

         if(posType == POSITION_TYPE_BUY)
         {
            partialTarget = openPx + (slDist * InpPartialCloseRR);
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            if(bid >= partialTarget)
            {
               double closeVol = NormalizeDouble(volume * InpPartialClosePercent / 100.0, 2);
               double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
               if(closeVol < minVol) closeVol = minVol;
               if(closeVol >= volume) closeVol = NormalizeDouble(volume - minVol, 2);
               if(closeVol >= minVol)
               {
                  if(trade.PositionClosePartial(ticket, closeVol))
                  {
                     partialInfo[idx].partialClosed = true;
                     Print("Partial close BUY: ", closeVol, " lots @ ", bid);
                  }
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            partialTarget = openPx - (slDist * InpPartialCloseRR);
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            if(ask <= partialTarget)
            {
               double closeVol = NormalizeDouble(volume * InpPartialClosePercent / 100.0, 2);
               double minVol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
               if(closeVol < minVol) closeVol = minVol;
               if(closeVol >= volume) closeVol = NormalizeDouble(volume - minVol, 2);
               if(closeVol >= minVol)
               {
                  if(trade.PositionClosePartial(ticket, closeVol))
                  {
                     partialInfo[idx].partialClosed = true;
                     Print("Partial close SELL: ", closeVol, " lots @ ", ask);
                  }
               }
            }
         }
      }

      //=== BREAK-EVEN ===
      // Can trigger either: (a) after partial close, or (b) when price reaches BETriggerRR
      if(InpUseBreakEven && idx >= 0 && !partialInfo[idx].movedToBE)
      {
         bool triggerBE = partialInfo[idx].partialClosed; // original: after partial close
         
         // NEW: Also trigger BE when price reaches InpBETriggerRR (works without partial close)
         if(!triggerBE && InpBETriggerRR > 0)
         {
            double slDist = MathAbs(openPx - partialInfo[idx].originalSL);
            if(posType == POSITION_TYPE_BUY)
            {
               double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
               if(slDist > 0 && (bid - openPx) >= slDist * InpBETriggerRR)
                  triggerBE = true;
            }
            else if(posType == POSITION_TYPE_SELL)
            {
               double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
               if(slDist > 0 && (openPx - ask) >= slDist * InpBETriggerRR)
                  triggerBE = true;
            }
         }
         
         if(triggerBE)
         {
            if(posType == POSITION_TYPE_BUY)
            {
               double beLevel = NormalizeDouble(openPx + (InpBEPlusTicks * tickSize), _Digits);
               if(currentSL < beLevel)
               {
                  if(trade.PositionModify(ticket, beLevel, currentTP))
                  {
                     partialInfo[idx].movedToBE = true;
                     Print("BUY moved to BE+", InpBEPlusTicks, " ticks");
                  }
               }
            }
            else if(posType == POSITION_TYPE_SELL)
            {
               double beLevel = NormalizeDouble(openPx - (InpBEPlusTicks * tickSize), _Digits);
               if(currentSL > beLevel || currentSL == 0)
               {
                  if(trade.PositionModify(ticket, beLevel, currentTP))
                  {
                     partialInfo[idx].movedToBE = true;
                     Print("SELL moved to BE+", InpBEPlusTicks, " ticks");
                  }
               }
            }
         }
      }

      //=== TRAILING STOP (after BE is locked in) ===
      if(InpUseTrailingStop && idx >= 0 && partialInfo[idx].movedToBE)
      {
         if(posType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double profitTicks = (bid - openPx) / tickSize;
            if(profitTicks >= InpTrailMinProfitTicks)
            {
               double newSL;
               if(InpUseSwingTrail)
               {
                  // Use recent swing low as trail level
                  double swingLow = FindRecentSwingLow(InpSwingTrailBars);
                  double atrTrail = (atr > 0) ? NormalizeDouble(bid - atr * InpTrailATRMult, _Digits) : 0;
                  // Use the higher (tighter) of swing low and ATR trail
                  newSL = MathMax(swingLow, atrTrail);
               }
               else
               {
                  newSL = (atr > 0) ? NormalizeDouble(bid - atr * InpTrailATRMult, _Digits) : currentSL;
               }

               if(newSL > currentSL && newSL < bid)
                  trade.PositionModify(ticket, newSL, currentTP);
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double profitTicks = (openPx - ask) / tickSize;
            if(profitTicks >= InpTrailMinProfitTicks)
            {
               double newSL;
               if(InpUseSwingTrail)
               {
                  double swingHigh = FindRecentSwingHigh(InpSwingTrailBars);
                  double atrTrail = (atr > 0) ? NormalizeDouble(ask + atr * InpTrailATRMult, _Digits) : DBL_MAX;
                  newSL = MathMin(swingHigh, atrTrail);
               }
               else
               {
                  newSL = (atr > 0) ? NormalizeDouble(ask + atr * InpTrailATRMult, _Digits) : currentSL;
               }

               if((newSL < currentSL || currentSL == 0) && newSL > ask)
                  trade.PositionModify(ticket, newSL, currentTP);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Close all positions at end of day                                |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      trade.PositionClose(ticket);
   }
}

//+------------------------------------------------------------------+
//| Track closed trades for daily loss/win count                     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                         const MqlTradeRequest &request,
                         const MqlTradeResult &result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      ulong dealTicket = trans.deal;
      if(dealTicket > 0 && HistoryDealSelect(dealTicket))
      {
         long   dealMagic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
         long   dealEntry = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
         double dealProf  = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);

         if(dealMagic == InpMagicNumber && dealEntry == DEAL_ENTRY_OUT)
         {
            totalTradesDay++;
            if(dealProf < 0)
            {
               dailyLossCount++;
               barsSinceLastLoss = 0;
               Print("Loss #", dailyLossCount, " today | P/L: ", DoubleToString(dealProf, 2));
            }
            else if(dealProf > 0)
            {
               totalWinsDay++;
               Print("Win #", totalWinsDay, " today | P/L: ", DoubleToString(dealProf, 2));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Dashboard display on chart                                       |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   if(!InpShowDashboard) return;

   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dailyPL = equity - dayStartBalance;
   double winRate = totalTradesDay > 0 ? (double)totalWinsDay / totalTradesDay * 100.0 : 0;

   string info = "";
   info += "EA v4 PRO | " + _Symbol + "\n";
   info += "Equity: " + DoubleToString(equity, 2) + " | Bal: " + DoubleToString(balance, 2) + "\n";
   info += "Daily P/L: " + DoubleToString(dailyPL, 2) + "\n";
   info += "Trades: " + IntegerToString(totalTradesDay) + " | Wins: " + IntegerToString(totalWinsDay) +
           " | WR: " + DoubleToString(winRate, 1) + "%\n";
   info += "Losses today: " + IntegerToString(dailyLossCount) + "/" +
           (InpMaxDailyLosses > 0 ? IntegerToString(InpMaxDailyLosses) : "inf") + "\n";
   info += "Positions: " + IntegerToString(CountPositions()) + "/" +
           (InpMaxPositions > 0 ? IntegerToString(InpMaxPositions) : "inf");

   if(ObjectFind(0, "EA_DASH_BG") < 0)
   {
      ObjectCreate(0, "EA_DASH_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_YDISTANCE, 25);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_XSIZE, 300);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_YSIZE, 110);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_BGCOLOR, clrMidnightBlue);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_BORDER_COLOR, clrGold);
      ObjectSetInteger(0, "EA_DASH_BG", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   }
   if(ObjectFind(0, "EA_DASH_TEXT") < 0)
   {
      ObjectCreate(0, "EA_DASH_TEXT", OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, "EA_DASH_TEXT", OBJPROP_XDISTANCE, 15);
      ObjectSetInteger(0, "EA_DASH_TEXT", OBJPROP_YDISTANCE, 30);
      ObjectSetInteger(0, "EA_DASH_TEXT", OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, "EA_DASH_TEXT", OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, "EA_DASH_TEXT", OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, "EA_DASH_TEXT", OBJPROP_FONT, "Consolas");
   }
   ObjectSetString(0, "EA_DASH_TEXT", OBJPROP_TEXT, info);
}

//+------------------------------------------------------------------+
//| Execute trade with all confirmations                             |
//+------------------------------------------------------------------+
bool ExecuteTrade(int direction, string patternName)
{
   double atr     = GetATR();
   double rsi     = GetRSI();
   int    trendH1 = GetH1TrendDirection();
   int    trendM15= GetM15Direction();
   int    macdSig = GetMACDSignal();
   int    emaCross= GetEMACrossoverDirection();
   int    emaSlope= GetEMASlopeDirection();
   int    adxDir  = 0;

   //=== FILTERS ===

   // EMA crossover alignment: fast EMA must be on the right side of slow EMA
   if(InpUseEMACrossover && slowEmaHandle != INVALID_HANDLE)
   {
      if(direction > 0 && emaCross < 0)
      {  Print(patternName, " BUY skip: EMA bearish (fast < slow)"); return false; }
      if(direction < 0 && emaCross > 0)
      {  Print(patternName, " SELL skip: EMA bullish (fast > slow)"); return false; }
   }

   // EMA slope confirmation — DISABLED in v4.4 (too restrictive, causes late entries)
   // if(emaSlope != 0)
   // {
   //    if(direction > 0 && emaSlope < 0)
   //    {  Print(patternName, " BUY skip: EMA slope falling"); return false; }
   //    if(direction < 0 && emaSlope > 0)
   //    {  Print(patternName, " SELL skip: EMA slope rising"); return false; }
   // }

   // H1 Trend filter: don't trade against the trend
   if(direction > 0 && trendH1 < 0)
   {  Print(patternName, " BUY skip: H1 trend bearish"); return false; }
   if(direction < 0 && trendH1 > 0)
   {  Print(patternName, " SELL skip: H1 trend bullish"); return false; }

   // M15 Structure confluence
   if(InpUseM15Confluence && m15EmaHandle != INVALID_HANDLE)
   {
      if(direction > 0 && trendM15 < 0)
      {  Print(patternName, " BUY skip: M15 structure bearish"); return false; }
      if(direction < 0 && trendM15 > 0)
      {  Print(patternName, " SELL skip: M15 structure bullish"); return false; }
   }

   // RSI filter
   if(InpUseRSIFilter)
   {
      if(direction > 0 && rsi > InpRSIOverbought)
      {  Print(patternName, " BUY skip: RSI ", DoubleToString(rsi, 1), " overbought"); return false; }
      if(direction < 0 && rsi < InpRSIOversold)
      {  Print(patternName, " SELL skip: RSI ", DoubleToString(rsi, 1), " oversold"); return false; }
   }

   // MACD momentum confirmation
   if(InpUseMACDFilter && macdHandle != INVALID_HANDLE)
   {
      if(direction > 0 && macdSig < 0)
      {  Print(patternName, " BUY skip: MACD bearish momentum"); return false; }
      if(direction < 0 && macdSig > 0)
      {  Print(patternName, " SELL skip: MACD bullish momentum"); return false; }
   }

   // ADX trend strength
   if(InpUseADXFilter && adxHandle != INVALID_HANDLE)
   {
      if(!IsADXTrending(adxDir))
      {  Print(patternName, " skip: ADX choppy market"); return false; }
      // ADX DI direction should match trade direction
      if(direction > 0 && adxDir < 0)
      {  Print(patternName, " BUY skip: ADX DI- dominant"); return false; }
      if(direction < 0 && adxDir > 0)
      {  Print(patternName, " SELL skip: ADX DI+ dominant"); return false; }
   }

   // Volume confirmation
   if(!IsVolumeConfirmed())
   {  Print(patternName, " skip: Volume below threshold"); return false; }

   //=== CALCULATE SL/TP ===
   double entryPrice, slPrice, tpPrice, slDist;

   if(direction > 0) // BUY
   {
      entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      slPrice    = CalculateSLPrice(+1, atr, entryPrice);
      slDist     = entryPrice - slPrice;
   }
   else // SELL
   {
      entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      slPrice    = CalculateSLPrice(-1, atr, entryPrice);
      slDist     = slPrice - entryPrice;
   }

   if(slDist <= 0) { Print(patternName, " skip: Invalid SL distance"); return false; }

   tpPrice = CalculateTPPrice(direction, entryPrice, slDist);
   double tpDist = MathAbs(tpPrice - entryPrice);

   // Minimum R:R check — skip trades where reward doesn't justify risk
   if(InpMinRRRatio > 0 && slDist > 0)
   {
      double actualRR = tpDist / slDist;
      if(actualRR < InpMinRRRatio)
      {
         Print(patternName, " skip: R:R ", DoubleToString(actualRR, 2),
               " < min ", DoubleToString(InpMinRRRatio, 2));
         return false;
      }
   }

   //=== CALCULATE LOT SIZE ===
   double lotSize = CalculateLotSize(slDist);
   if(lotSize <= 0) { Print(patternName, " skip: Lot size = 0"); return false; }

   //=== EXECUTE ===
   double tickSize = GetTickSize();
   bool success = false;
   string comment = patternName + (direction > 0 ? " Buy" : " Sell");

   if(direction > 0)
      success = trade.Buy(lotSize, _Symbol, entryPrice, slPrice, tpPrice, comment);
   else
      success = trade.Sell(lotSize, _Symbol, entryPrice, slPrice, tpPrice, comment);

   if(success)
   {
      ulong posTicket = trade.ResultOrder();
      if(posTicket > 0)
         AddPartialInfo(posTicket, slPrice, tpPrice, entryPrice);

      Print(comment, " @ ", DoubleToString(entryPrice, _Digits),
            " | Lot: ", DoubleToString(lotSize, 2),
            " | SL: ", DoubleToString(slPrice, _Digits),
            " (", DoubleToString(slDist / tickSize, 0), " ticks)",
            " | TP: ", DoubleToString(tpPrice, _Digits),
            " | RSI: ", DoubleToString(rsi, 1),
            " | MACD: ", macdSig > 0 ? "Bull" : (macdSig < 0 ? "Bear" : "Flat"),
            " | H1: ", trendH1 > 0 ? "UP" : (trendH1 < 0 ? "DN" : "FLAT"));
      return true;
   }
   else
   {
      Print(comment, " FAILED. Err: ", GetLastError());
      return false;
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Always manage open positions every tick
   ManageOpenPositions();
   CleanPartialInfo();

   //--- End of day close
   if(InpCloseEndOfDay)
   {
      MqlDateTime dt;
      TimeCurrent(dt);
      if(dt.hour >= InpEODHour && CountPositions() > 0)
      {
         Print("End of Day: Closing all positions");
         CloseAllPositions();
         return;
      }
   }

   //--- Only check entries on new M5 bar
   if(!IsNewBar()) return;

   barsSinceLastLoss++;
   CheckNewDay();
   UpdateDashboard();

   //--- Pre-checks
   if(!IsWithinTradingHours()) return;
   if(InpMaxPositions > 0 && CountPositions() >= InpMaxPositions) return;
   if(InpMaxDailyLosses > 0 && dailyLossCount >= InpMaxDailyLosses) return;
   if(InpCooldownBars > 0 && barsSinceLastLoss < InpCooldownBars) return;
   if(!IsSpreadOK()) return;
   if(!IsDrawdownOK()) return;

   //--- Get EMA values
   double fastEma, slowEma;
   if(!GetEMAValues(fastEma, slowEma)) return;

   //--- Detect patterns (v4.4: Engulfing only by default)
   int signal = 0;
   string patternName = "";

   // Three-Candle Reversal (strongest signal)
   signal = DetectThreeCandlePattern(fastEma);
   if(signal != 0)
   {
      patternName = "3CP";
      if(ExecuteTrade(signal, patternName)) return;
   }

   // Engulfing Pattern
   signal = DetectEngulfingPattern(fastEma);
   if(signal != 0)
   {
      patternName = "ENGULF";
      if(ExecuteTrade(signal, patternName)) return;
   }

   // Pin Bar Pattern
   signal = DetectPinBarPattern(fastEma);
   if(signal != 0)
   {
      patternName = "PINBAR";
      if(ExecuteTrade(signal, patternName)) return;
   }
}
//+------------------------------------------------------------------+
