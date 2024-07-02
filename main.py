import os
import ftplib
import shutil
import sys
from dotenv import load_dotenv

# Load settings from .env file
load_dotenv()

local_directory = os.getenv('LOCAL_DIRECTORY')

ftp_directory = os.getenv('FTP_DIRECTORY')
ftp_host = os.getenv('FTP_HOST')
ftp_user = os.getenv('FTP_USER')
ftp_pass = os.getenv('FTP_PASS')

# Define subfolder for old files
old_subfolder = os.path.join(local_directory, 'old')
os.makedirs(old_subfolder, exist_ok=True)

# Connect to FTP server
ftp = ftplib.FTP(ftp_host)
ftp.login(ftp_user, ftp_pass)

# Change to the desired directory on FTP
ftp.cwd(ftp_directory)

# Get list of files on FTP server
ftp_files = ftp.nlst()

# Get list of files in local directory
local_files = [f for f in os.listdir(local_directory) if os.path.isfile(os.path.join(local_directory, f))]


# Progress callback function
def progress_callback(block):
    global downloaded_size
    downloaded_size += len(block)
    percent_complete = downloaded_size / total_size * 100
    sys.stdout.write(f'\rDownloading {current_file}: {percent_complete:.2f}%')
    sys.stdout.flush()
    local_file.write(block)


# Sync FTP to local directory
for ftp_file in ftp_files:
    if ftp_file.endswith('.') or ftp_file.endswith('..'):
        continue

    local_file_path = os.path.join(local_directory, ftp_file)
    total_size = ftp.size(ftp_file)

    # Check if file exists and has the same size
    if os.path.exists(local_file_path):
        local_size = os.path.getsize(local_file_path)
        if os.path.getsize(local_file_path) == total_size:
            print(f'Skipping {ftp_file} (already exists with same size)')
            continue
            
    downloaded_size = 0
    current_file = ftp_file

    with open(local_file_path, 'wb') as local_file:
        ftp.retrbinary('RETR ' + ftp_file, progress_callback, 1024)

    print()  # Newline after each file download

# Move local files not on FTP to /old subfolder
for local_file in local_files:
    if local_file not in ftp_files:
        shutil.move(os.path.join(local_directory, local_file), os.path.join(old_subfolder, local_file))

# Close FTP connection
ftp.quit()