import os
import ftplib
import shutil
import sys
import configparser
import argparse

def load_settings(ini_file):
    config = configparser.ConfigParser()
    if not config.read(ini_file):
        raise FileNotFoundError(f"Could not read settings file: {ini_file}")
    
    if 'FTP' not in config:
        raise ValueError("Missing [FTP] section in settings file")
    
    settings = config['FTP']
    required_settings = ['LOCAL_DIRECTORY', 'FTP_DIRECTORY', 'FTP_HOST', 'FTP_USER', 'FTP_PASS']
    
    for setting in required_settings:
        if setting not in settings:
            raise ValueError(f"Missing required setting: {setting}")
    
    return {
        'local_directory': settings['LOCAL_DIRECTORY'],
        'ftp_directory': settings['FTP_DIRECTORY'],
        'ftp_host': settings['FTP_HOST'],
        'ftp_user': settings['FTP_USER'],
        'ftp_pass': settings['FTP_PASS'],
        'direction': settings.get('DIRECTION', 'down')  # Default to down if not specified
    }

def parse_arguments():
    parser = argparse.ArgumentParser(description='FTP Sync Tool')
    parser.add_argument('settings_file', help='Path to the settings INI file')
    return parser.parse_args()

# Progress callback function for download
def download_progress_callback(block):
    global downloaded_size
    downloaded_size += len(block)
    percent_complete = downloaded_size / total_size * 100
    sys.stdout.write(f'\rDownloading {current_file}: {percent_complete:.2f}%')
    sys.stdout.flush()
    local_file.write(block)

# Progress callback function for upload
def upload_progress_callback(block):
    global uploaded_size
    uploaded_size += len(block)
    percent_complete = uploaded_size / total_size * 100
    sys.stdout.write(f'\rUploading {current_file}: {percent_complete:.2f}%')
    sys.stdout.flush()

def download_from_ftp(ftp, settings, ftp_files, local_files):
    global downloaded_size, total_size, current_file, local_file
    
    # Sync FTP to local directory
    for ftp_file in ftp_files:
        if ftp_file.endswith('.') or ftp_file.endswith('..'):
            continue

        local_file_path = os.path.join(settings['local_directory'], ftp_file)
        total_size = ftp.size(ftp_file)

        # Check if file exists and has the same size
        if os.path.exists(local_file_path):
            local_size = os.path.getsize(local_file_path)
            if local_size == total_size:
                print(f'Skipping {ftp_file} (already exists with same size)')
                continue
                
        downloaded_size = 0
        current_file = ftp_file

        with open(local_file_path, 'wb') as local_file:
            ftp.retrbinary('RETR ' + ftp_file, download_progress_callback, 1024)

        print()  # Newline after each file download

    old_subfolder = os.path.join(settings['local_directory'], 'old')
    os.makedirs(old_subfolder, exist_ok=True)

    # Move local files not on FTP to /old subfolder
    for local_file in local_files:
        if local_file not in ftp_files:
            shutil.move(os.path.join(settings['local_directory'], local_file), 
                       os.path.join(old_subfolder, local_file))

def upload_to_ftp(ftp, settings, ftp_files, local_files):
    global uploaded_size, total_size, current_file
    
    # Sync local directory to FTP
    for local_file in local_files:
        if local_file in ['.', '..']:
            continue

        local_file_path = os.path.join(settings['local_directory'], local_file)
        total_size = os.path.getsize(local_file_path)

        # Check if file exists and has the same size on FTP
        if local_file in ftp_files:
            try:
                ftp_size = ftp.size(local_file)
                if ftp_size == total_size:
                    print(f'Skipping {local_file} (already exists with same size)')
                    continue
            except:
                pass  # File doesn't exist or can't get size, proceed with upload
                
        uploaded_size = 0
        current_file = local_file

        with open(local_file_path, 'rb') as file:
            print(f'Uploading {local_file}')
            ftp.storbinary(f'STOR {local_file}', file, 1024, upload_progress_callback)
        print()  # Newline after each file upload

def main():
    args = parse_arguments()
    settings = load_settings(args.settings_file)

    # Create local directory if it doesn't exist
    os.makedirs(settings['local_directory'], exist_ok=True)

    # Connect to FTP server
    ftp = ftplib.FTP(settings['ftp_host'])
    ftp.login(settings['ftp_user'], settings['ftp_pass'])

    # Change to the desired directory on FTP
    ftp.cwd(settings['ftp_directory'])

    # Get list of files
    ftp_files = ftp.nlst()
    local_files = [f for f in os.listdir(settings['local_directory']) 
                  if os.path.isfile(os.path.join(settings['local_directory'], f))]

    try:
        if settings['direction'].lower() == 'up':
            print("Syncing local files to FTP...")
            upload_to_ftp(ftp, settings, ftp_files, local_files)
        else:
            print("Syncing FTP files to local...")
            download_from_ftp(ftp, settings, ftp_files, local_files)
    finally:
        # Close FTP connection
        ftp.quit()

if __name__ == "__main__":
    main()
