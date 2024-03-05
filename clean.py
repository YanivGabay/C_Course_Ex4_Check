import os
import re

def clean_folder_names(main_dir):
    for folder_name in os.listdir(main_dir):
        folder_path = os.path.join(main_dir, folder_name)
        # Ensure we're only dealing with directories
        if os.path.isdir(folder_path):
            # Remove numbers and specific substrings
            new_folder_name = re.sub(r'\d+|_assignsubmission_file|_', '', folder_name)
            new_folder_path = os.path.join(main_dir, new_folder_name)
            # Rename the folder
            os.rename(folder_path, new_folder_path)
            print(f"Renamed '{folder_name}' to '{new_folder_name}'")

# Directory containing all student folders
main_dir = os.getcwd()

# Clean up the folder names
clean_folder_names(main_dir)
