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

githash = subprocess.check_output(['git', 'describe', '--always', '--tags', '--long'], encoding='utf-8').strip()

# Configuration
PACKAGE_NAME = f'RedPlanted-{githash}'
RESOURCES = [
    'data',
    'run_game.py',
    'requirements.txt',
    'ARTWORK.md',
]
HERE = os.path.dirname(__file__)
DST = 'sdist'
README = open(os.path.join(HERE, 'README.dist.md'), 'r').read()

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

# write README
readme = target_folder / 'README.md'
readme.write_text(README)

# run game
print('Will try to run the game now. Check if everything works and then close the window.')
completed_process = subprocess.run(['python3', 'run_game.py',], check=False, cwd=target_folder)

# if okay, create archive
if completed_process.returncode == 0:
    print('Creating ZIP...')
    shutil.make_archive(target_folder, 'zip', target_folder)
    print(r'Created ZIP archive! \o/')
