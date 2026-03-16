# Huong Dan Gui Thong Bao BUY/SELL Qua Gmail

## Tong Quan

Khi indicator XAUUSD Clean Scalping Engine v10 phat hien tin hieu BUY hoac SELL, he thong se tu dong gui email chi tiet ve Gmail cua ban, bao gom: Entry, TP1-3, SL, R:R, Momentum Score, v.v.

Co **2 cach** de nhan thong bao qua email:

---

## Cach 1: Dung Email Co San Cua TradingView (Don Gian)

> Chi can tai khoan TradingView mien phi. Email se gui ve dia chi dang ky TradingView.

1. Mo chart **XAUUSD** tren TradingView
2. Add indicator: **Indicators** -> **My Scripts** -> chon "XAUUSD Clean Scalping Engine v10"
3. Click bieu tuong **chuong** (Alert) -> **Create Alert**
4. Cai dat:
   - **Condition**: Chon indicator "XAUUSD Clean Scalping Engine v10"
   - **Option 1**: Chon "BUY Signal" hoac "SELL Signal" (alertcondition)
   - **Option 2**: Chon "Any alert() function call" (nhan tat ca alert bao gom TP hit, jump, v.v.)
5. Tab **Notifications**:
   - Tick **Email** -> email se gui ve dia chi dang ky TradingView
6. Click **Create**

**Uu diem**: Don gian, mien phi, khong can setup gi them.
**Nhuoc diem**: Email chi gui ve email TradingView, noi dung don gian.

---

## Cach 2: Webhook + Google Apps Script (Chi Tiet, Dep)

> Can tai khoan TradingView **Pro** tro len (de dung Webhook URL).
> Email gui ve bat ky Gmail nao ban muon, voi giao dien HTML dep.

### Buoc 1: Tao Google Apps Script

1. Vao [Google Apps Script](https://script.google.com)
2. Click **New Project**
3. Xoa code mac dinh, copy **toan bo** noi dung file `gmail_webhook.gs` vao
4. **Quan trong**: Thay `YOUR_EMAIL@gmail.com` thanh email Gmail cua ban tai dong:
   ```javascript
   EMAIL_TO: "YOUR_EMAIL@gmail.com",
   ```
5. Click **Save** (Ctrl+S)

### Buoc 2: Deploy Web App

1. Click **Deploy** -> **New deployment**
2. Click bieu tuong banh rang -> chon **Web app**
3. Cai dat:
   - **Description**: "TradingView XAUUSD Alert"
   - **Execute as**: **Me**
   - **Who has access**: **Anyone**
4. Click **Deploy**
5. **Authorize access**: Click "Authorize access" -> chon tai khoan Google -> "Allow"
6. **Copy URL** deployment (dang: `https://script.google.com/macros/s/xxx/exec`)

### Buoc 3: Test Thu

1. Trong Apps Script Editor, chon ham `testSendBuyEmail` tu dropdown
2. Click **Run**
3. Kiem tra hop thu Gmail -> ban se nhan duoc email test

### Buoc 4: Cai Dat TradingView Alert

1. Mo chart **XAUUSD** tren TradingView
2. Add indicator neu chua co
3. Click **chuong** (Alert) -> **Create Alert**
4. Cai dat:
   - **Condition**: Chon indicator "XAUUSD Clean Scalping Engine v10"
   - Chon **"Any alert() function call"**
5. Tab **Notifications**:
   - Tick **Webhook URL**
   - Dan URL Google Apps Script vao
6. **Alert actions**: "Once Per Bar Close" (khuyen nghi)
7. Click **Create**

### Buoc 5: Xac Nhan

- Khi co tin hieu BUY/SELL moi tren chart, ban se nhan email Gmail voi noi dung chi tiet
- Email bao gom: Entry, TP1-3, SL, R:R ratios, Risk, ATR, Volume, ADX, Momentum Score

---

## Noi Dung Email Mau

Email se co giao dien HTML dep voi cac thong tin:

```
+---------------------------+
|     BUY XAUUSD            |
|   16/03/2026 15:30:00     |
+---------------------------+
| ENTRY      |    2650.50   |
| TP1        |    2655.30   |
| TP2        |    2660.10   |
| TP3        |    2668.50   |
| STOP LOSS  |    2645.20   |
+---------------------------+
| Risk: 5.30  | ATR: 6.80  |
| Vol: 1.3x   | ADX: 28.5  |
| Score: 4/5   | Bull: 72%  |
+---------------------------+
```

---

## Luu Y

- **Cach 1** (TradingView Email): Mien phi nhung chi gui ve email TradingView
- **Cach 2** (Webhook): Can TradingView Pro, nhung email dep hon va gui ve bat ky Gmail nao
- Google Apps Script co gioi han **100 email/ngay** (du cho scalping)
- Nen dat Alert expiration dai (VD: "Open-ended") de khong bi mat alert
- Timezone mac dinh: Asia/Ho_Chi_Minh (co the thay trong `gmail_webhook.gs`)
