# Trade Planner & Journal (Streamlit)

แอปวางแผนเทรดและไดอารี่เทรด (รองรับหลายพอร์ต) พร้อมพรีเซ็ต XAUUSD/BTCUSD

## รันท้องถิ่น
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy บน Streamlit Cloud
1) สร้าง GitHub repo (public) แล้วอัปโหลดไฟล์ 3 ชิ้น: `app.py`, `requirements.txt`, `README.md`
2) ไปที่ https://share.streamlit.io → Sign in → Deploy → เลือก repo
3) เลือกไฟล์หลักเป็น `app.py` → Deploy
4) เปิดลิงก์บนมือถือได้เลย (Add to Home Screen เพื่อให้เหมือนแอป)

> หมายเหตุ: SQLite ในคลาวด์อาจรีเซ็ตเมื่อแอปหลับ (sleep). ถ้าต้องการเก็บข้อมูลถาวร ให้ต่อฐานข้อมูลภายนอก (เช่น Supabase/Postgres).

## ใช้งาน
- แท็บ **Planner**: ใส่ Risk$/ไม้ + SL(pips) → ได้ Lot และประมาณการ Margin
- แท็บ **Trade Log**: กรอก Entry/SL/TP/Exit → ระบบคำนวณ pips และ P/L อัตโนมัติ
- แท็บ **Dashboard**: กราฟและสรุปกำไร
- แท็บ **Settings**: เพิ่มพอร์ต, ปรับราคา Spot ของ XAU/BTC
