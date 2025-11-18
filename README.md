1) ติดตั้ง Git ก่อน

ดาวน์โหลดที่: https://git-scm.com/downloads

🔹 2) เปิด Terminal / CMD / PowerShell

แล้วใช้คำสั่ง:

git clone https://github.com/Anuwatkl65/A.best.git


จะได้โฟลเดอร์ชื่อ A.best ในเครื่องผู้ใช้งาน

ถ้าต้องการให้เขาเปิดใน VS Code
cd A.best
code .

ถ้าต้องการให้เขาใช้งาน virtual environment (Python)

ในโฟลเดอร์โปรเจกต์ ให้รัน:

python -m venv venv


แล้ว activate:

🔸 Windows PowerShell:
venv\Scripts\Activate

🔸 Windows CMD:
venv\Scripts\activate.bat

🔸 Mac/Linux:
source venv/bin/activate

ติดตั้ง dependencies:
pip install -r requirements.txt

🎯 แบบข้อความสั้นให้นำไปส่งให้คนอื่น (Copy ไปใช้ได้เลย)
# Clone project
git clone https://github.com/Anuwatkl65/A.best.git
cd A.best

# Setup virtual environment
python -m venv venv
venv\Scripts\activate   # (Windows)
pip install -r requirements.txt

# Start project (if Django)
python manage.py runserver
