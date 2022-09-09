"""
Utility script to package our game for PyWeek:
1. Copy relevant files to dist/TheRedPlanted/
2. Try to run the game by calling `python dist/TheRedPlanted/run_game.py`
3. If running the game succeeds, create a ZIP archive for upload
"""
import os
import shutil
from pathlib import Path
import subprocess


# Configuration
PACKAGE_NAME = 'TheRedPlanted'
RESOURCES = [
    'data',
    'run_game.py',
    'requirements.txt',
    'README.md',
]
HERE = os.path.dirname(__file__)
DST = 'sdist'

target_folder = Path(HERE) / DST / PACKAGE_NAME
zip_archive = Path(HERE) / DST / (PACKAGE_NAME + '.zip')

# remove eventually exisiting files in sdist
print('Removing outdates files and folders.')
shutil.rmtree(target_folder, ignore_errors=True)

# copy listed resources
print('Copying resources.')
target_folder.mkdir(exist_ok=True)
for resource in RESOURCES:
    print(resource)
    src = Path(HERE) / resource
    dst = target_folder /resource
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy(src, dst)

# run game
print('Will try to run the game now. Check if everything works and then close the window.')
completed_process = subprocess.run(['python', 'run_game.py',], check=False, cwd=target_folder)

# if okay, create archive
if completed_process.returncode == 0:
    print('Creating ZIP...')
    shutil.make_archive(target_folder, 'zip', target_folder)
    print('Created ZIP archive! \o/')
