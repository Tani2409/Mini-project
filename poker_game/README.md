# Poker Texas Hold'em - Pygame

Game poker Texas Hold'em đơn giản: một người chơi đấu với máy.

Luật chơi và hand-ranking sử dụng [PokerKit](https://github.com/uoftcprg/pokerkit)
thông qua lớp adapter `poker_engine.py`. Adapter này cũng cung cấp state engine
server-authoritative để phát triển bàn chơi online nhiều người sau này.

## Cài đặt và chạy

```powershell
cd poker_game
python -m pip install -r requirements.txt
python main.py
```

## Chạy trên trình duyệt

```powershell
python -m pip install -r requirements.txt
$env:PYTHONUTF8=1
python -m pygbag main.py
```

Sau đó mở địa chỉ `http://localhost:8000` trong trình duyệt. Không mở trực tiếp
file HTML bằng `file://`, vì WebAssembly cần được phục vụ qua HTTP.

## Deploy GitHub Pages

Workflow `.github/workflows/deploy-poker.yml` sẽ tự build và deploy game khi có
thay đổi trong thư mục `poker_game` được đẩy lên nhánh `main`.

Lần đầu sử dụng, vào **GitHub repository → Settings → Pages → Source** và chọn
**GitHub Actions**. Sau khi workflow hoàn tất, game sẽ có địa chỉ dạng:

`https://<ten-tai-khoan>.github.io/<ten-repository>/`

## Điều khiển

- `CHECK / CALL`: theo cược hoặc bỏ qua nếu chưa có cược.
- `RAISE +20`: tăng cược thêm 20 chip.
- `FOLD`: bỏ bài.
- `VÁN MỚI`: bắt đầu ván tiếp theo.
- `ESC`: thoát game.

Trên phiên bản web, đóng tab trình duyệt để thoát.

Mỗi bên bắt đầu với 1.000 chip. Small blind là 10 và big blind là 20.
