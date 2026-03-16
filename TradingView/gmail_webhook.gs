/**
 * Google Apps Script - TradingView Webhook to Gmail
 * 
 * Script nay nhan webhook tu TradingView va gui email thong bao ve Gmail
 * khi co tin hieu BUY/SELL tren chart XAUUSD.
 *
 * HUONG DAN CAI DAT:
 * 1. Vao https://script.google.com -> Tao project moi
 * 2. Copy toan bo code nay vao
 * 3. Thay YOUR_EMAIL thanh email cua ban
 * 4. Deploy -> New deployment -> Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5. Copy URL deployment -> dan vao Webhook URL trong TradingView Alert
 *
 * CAI DAT TRADINGVIEW ALERT:
 * 1. Mo chart XAUUSD da add indicator
 * 2. Click chuong Alert -> Create Alert
 * 3. Condition: chon indicator "XAUUSD Clean Scalping Engine v10"
 * 4. Chon "Any alert() function call"
 * 5. Notifications -> Webhook URL -> dan URL Google Apps Script
 * 6. Message: de trong (script se tu dong gui JSON)
 * 7. Save
 */

// ===== CAU HINH =====
var CONFIG = {
  EMAIL_TO: "YOUR_EMAIL@gmail.com",  // Thay bang email cua ban
  EMAIL_SUBJECT_PREFIX: "[XAUUSD Signal]",
  TIMEZONE: "Asia/Ho_Chi_Minh"
};

/**
 * Xu ly POST request tu TradingView webhook
 */
function doPost(e) {
  try {
    var body = e.postData.contents;
    var data = JSON.parse(body);
    
    // Gui email dua tren loai tin hieu
    if (data.signal === "BUY" || data.signal === "SELL") {
      sendSignalEmail(data);
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({ status: "ok" }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    // Log loi de debug
    Logger.log("Error: " + error.toString());
    Logger.log("Body: " + (e.postData ? e.postData.contents : "no body"));
    
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", message: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Xu ly GET request (de test deployment)
 */
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: "ok", message: "TradingView Webhook Gmail Service is running" }))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Gui email thong bao tin hieu BUY/SELL
 */
function sendSignalEmail(data) {
  var signal = data.signal;
  var symbol = data.symbol || "XAUUSD";
  var now = Utilities.formatDate(new Date(), CONFIG.TIMEZONE, "dd/MM/yyyy HH:mm:ss");
  
  var subject = CONFIG.EMAIL_SUBJECT_PREFIX + " " + signal + " " + symbol + " - " + now;
  
  var signalColor = signal === "BUY" ? "#00C853" : "#FF1744";
  var signalIcon = signal === "BUY" ? "&#x25B2;" : "&#x25BC;";
  var trendKey = signal === "BUY" ? "bull" : "bear";
  var trendValue = data[trendKey] || "N/A";
  
  var htmlBody = '<!DOCTYPE html>'
    + '<html><head><meta charset="utf-8"></head>'
    + '<body style="font-family:Arial,sans-serif;background:#1a1a2e;color:#e0e0e0;padding:20px;">'
    + '<div style="max-width:500px;margin:0 auto;background:#16213e;border-radius:12px;overflow:hidden;border:1px solid #0f3460;">'
    
    // Header
    + '<div style="background:' + signalColor + ';padding:20px;text-align:center;">'
    + '<h1 style="margin:0;color:white;font-size:28px;">' + signalIcon + ' ' + signal + ' ' + symbol + '</h1>'
    + '<p style="margin:5px 0 0;color:rgba(255,255,255,0.9);font-size:14px;">' + now + '</p>'
    + '</div>'
    
    // Entry & Targets
    + '<div style="padding:20px;">'
    + '<table style="width:100%;border-collapse:collapse;">'
    
    + '<tr><td style="padding:10px;border-bottom:1px solid #0f3460;color:#aaa;font-size:13px;">ENTRY</td>'
    + '<td style="padding:10px;border-bottom:1px solid #0f3460;text-align:right;font-size:16px;font-weight:bold;color:#42A5F5;">' + data.entry + '</td></tr>'
    
    + '<tr><td style="padding:10px;border-bottom:1px solid #0f3460;color:#aaa;font-size:13px;">TP1</td>'
    + '<td style="padding:10px;border-bottom:1px solid #0f3460;text-align:right;color:#00E676;">' + data.tp1 + ' <span style="color:#888;font-size:12px;">(R:R ' + data.rr1 + ')</span></td></tr>'
    
    + '<tr><td style="padding:10px;border-bottom:1px solid #0f3460;color:#aaa;font-size:13px;">TP2</td>'
    + '<td style="padding:10px;border-bottom:1px solid #0f3460;text-align:right;color:#00E676;">' + data.tp2 + ' <span style="color:#888;font-size:12px;">(R:R ' + data.rr2 + ')</span></td></tr>'
    
    + '<tr><td style="padding:10px;border-bottom:1px solid #0f3460;color:#aaa;font-size:13px;">TP3</td>'
    + '<td style="padding:10px;border-bottom:1px solid #0f3460;text-align:right;color:#00E676;">' + data.tp3 + ' <span style="color:#888;font-size:12px;">(R:R ' + data.rr3 + ')</span></td></tr>'
    
    + '<tr><td style="padding:10px;border-bottom:1px solid #0f3460;color:#aaa;font-size:13px;">STOP LOSS</td>'
    + '<td style="padding:10px;border-bottom:1px solid #0f3460;text-align:right;font-size:16px;font-weight:bold;color:#FF1744;">' + data.sl + '</td></tr>'
    
    + '</table>'
    + '</div>'
    
    // Stats
    + '<div style="padding:0 20px 20px;">'
    + '<div style="background:#0f3460;border-radius:8px;padding:15px;display:flex;">'
    + '<table style="width:100%;border-collapse:collapse;">'
    
    + '<tr>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">Risk</td>'
    + '<td style="padding:5px 10px;text-align:right;color:#FFC107;font-size:13px;">' + data.risk + '</td>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">ATR</td>'
    + '<td style="padding:5px 10px;text-align:right;color:#e0e0e0;font-size:13px;">' + data.atr + '</td>'
    + '</tr>'
    
    + '<tr>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">Volume</td>'
    + '<td style="padding:5px 10px;text-align:right;color:#e0e0e0;font-size:13px;">' + data.vol + 'x</td>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">ADX</td>'
    + '<td style="padding:5px 10px;text-align:right;color:#e0e0e0;font-size:13px;">' + data.adx + '</td>'
    + '</tr>'
    
    + '<tr>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">Score</td>'
    + '<td style="padding:5px 10px;text-align:right;color:#FFC107;font-size:13px;">' + data.score + '</td>'
    + '<td style="padding:5px 10px;color:#aaa;font-size:12px;">Trend</td>'
    + '<td style="padding:5px 10px;text-align:right;color:' + signalColor + ';font-size:13px;">' + trendValue + '</td>'
    + '</tr>'
    
    + '</table>'
    + '</div>'
    + '</div>'
    
    // Footer
    + '<div style="padding:15px 20px;background:#0a0a23;text-align:center;color:#555;font-size:11px;">'
    + 'XAUUSD Clean Scalping Engine v10 | TradingView Alert'
    + '</div>'
    
    + '</div>'
    + '</body></html>';
  
  // Gui email
  MailApp.sendEmail({
    to: CONFIG.EMAIL_TO,
    subject: subject,
    htmlBody: htmlBody
  });
  
  // Log
  Logger.log("Email sent: " + subject);
}

/**
 * Ham test thu - chay truc tiep trong Apps Script Editor
 */
function testSendBuyEmail() {
  var testData = {
    signal: "BUY",
    symbol: "XAUUSD",
    entry: "2650.50",
    tp1: "2655.30",
    tp2: "2660.10",
    tp3: "2668.50",
    sl: "2645.20",
    rr1: "1.2",
    rr2: "2.1",
    rr3: "3.5",
    risk: "5.30",
    atr: "6.80",
    adx: "28.5",
    vol: "1.3",
    score: "4/5",
    bull: "72.5%"
  };
  
  sendSignalEmail(testData);
  Logger.log("Test BUY email sent!");
}

function testSendSellEmail() {
  var testData = {
    signal: "SELL",
    symbol: "XAUUSD",
    entry: "2650.50",
    tp1: "2645.70",
    tp2: "2640.90",
    tp3: "2632.50",
    sl: "2655.80",
    rr1: "1.1",
    rr2: "1.9",
    rr3: "3.2",
    risk: "5.30",
    atr: "6.80",
    adx: "25.3",
    vol: "1.5",
    score: "3/5",
    bear: "68.2%"
  };
  
  sendSignalEmail(testData);
  Logger.log("Test SELL email sent!");
}
