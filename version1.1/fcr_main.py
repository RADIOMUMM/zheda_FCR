"""FCR计算工具 - 主入口"""
import sys, os

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fcr_app.gui import main

if __name__ == "__main__":
    main()
