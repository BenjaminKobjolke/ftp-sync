# ftp-sync
Sync a local folder with a ftp folder.

The script will download all files from the ftp server to the local folder.

If there is a local file that is not on the ftp server anymore, it will be moved to the subfolder "old".


# install
- make sure you have python 3.11 installed
- pip install -r requirements.txt
- copy .env.example to .env and fill in the required fields
- run the script with `python main.py`

