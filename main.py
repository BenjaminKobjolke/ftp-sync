import os
import ftplib
import shutil
import sys
import configparser
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-local storage for FTP connections
thread_local = threading.local()

def get_ftp_connection(settings):
    """Create or get thread-local FTP connection"""
    if not hasattr(thread_local, "ftp"):
        ftp = ftplib.FTP(settings['ftp_host'])
        ftp.login(settings['ftp_user'], settings['ftp_pass'])
        if settings['ftp_directory']:
            ftp.cwd(settings['ftp_directory'])
        thread_local.ftp = ftp
    return thread_local.ftp

def load_settings(ini_file):
    config = configparser.ConfigParser()
    if not config.read(ini_file):
        raise FileNotFoundError(f"Could not read settings file: {ini_file}")
    
    if 'FTP' not in config:
        raise ValueError("Missing [FTP] section in settings file")
    
    settings = config['FTP']
    required_settings = ['FTP_HOST', 'FTP_USER', 'FTP_PASS']

    for setting in required_settings:
        if setting not in settings:
            raise ValueError(f"Missing required setting: {setting}")

    return {
        'local_directory': settings.get('LOCAL_DIRECTORY', ''),
        'ftp_directory': settings.get('FTP_DIRECTORY', ''),
        'ftp_host': settings['FTP_HOST'],
        'ftp_user': settings['FTP_USER'],
        'ftp_pass': settings['FTP_PASS'],
        'direction': settings.get('DIRECTION', 'down'),
        'concurrent_operations': int(settings.get('CONCURRENT_UPLOADS_OR_DOWNLOADS', '1'))
    }

def parse_arguments():
    parser = argparse.ArgumentParser(description='FTP Sync Tool')
    parser.add_argument('settings_file', help='Path to the settings INI file')
    parser.add_argument('--local-dir', '-l', help='Override LOCAL_DIRECTORY from INI file')
    parser.add_argument('--ftp-dir', '-f', help='Override FTP_DIRECTORY from INI file')
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

def upload_file(args):
    """Upload a single file to FTP server"""
    local_file, settings, ftp_files = args
    if local_file in ['.', '..']:
        return None

    try:
        ftp = get_ftp_connection(settings)
        
        local_file_path = os.path.join(settings['local_directory'], local_file)
        ftp_file_path = local_file.replace('\\', '/')
        ftp_base = settings['ftp_directory'].rstrip('/')
        ftp_absolute_path = f"{ftp_base}/{ftp_file_path}"
        ftp_dir = os.path.dirname(ftp_absolute_path)

        if ftp_dir:
            ensure_ftp_dir(ftp, ftp_dir)

        total_size = os.path.getsize(local_file_path)

        # Check if file exists and has the same size on FTP
        if local_file in ftp_files:
            try:
                ftp_size = ftp.size(ftp_absolute_path)
                if ftp_size == total_size:
                    print(f'Skipping {local_file} (already exists with same size)')
                    #return None
            except:
                pass  # File doesn't exist or can't get size, proceed with upload

        print(f'Uploading {local_file}')
        with open(local_file_path, 'rb') as file:
            ftp.storbinary(f'STOR {ftp_absolute_path}', file, 1024)
        
        print(f'Completed upload of {local_file}')
        return local_file
    except Exception as e:
        print(f"Error uploading {local_file}: {str(e)}")
        return None

def download_file(args):
    """Download a single file from FTP server"""
    ftp_file, settings, local_files = args
    if ftp_file.endswith('.') or ftp_file.endswith('..'):
        return None

    try:
        ftp = get_ftp_connection(settings)
        
        local_file_path = os.path.join(settings['local_directory'], ftp_file)
        local_dir = os.path.dirname(local_file_path)
        ensure_local_dir(local_dir)

        try:
            total_size = ftp.size(ftp_file)
        except:
            print(f"Couldn't get size for {ftp_file}, skipping...")
            return None

        # Check if file exists and has the same size
        if os.path.exists(local_file_path):
            local_size = os.path.getsize(local_file_path)
            if local_size == total_size:
                print(f'Skipping {ftp_file} (already exists with same size)')
                return None

        print(f'Downloading {ftp_file}')
        with open(local_file_path, 'wb') as file:
            ftp.retrbinary(f'RETR {ftp_file}', file.write, 1024)
        
        print(f'Completed download of {ftp_file}')
        return ftp_file
    except Exception as e:
        print(f"Error downloading {ftp_file}: {str(e)}")
        return None

def sync_files(settings, ftp_files, local_files, operation_func, file_list):
    """Sync files using concurrent operations"""
    max_workers = settings['concurrent_operations']
    completed_files = []
    
    print(f"Starting sync with {max_workers} concurrent operations...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create arguments for each file operation
        args_list = [(f, settings, ftp_files if operation_func == upload_file else local_files) 
                    for f in file_list]
        
        # Submit all tasks and wait for completion
        future_to_file = {executor.submit(operation_func, args): args[0] 
                         for args in args_list}
        
        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result:
                    completed_files.append(result)
            except Exception as e:
                print(f"Operation failed for {file}: {str(e)}")
    
    return completed_files

def handle_old_files(settings, completed_files, local_files):
    """Move files to old directory that are not in completed files"""
    old_subfolder = os.path.join(settings['local_directory'], 'old')
    os.makedirs(old_subfolder, exist_ok=True)

    for local_file in local_files:
        if local_file not in completed_files:
            local_path = os.path.join(settings['local_directory'], local_file)
            old_path = os.path.join(old_subfolder, local_file)
            ensure_local_dir(os.path.dirname(old_path))
            if os.path.exists(local_path):
                shutil.move(local_path, old_path)

def main():
    args = parse_arguments()
    settings = load_settings(args.settings_file)

    # Apply CLI overrides
    if args.local_dir:
        settings['local_directory'] = args.local_dir
    if args.ftp_dir:
        settings['ftp_directory'] = args.ftp_dir

    # Validate that directories are set from at least one source
    if not settings['local_directory']:
        print("Error: LOCAL_DIRECTORY must be set in INI file or via --local-dir argument")
        sys.exit(1)
    if not settings['ftp_directory']:
        print("Error: FTP_DIRECTORY must be set in INI file or via --ftp-dir argument")
        sys.exit(1)

    # Create local directory if it doesn't exist
    os.makedirs(settings['local_directory'], exist_ok=True)

    # Connect to FTP server
    ftp = ftplib.FTP(settings['ftp_host'])
    ftp.login(settings['ftp_user'], settings['ftp_pass'])

    # Change to the desired directory on FTP, creating it if needed
    ensure_ftp_dir(ftp, settings['ftp_directory'])
    ftp.cwd(settings['ftp_directory'])

    # Get list of files recursively
    print("Getting file lists...")
    ftp_files = get_ftp_files_recursive(ftp)
    local_files = get_local_files_recursive(settings['local_directory'])

    try:
        if settings['direction'].lower() == 'up':
            print("Syncing local files to FTP...")
            completed_files = sync_files(settings, ftp_files, local_files, upload_file, local_files)
        else:
            print("Syncing FTP files to local...")
            completed_files = sync_files(settings, ftp_files, local_files, download_file, ftp_files)
            handle_old_files(settings, completed_files, local_files)
    finally:
        # Close FTP connection
        ftp.quit()

if __name__ == "__main__":
    main()
