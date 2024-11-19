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

def get_ftp_files_recursive(ftp, path='.'):
    """Recursively list files and directories on FTP server"""
    files = []
    try:
        ftp.cwd(path)
        items = ftp.nlst()
        
        for item in items:
            if item in ['.', '..']:
                continue
                
            try:
                # Try to change into the directory
                ftp.cwd(item)
                # If successful, it's a directory
                ftp.cwd('..')  # Go back
                subpath = os.path.join(path, item).replace('\\', '/')
                # Recursively get files from subdirectory
                files.extend(get_ftp_files_recursive(ftp, subpath))
            except ftplib.error_perm:
                # If failed, it's a file
                file_path = os.path.join(path, item).replace('\\', '/')
                if path == '.':
                    files.append(item)
                else:
                    files.append(file_path)
                    
        if path != '.':
            ftp.cwd('..')
            
    except ftplib.error_perm as e:
        print(f"Error accessing path {path}: {str(e)}")
        
    return files

def get_local_files_recursive(local_dir, base_dir=None):
    """Recursively list files in local directory"""
    if base_dir is None:
        base_dir = local_dir
        
    files = []
    for item in os.listdir(local_dir):
        full_path = os.path.join(local_dir, item)
        if os.path.isfile(full_path):
            rel_path = os.path.relpath(full_path, base_dir).replace('\\', '/')
            files.append(rel_path)
        elif os.path.isdir(full_path) and item != 'old':
            files.extend(get_local_files_recursive(full_path, base_dir))
    return files

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

def ensure_local_dir(path):
    """Create local directory if it doesn't exist"""
    if not os.path.exists(path):
        os.makedirs(path)

def ensure_ftp_dir(ftp, path):
    """Create FTP directory if it doesn't exist"""
    try:
        ftp.cwd(path)
        ftp.cwd('/')  # Go back to root
    except ftplib.error_perm:
        # Create directory and any missing parent directories
        parts = path.split('/')
        current = ''
        for part in parts:
            if not part:
                continue
            current = f"{current}/{part}"
            try:
                ftp.cwd(current)
            except ftplib.error_perm:
                ftp.mkd(current)

def download_from_ftp(ftp, settings, ftp_files, local_files):
    global downloaded_size, total_size, current_file, local_file
    
    # Sync FTP to local directory
    for ftp_file in ftp_files:
        if ftp_file.endswith('.') or ftp_file.endswith('..'):
            continue

        local_file_path = os.path.join(settings['local_directory'], ftp_file)
        local_dir = os.path.dirname(local_file_path)
        ensure_local_dir(local_dir)

        try:
            total_size = ftp.size(ftp_file)
        except:
            print(f"Couldn't get size for {ftp_file}, skipping...")
            continue

        # Check if file exists and has the same size
        if os.path.exists(local_file_path):
            local_size = os.path.getsize(local_file_path)
            if local_size == total_size:
                print(f'Skipping {ftp_file} (already exists with same size)')
                continue
                
        downloaded_size = 0
        current_file = ftp_file

        with open(local_file_path, 'wb') as local_file:
            ftp.retrbinary(f'RETR {ftp_file}', download_progress_callback, 1024)

        print()  # Newline after each file download

    old_subfolder = os.path.join(settings['local_directory'], 'old')
    os.makedirs(old_subfolder, exist_ok=True)

    # Move local files not on FTP to /old subfolder
    for local_file in local_files:
        if local_file not in ftp_files:
            local_path = os.path.join(settings['local_directory'], local_file)
            old_path = os.path.join(old_subfolder, local_file)
            ensure_local_dir(os.path.dirname(old_path))
            shutil.move(local_path, old_path)

def upload_to_ftp(ftp, settings, ftp_files, local_files):
    global uploaded_size, total_size, current_file
    
    # Sync local directory to FTP
    for local_file in local_files:
        if local_file in ['.', '..']:
            continue

        local_file_path = os.path.join(settings['local_directory'], local_file)
        ftp_file_path = local_file.replace('\\', '/')
        ftp_dir = os.path.dirname(ftp_file_path)
        
        if ftp_dir:
            ensure_ftp_dir(ftp, ftp_dir)
            ftp.cwd('/')  # Go back to root

        total_size = os.path.getsize(local_file_path)

        # Check if file exists and has the same size on FTP
        if local_file in ftp_files:
            try:
                ftp_size = ftp.size(ftp_file_path)
                if ftp_size == total_size:
                    print(f'Skipping {local_file} (already exists with same size)')
                    continue
            except:
                pass  # File doesn't exist or can't get size, proceed with upload
                
        uploaded_size = 0
        current_file = local_file

        with open(local_file_path, 'rb') as file:
            print(f'Uploading {local_file}')
            ftp.storbinary(f'STOR {ftp_file_path}', file, 1024, upload_progress_callback)
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

    # Get list of files recursively
    print("Getting file lists...")
    ftp_files = get_ftp_files_recursive(ftp)
    local_files = get_local_files_recursive(settings['local_directory'])

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
