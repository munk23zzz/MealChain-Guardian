import sys
sys.path.insert(0, "/app")
import os
os.chdir("/app")
import tests.conftest as c
print("kiriman hari ini:", c._ada_kiriman_demo_hari_ini())
print("bukti masih segar:", c._bukti_suhu_masih_segar())
