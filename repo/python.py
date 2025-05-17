import os
import random
import string
import time
import concurrent.futures
from github import Github, GithubException

def read_config():
    """
    Reads configuration values from a file named 'config.txt' located in the same folder as this script.
    The file should use lines in key=value format. Lines beginning with '#' or blank lines are ignored.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.txt")
    
    if not os.path.exists(config_path):
        print(f"Config file '{config_path}' not found. Please ensure it is in the same folder as this script.")
        exit(1)
    
    config = {}
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config

def random_string_newlined(length):
    """
    Generates a random string of the specified length where each character appears on its own line.
    
    For example, if length is 3 a possible output is:
      A
      7
      %
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return "\n".join(random.choice(characters) for _ in range(length))

def create_junk_file(repo, file_index, file_size, config):
    """
    Attempts to create (or update) a junk file in the specified repository.
    
    - The file name is constructed using FILE_NAME_PREFIX and FILE_EXTENSION from the config.
    - The junk file's content is a random string with each character on its own line.
    
    If the file already exists (error 409), the script retrieves the current SHA and updates the file.
    If a 403 error is encountered, a delay is applied before retrying the update.
    """
    file_prefix = config.get("FILE_NAME_PREFIX", "junk-")
    file_ext = config.get("FILE_EXTENSION", "txt")
    file_name = f"{file_prefix}{file_index}.{file_ext}"
    content = random_string_newlined(file_size)
    commit_message = f"Add/Update file {file_name} with junk content"
    
    try:
        repo.create_file(path=file_name, message=commit_message, content=content)
        print(f"Created file '{file_name}' in repository '{repo.name}'.")
    except GithubException as e:
        if e.status == 409:
            # File already exists; attempt update.
            try:
                current_content = repo.get_contents(file_name)
                repo.update_file(path=file_name, message=commit_message,
                                 content=content, sha=current_content.sha)
                print(f"Updated file '{file_name}' in repository '{repo.name}'.")
            except GithubException as update_err:
                print(f"Error updating file '{file_name}' in repository '{repo.name}': {update_err}")
        elif e.status == 403:
            # 403 Forbidden: likely due to rate limiting or permission issues.
            print(f"403 Forbidden error for file '{file_name}' in repository '{repo.name}': {e}")
            print("Waiting 60 seconds before retrying the update.")
            time.sleep(60)
            try:
                current_content = repo.get_contents(file_name)
                repo.update_file(path=file_name, message=commit_message,
                                 content=content, sha=current_content.sha)
                print(f"Updated file '{file_name}' after delay in repository '{repo.name}'.")
            except GithubException as update_err:
                print(f"Error updating file '{file_name}' after delay in repository '{repo.name}': {update_err}")
        else:
            print(f"Error creating file '{file_name}' in repository '{repo.name}': {e}")

def main():
    # Read configuration from config.txt (which must be in the same folder as this script).
    config = read_config()
    token = config.get("GITHUB_TOKEN")
    repo_name = config.get("REPO_NAME")
    
    if not token or not repo_name:
        print("Error: GITHUB_TOKEN and REPO_NAME must be set in config.txt")
        exit(1)
    
    # Connect to GitHub using your token.
    try:
        github_client = Github(token)
        user = github_client.get_user()
    except Exception as e:
        print(f"Error connecting to GitHub: {e}")
        exit(1)
    
    # Try to retrieve the repository; if it doesn't exist, create it.
    try:
        repo = user.get_repo(repo_name)
        print(f"Repository '{repo_name}' found on your user account.")
    except GithubException as e:
        print(f"Repository '{repo_name}' not found. Attempting to create it.")
        try:
            repo = user.create_repo(
                name=repo_name,
                description=config.get("REPO_DESCRIPTION", "Repository filled with junk content"),
                private=config.get("PRIVATE_REPO", "False").strip().lower() == "true",
                auto_init=True
            )
            print(f"Created repository '{repo_name}'.")
        except GithubException as create_err:
            print(f"Error creating repository '{repo_name}': {create_err}")
            exit(1)
    
    # Ask the user for the execution mode.
    mode_input = input("Choose execution speed - Enter F for SUPER FAST or S for SLOW: ").strip().lower()
    slow_mode = True if mode_input == "s" else False
    if slow_mode:
        print("Running in SLOW mode. Concurrency is reduced and delays are added to avoid rate limiting.")
    else:
        print("Running in SUPER FAST mode. This will use maximum concurrency (use with caution).")
    
    # Prompt for the junk file details.
    try:
        num_files = int(input("Enter the number of junk files to create/update: "))
        file_size = int(input("Enter the number of characters (each on its own line) per junk file: "))
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        exit(1)
    
    # Adjust the number of threads based on the mode.
    max_workers = 1 if slow_mode else num_files

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(create_junk_file, repo, i, file_size, config)
            for i in range(1, num_files + 1)
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"An error occurred during file processing: {e}")
            if slow_mode:
                time.sleep(1)
    
if __name__ == "__main__":
    main()
