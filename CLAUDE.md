## Deployment
* This is a ESP32 MicroPython project.
* Files are located in the `esp32/` subfolder.
* To deploy, cd to esp32/ and use `./deploy.sh -r main.py boot.py file.py` this will upload those 3 files and restart (-r).
* To change WiFi, cd to esp32/ and use `./generate_boot.py SSID PSK webrepl_password` and `./deploy.sh -r boot.py`
