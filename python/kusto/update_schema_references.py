#!/usr/bin/env python3
"""
YML Processor CLI

This tool processes YML files based on a list of names from an input file.
"""

import argparse
import os
import sys

def find_prefix(s: str, prefix: str) -> bool:
     # Look for database qualifier pattern
    if prefix in s:
        # If we find the database pattern, check if it's properly connected to the function
        # by finding the last occurrence of the pattern and checking what follows
        pattern_pos = s.rfind(prefix)
        after_pattern = s[pattern_pos + len(prefix):]

        # If there's only whitespace and a dot connecting the db qualifier to the function,
        # then the function is already qualified
        if after_pattern.strip() in ('', '.'):
            return True
    return False

def main(data_folder: str, yml_folder: str) -> int:
    """Main entry point for the CLI."""
    assert(os.path.isdir(data_folder)), f"Data folder '{data_folder}' does not exist or is not a directory."
    assert(os.path.isdir(yml_folder)), f"YML folder '{yml_folder}' does not exist or is not a directory."

    # Get datasource name from data_folder
    datasource = data_folder.strip(os.sep).split(os.sep)[-2]

    # Load the list of names from the input file
    functions = []
    for _, _, files in os.walk(data_folder):
        for file in files:
            if not file.endswith('.yml'):
                continue
            functions.append(os.path.splitext(file)[0])  # Store function names without .yml extension

    # Walk files, replace all instances of function name with database qualified versions
    for root, _, files in os.walk(yml_folder):
        for file in files:
            if not file.endswith('.yml'):
                continue
                
            file_path = os.path.join(root, file)
                
            # Read entire file content
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # Replace function names with qualified versions, line by line
                modified_lines = []
                file_modified = False
                discovered_let_statements = []
                for line_number, line in enumerate(lines):
                    modified_line = line
                    for function in functions:
                        # If we have already discovered this function in a let statement,
                        # skip further processing for this function
                        if function in discovered_let_statements:
                            continue

                        prefix = f"database('{datasource}')"
                        qualified_function = f"{prefix}.{function}"
                        
                        # Skip if the qualified version already exists in this line
                        if qualified_function in modified_line:
                            continue
                        
                        # Find all occurrences of the function name
                        index = 0
                        while index < len(modified_line):
                            index = modified_line.find(function, index)
                            if index == -1:
                                break
                                
                            # Check if this function name might already be qualified
                            replace = True
                            decision = False
                            rev_line_number = line_number
                            rev_line = lines[rev_line_number]
                            rev_index = index # use this index initially
                            while not decision and rev_line_number >= 0:
                                for i in range(rev_index - 1, - 1, -1):
                                    c = rev_line[i]
                                    if c.isspace(): 
                                        continue

                                    # check for `let` statement
                                    if c == 't' and i >= 3 and rev_line[i-2:i+1] == 'let':
                                        replace = False # this is a let statement, do not replace
                                        decision = True
                                        discovered_let_statements.append(function)
                                        break

                                    replace = c != '.' # this is the only allowable character
                                    decision = True
                                    break
                                rev_line_number -= 1
                                rev_line = lines[rev_line_number]
                                rev_index = len(rev_line) - 1

                            if replace:
                                # Replace this occurrence with the qualified version
                                modified_line = modified_line[:index] + qualified_function + modified_line[index + len(function):]
                                file_modified = True
                                # Skip ahead to avoid infinite loop
                                index += len(qualified_function)
                            else:
                                # If we found a non-whitespace character before the function name, skip this occurrence
                                index += len(function)

                            # If we found a let statement, no need to check further for this function in this line
                            if function in discovered_let_statements:
                                break

                    # Append the modified line to the list 
                    modified_lines.append(modified_line)
                
                # Only write back if changes were made
                if file_modified:
                    with open(file_path, 'w') as f:
                        f.writelines(modified_lines)
                    print(f"  - modified {file_path}")
                        
            except Exception as e:
                print(f"Error processing {file_path}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Add qualifier to function names in YML files based on a list of names.')
    parser.add_argument('data_folder', help='Folder containing functions for a given datasource')
    parser.add_argument('yml_folder', help='Folder containing new functions to process')
    args = parser.parse_args()
    sys.exit(main(args.data_folder, args.yml_folder))
