


def do_summarize(student, summary_type="default"):
    # The function now accepts a 'summary_type' parameter for customization
    if summary_type == "default":
        return generate_default_summary(student)


def generate_default_summary(student):
    # Header
    summary_lines = [
        f"Summary for {student.student_dir}",
        "=" * 80,
        f"Grade: {student.grade - student.extraction_penalty}\n",
    ]

    # README Content
    summary_lines.append("README Content:")
    if student.readme_content:
        summary_lines.extend(["\t" + line for line in student.readme_content])
    else:
        summary_lines.append("\tNo README Content Found")
    summary_lines.append("")

    # Source File Headers
    summary_lines.append("Source File Headers:")
    for file, header in student.source_headers.items():
        summary_lines.append(f"\t{file}:")
        summary_lines.extend(["\t\t" + line for line in header])
    summary_lines.append("")

  
    def format_error(field,summary_lines,field_name):
        summary_lines.append(f"{field_name} Errors:")
        if field:
            summary_lines.extend(["\t- " + error for error in field])
        else:
            summary_lines.append("\tNone")
        summary_lines.append("")
    # Compilation
    format_error(student.compilation_errors,summary_lines,"Compilation")
    format_error(student.warning_messages,summary_lines,"Warnings")
    format_error(student.memory_leaks,summary_lines,"Memory Leaks")
    format_error(student.catched_errors,summary_lines,"Catched")

    # Program Outputs
    summary_lines.append("Program Outputs:")
    if student.output:
        for program, output in student.output:
            summary_lines.append(f"\tOutput for {program}:")
            # Show first few lines of output with an indication there's more
            output_preview = "\n".join(output.splitlines()[:7])
            summary_lines.extend(["\t\t" + line for line in output_preview.splitlines()])
            summary_lines.append("\t\t... (more lines follow)")
    else:
        summary_lines.append("\tNone")
    summary_lines.append("")

    # Final summary
    summary_lines.extend([
        f"Extraction Penalty: {student.extraction_penalty}",
        f"Final Grade: {student.grade - student.extraction_penalty}",
        "=" * 80
    ])

    return "\n".join(summary_lines)

def display_statistics(students, total_count):
    total_compilation_errors = 0
    total_warnings = 0
    total_memory_leaks = 0
    total_grades = 0
    total_catched_errors = 0
    for student in students:
        total_compilation_errors += len(student.compilation_errors)
        total_warnings += len(student.warning_messages)
        total_memory_leaks += len(student.memory_leaks)
        total_grades += student.grade
        total_catched_errors += len(student.catched_errors)
    average_grade = total_grades / len(students) if students else 0

    print("\n----- Statistics Summary -----")
    print(f"Total students processed: {total_count}")
    print(f"Total students with submissions: {len(students)}")
    print(f"Total compilation errors: {total_compilation_errors}")
    print(f"Total warnings: {total_warnings}")
    print(f"Total memory leaks detected: {total_memory_leaks}")
    print(f"Total catched errors: {total_catched_errors}")
    print(f"Average grade: {average_grade:.2f}")
    print("--------------------------------\n")

