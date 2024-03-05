import os
import subprocess
import re
import signal
import threading
from summarize import do_summarize, display_statistics
import time
import logging
import sys
import resource
import select

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)


# Handle SIGTERM and SIGINT signals
def signal_handler(signum, frame):
    logging.info(f"Received signal: {signum}")

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def set_limits():
    # Limit CPU time to 30 seconds
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    # Limit maximum memory size to 256 MB
    resource.setrlimit(resource.RLIMIT_AS, (256*1024*1024, 256*1024*1024))
# ------------------------------------------------------------------ #
def run_process_with_timeout_valgrind(command, exe_file, timeout_duration):
    try:
        max_output_lines = 5
        process = subprocess.Popen(command, preexec_fn=set_limits, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True, start_new_session=True)
        logging.info(f"Before valgrind process.communicate Running {exe_file} with PID: {process.pid}")
        
        stdout,stderr = process.communicate(timeout=timeout_duration)
       
        logging.info(f"After valgrind process.communicate Running {exe_file} with PID: {process.pid}")
        logging.info(f"stdout: {stdout}")
        logging.info(f"stderr: {stderr}")
        return stdout, stderr, None  # No error
    except subprocess.TimeoutExpired:
        logging.warning(f"Timeout expired running {exe_file}, attempting to terminate with SIGINT...")
        process.send_signal(signal.SIGINT)  # Send SIGINT to the process

        try:
            # Wait for the process to terminate after SIGINT
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            logging.warning("Process did not terminate after SIGINT, attempting to send '0'...")
            process.terminate()
        return stdout, stderr, "Execution timed out."
    except Exception as e:
        logging.exception(f"Error running {exe_file}")
        return None, None, str(e)

def run_process_with_timeout(command, exe_file, timeout_duration, input_data=None, max_output_bytes=1024*1024):
    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True, start_new_session=True)
        logging.info(f"Starting {exe_file} with PID: {process.pid}")

        start_time = time.time()
        stdout, stderr = '', ''
        while True:
            # Check if the timeout has been exceeded
            if time.time() - start_time > timeout_duration:
                logging.warning(f"Timeout expired running {exe_file}, attempting to terminate...")
              
                raise subprocess.TimeoutExpired(process.args, timeout_duration)

            # Use select to wait for output to be available
            readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
            if readable:
               #logging.debug(f"readable: select.select {readable}")
            # Read available output
            
                for output in readable:
                    if output == process.stdout:
                        chunk = process.stdout.read(1024)
                        stdout += chunk
                    elif output == process.stderr:
                        chunk = process.stderr.read(1024)
                        stderr += chunk

                # Check if both stdout and stderr have reached the output limit
                if len(stdout) + len(stderr) >= max_output_bytes:
                    logging.warning("Maximum output size reached. Further output will be discarded.")
                    break

            # Check if the process has terminated
            if process.poll() is not None:
                break

        logging.info(f"Completed {exe_file} with PID: {process.pid}")
        logging.info(f"stdout: {stdout[:10]}")  # Log only the first 1000 characters
        logging.info(f"stderr: {stderr[:50]}")

        return stdout, stderr, None

    except subprocess.TimeoutExpired:
        logging.warning(f"Timeout expired running {exe_file}, attempting to terminate...")
        process.kill()
        process.wait()
        logging.info(f"Terminated {exe_file} due to timeout.")

        return stdout, stderr, "Execution timed out."

    except Exception as e:
        logging.exception(f"Error running {exe_file}")
        if process:
            process.kill()
            process.wait()
        return None, None, str(e)

    finally:
        if process:
            process.stdout.close()
            process.stderr.close()


def remove_all_msg_queues():
    try:
        # Command to list and remove all message queues
        cmd = "ipcs -q | awk '/0x/ {print $2}' | xargs -n 1 ipcrm -q"
        subprocess.run(cmd, shell=True, check=True)
        logging.info("Successfully removed all message queues")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to remove message queues: {e}")

# ------------------------------------------------------------------ #

class Student:
    def __init__(self, student_dir):
        self.student_dir = student_dir
        self.compilation_errors = []
        self.warning_messages = []
        self.test_results = []
        self.grade = 100  # Starting grade, adjust based on errors and warnings
        self.extraction_penalty = 0  # Adjust based on extraction summary log
        self.catched_errors = []
        self.memory_leaks = []
        self.readme_content = self.read_readme()
        self.output = []
        self.source_headers = {}

    def read_readme(self):
        readme_files = [file for file in os.listdir(self.student_dir) if file.lower().startswith('readme')]
        readme_content = []
        if readme_files:
            readme_path = os.path.join(self.student_dir, readme_files[0])
            try:
                with open(readme_path, 'r') as readme_file:
                    for _ in range(10):
                        line = readme_file.readline()
                        if not line:
                            break
                        readme_content.append(line.strip())
            except Exception as e:
                logging.exception("Error reading README")
                readme_content.append(f"Error reading README: {str(e)}")
        return readme_content

    def compile_single_program(self, source_file, exe_file):
        compile_result = subprocess.run(["gcc", "-Wall", "-g", source_file, "-o", exe_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return compile_result

    def handle_compilation_result(self, compile_result, program):
        if compile_result.returncode != 0:
            self.compilation_errors.append(compile_result.stderr)
            logging.error(f"Compilation failed for {program}: {compile_result.stderr}")
            self.grade -= 40  # Deduct points for compilation error
        elif compile_result.stderr:
            self.warning_messages.append(compile_result.stderr)
            logging.warning(f"Warnings for {program}: {compile_result.stderr}")
            self.grade -= 7  # Deduct points for warnings

    def compile_program(self, program):
        program_sources = {
            "ex4a1": ["ex4a1.c"],
            "ex4a2": ["ex4a2.c"],
            "ex4b1": ["ex4b1.c", "ex4b2.c"],
            "ex4c1": ["ex4c1.c", "ex4c2.c", "ex4c3.c"],
        }
        try:
            for source in program_sources.get(program, []):
                source_file = os.path.join(self.student_dir, source)
                exe_file = os.path.join(self.student_dir, source.replace(".c", ""))
                if os.path.exists(source_file):
                    compile_result = self.compile_single_program(source_file, exe_file)
                    self.handle_compilation_result(compile_result, source)
                else:
                    self.compilation_errors.append(f"Source file {source}.c not found.")
                    logging.error(f"Source file {source}.c not found.")
                    self.grade -= 5  # Deduct points for missing file
                logging.info(f"Compilation completed for {source}")
                self.valgrind_check(exe_file)
        except Exception as e:
            logging.exception(f"Error compiling {program}")

    def valgrind_check(self, exe_file):
        try:
            logging.info(f"Running Valgrind on {exe_file}")
            valgrind_command = ["valgrind", "--leak-check=summary", exe_file]
            stdout, stderr, error = run_process_with_timeout_valgrind(valgrind_command, exe_file, 30)
            if stderr and "no leaks are possible" not in stderr:
                self.grade -= 10
                self.memory_leaks.append(f"Memory leaks detected in {exe_file}:\n{stderr}")
            else:
                self.memory_leaks.append(f"No memory leaks in {exe_file}")
            logging.info(f"Valgrind check completed for {exe_file}")
        except subprocess.TimeoutExpired:
            logging.error(f"Timeout expired running Valgrind on {exe_file}")
            self.memory_leaks.append(f"Timeout expired during Valgrind check for {exe_file}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Valgrind process was terminated for {exe_file}, possibly 'killed'. Return code: {e.returncode}")
            self.memory_leaks.append(f"Valgrind process was terminated for {exe_file}.")
        except Exception as e:
            logging.exception(f"Error running Valgrind on {exe_file}")

    def execute_program(self, command, input_data=None):
        try:
            if command is "ex4c3" or command is "ex4c2" or command is "ex4c1":
                timeout = 12
            else:
                timeout = 120
            thread_id = threading.get_ident()  # Get current thread identifier
            logging.debug(f"Thread {thread_id} executing command: {' '.join(command)}")    
            stdout, stderr, error = run_process_with_timeout(command, command[0], timeout,input_data=input_data)
            if stdout:
                logging.info(f"Output for {' '.join(command)}: {stdout}")
                self.output.append((command[0], stdout))
            if error:
                logging.error(f"Error execute_program error: {' '.join(command)}: {error}")
                self.catched_errors.append(error)
            if stderr:
                logging.error(f"Error execute_program stderr: {' '.join(command)}: {stderr}")
                self.catched_errors.append(stderr)
        except Exception as e:
            logging.exception(f"Error running {' '.join(command)}")

    def just_run_all(self):
        commands_groups = [
        [  # First group of commands
            [os.path.join(self.student_dir, "ex4a1"), "fifom", "fifo1", "fifo2"],
            [os.path.join(self.student_dir, "ex4a2"), "fifom", "0"],
            [os.path.join(self.student_dir, "ex4a2"), "fifom", "1"],
            ],
        [  # Second group of commands
            [os.path.join(self.student_dir, "ex4b1")],
            [os.path.join(self.student_dir, "ex4b2"), "0"],
            [os.path.join(self.student_dir, "ex4b2"), "1"],
            ],
        [  # Third group of commands
            [os.path.join(self.student_dir, "ex4c1")],
            [os.path.join(self.student_dir, "ex4c2")],
            [os.path.join(self.student_dir, "ex4c3")],  # This one requires special input handling
              ]
          ]
        try:
           
            remove_all_msg_queues()
            for commands in commands_groups:
                if os.path.exists(commands[0][0]) :
                    remove_all_msg_queues()
                    threads = []  # Resetting threads for each group
                    for command in commands:
                        logging.info(f"Running {' '.join(command)} for {self.student_dir}")
                       
                        if command[0].endswith("ex4c3"):
                        # Special handling for ex4c3, assuming you want to send and receive specific data
                           logging.info(f"Special handling for {' '.join(command)}")
                           thread = threading.Thread(target=self.execute_program, args=(command, "p 1 2 3 4 5 6 7 8 9 10 0\nq 121\n"))
                        else:
                            thread = threading.Thread(target=self.execute_program, args=(command,))
                        threads.append(thread)
                        thread.start()
                        if 'ex4a1' in command or 'ex4b1' in command or 'ex4c1' in command or 'ex4c2' in command:
                            logging.info("Waiting after starting creator program")
                            time.sleep(5)  # Wait for 1 second after starting the creator program
                    # Debugging: List all live threads
                    live_threads = threading.enumerate()
                    logging.debug(f"Live threads: {[thread.name for thread in live_threads]}")        
                    for thread in threads:
                        thread.join()
        except Exception as e:
            logging.exception("Error in just_run_all method")

    def read_source_header(self, num_lines=20):
        for file in os.listdir(self.student_dir):
            if file.endswith(".c"):
                try:
                    with open(os.path.join(self.student_dir, file), 'r') as src_file:
                        header_lines = [next(src_file) for _ in range(num_lines)]
                        self.source_headers[file] = header_lines
                except StopIteration:
                    pass  # File has less than 'num_lines' lines
                except Exception as e:
                    logging.exception(f"Error reading file {file}")

    def log_to_file(self, message):
        with open(os.path.join(self.student_dir, "test_results.log"), 'a') as log_file:
            log_file.write(message + "\n")

# ------------------------------------------------------------------ #

def read_extraction_penalties(summary_log_path):
    penalties = {}
    try:
        with open(summary_log_path, 'r', encoding='utf-8') as f:
            content = f.read().split('\n\n')
            for block in content:
                lines = block.split('\n')
                if lines[0].startswith("Logs for "):
                    student_name = lines[0][9:-1]  # Remove "Logs for " and trailing colon
                    score_line = lines[-1]
                    score = int(score_line.split(': ')[-1].split(' ')[0])
                    penalties[student_name] = 100 - score  # Calculate penalty
    except Exception as e:
        logging.exception("Error reading extraction penalties")
    return penalties

# ------------------------------------------------------------------ #

def cleanup_fifos(fifo_list, main_dir):
    for fifo in fifo_list:
        try:
            os.remove(fifo)
            logging.info(f"Removed named pipe: {fifo}")
        except OSError as e:
            logging.error(f"Error removing named pipe {fifo}: {e}")
            

# ------------------------------------------------------------------ #

def contains_hebrew(name):
    return bool(re.search(r'[\u0590-\u05FF]', name))

# ------------------------------------------------------------------ #

def student_count(main_dir):
    directories = [name for name in os.listdir(main_dir) if os.path.isdir(os.path.join(main_dir, name))]
    hebrew_directories = [name for name in directories if contains_hebrew(name)]
    return len(hebrew_directories)

# ------------------------------------------------------------------ #

# Main script
ex_name = "ex4"
main_dir = os.getcwd()
extraction_summary_log_path = os.path.join(main_dir, "extraction_summary.log")
extraction_penalties = read_extraction_penalties(extraction_summary_log_path)

students = []
final_summary_file_path = os.path.join(main_dir, f"final_summary_{ex_name}.log")
count = 0

with open(final_summary_file_path, 'w') as final_summary_file:
    for student_dir in os.listdir(main_dir):
        student_path = os.path.join(main_dir, student_dir)
        if not os.path.isdir(student_path) or not contains_hebrew(student_dir):
            continue

        try:
            fifo_list = ['fifom', 'fifo1', 'fifo2']
            logging.info(f"Processing: {student_dir}")
            cleanup_fifos(fifo_list,main_dir)

            student = Student(student_dir)
            student.extraction_penalty = extraction_penalties.get(student_dir, 0)
            students.append(student)

            logging.info(f"Compiling for {student_dir}")
            for program in ["ex4a1", "ex4a2", "ex4b1", "ex4c1"]:
                student.compile_program(program)
            student.just_run_all()
            student.read_source_header()
            count += 1
            cleanup_fifos(fifo_list,main_dir)

            student_summary = do_summarize(student)
            final_summary_file.write(student_summary)
            final_summary_file.write("\n" + "="*40 + "\n\n")
        except Exception as e:
            logging.exception(f"An error occurred while processing {student_dir}")
            final_summary_file.write(f"Error processing {student_dir}: {str(e)}\n\n")
            final_summary_file.write("\n" + "="*40 + "\n\n")

logging.info(f"Total {count} students out of {student_count(main_dir)}")
display_statistics(students, count)
