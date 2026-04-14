# S.A.I. Network Control Addon

You have successfully turned S.A.I. into a Multi-Device System!

## How to connect an Android Agent:
1. Install Termux on your Android phone from F-Droid.
2. Install Termux:API app from F-Droid.
3. Open Termux and run:
   > pkg update && pkg install python termux-api
   > pip install python-socketio websocket-client
4. Copy the `agents/android_termux_agent.py` to your phone.
5. Edit `HUB_URL` in the script to match the Pi's local IP (e.g. `http://192.168.1.10:5000`).
6. Run `python android_termux_agent.py`.

## How to connect a Windows Agent:
1. Make sure Python is installed on your PC.
2. Run `pip install python-socketio websocket-client`.
3. Copy `agents/windows_agent.py` to the PC.
4. Edit `HUB_URL` to match the Pi's local IP.
5. Run `python windows_agent.py`.

## How it works:
S.A.I. will detect when these devices connect silently over WebSockets to port 5000. Once connected, S.A.I.'s main brain will understand requests like "Send a WhatsApp message" and automatically route the command over the socket to the phone!
