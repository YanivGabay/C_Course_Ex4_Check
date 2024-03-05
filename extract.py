import os
import zipfile
import tarfile
import shutil

import os, stat

def check_permissions(path):
    # Check for read, write, and execute permissions
    is_readable = os.access(path, os.R_OK)
    is_writable = os.access(path, os.W_OK)
    permissions = {'readable': is_readable, 'writable': is_writable}
    return permissions

def handle_extraction_directory(student_path, log_entries, scores, student_dir):
   
    contents_after_extraction = os.listdir(student_path)
    if len(contents_after_extraction) == 1 and os.path.isdir(os.path.join(student_path, contents_after_extraction[0])):
        print(f"Found an unwanted directory: {contents_after_extraction[0]}")
        unwanted_dir = contents_after_extraction[0]
        unwanted_dir_path = os.path.join(student_path, unwanted_dir)
        dir_permissions = check_permissions(unwanted_dir_path)

        if not dir_permissions['readable'] or not dir_permissions['writable']:
            log_entries.append(f"Permission denied for directory '{unwanted_dir}'. Readable: {dir_permissions['readable']}, Writable: {dir_permissions['writable']}")
            return  # Exit the function if you don't have necessary permissions

        try:
            for item in os.listdir(unwanted_dir_path):
                item_path = os.path.join(unwanted_dir_path, item)
                item_permissions = check_permissions(item_path)

                if item_permissions['readable'] and item_permissions['writable']:
                    shutil.move(item_path, student_path)
                else:
                    log_entries.append(f"Permission denied for item '{item}'. Readable: {item_permissions['readable']}, Writable: {item_permissions['writable']}")

            os.rmdir(unwanted_dir_path)
            log_entries.append(f"Moved contents from unwanted directory '{unwanted_dir}' to the main directory.")
            scores[student_dir] -= 15  # Deduct points for having an extra directory

        except Exception as e:
            log_entries.append(f"Error moving contents from unwanted directory '{unwanted_dir}': {e}")


def unzip_and_extract_student_submissions(main_dir):
    extraction_logs = {}
    scores = {}

    for student_dir in os.listdir(main_dir):
        student_path = os.path.join(main_dir, student_dir)
        if not os.path.isdir(student_path):
            continue

        log_entries = []
        score = 100  # Start with a full score

        for file in os.listdir(student_path):
            file_path = os.path.join(student_path, file)
            if file.endswith('.zip'):
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(student_path)
                        log_entries.append(f"Extracted and deleted {file}")
                    os.remove(file_path)  # Delete the zip file after extraction
                except zipfile.BadZipFile:
                    log_entries.append(f"Error extracting {file}: Bad zip file")
                    score -= 10
            elif file.endswith('.tgz'):
                try:
                    with tarfile.open(file_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(student_path)
                        log_entries.append(f"TGZ archive found: {file}.")
                        score -= 0
                        log_entries.append(f"Extracted and deleted {file}")
                    os.remove(file_path)  # Delete the tgz file after extraction
               
                except tarfile.TarError:
                    log_entries.append(f"Error extracting {file}: Bad tgz file")
                    score -= 20
            elif file.endswith('.rar'):
                log_entries.append(f"RAR archive found: {file}. Manual extraction required.")
                score -= 15
            elif file.endswith('.tar.gz'):
                log_entries.append(f"TAR archive found: {file}. Manual extraction required.")
                score -= 15
                # Note: Manual extraction required for .rar files or use an external tool
        scores[student_dir] = score
        handle_extraction_directory(student_path, log_entries, scores, student_dir)
        extraction_logs[student_dir] = log_entries
        

    # Return the logs and scores for further processing
    return extraction_logs, scores

def write_summary_log(main_dir, extraction_logs, scores):
    summary_log_path = os.path.join(main_dir, "extraction_summary.log")
    with open(summary_log_path, 'w') as log_file:
        for student, logs in extraction_logs.items():
            log_file.write(f"Logs for {student}:\n")
            for log in logs:
                log_file.write(f" - {log}\n")
            log_file.write(f"Score for {student}: {scores[student]} points\n\n")

# Directory containing all student folders
main_dir = os.getcwd()

# Run the function to unzip and extract submissions, and collect logs and scores
extraction_logs, scores = unzip_and_extract_student_submissions(main_dir)

# Write a summary log file with the extraction logs and scores for all students
write_summary_log(main_dir, extraction_logs, scores)

print(f"Extraction summary log has been written to {os.path.join(main_dir, 'extraction_summary.log')}")
