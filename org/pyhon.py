import os
import random
import string
import time
import concurrent.futures
from github import Github, GithubException

# Global constants for retry behavior.
MAX_RETRIES = 3         # Maximum number of global retry rounds.
RETRY_DELAY = 5         # Delay in seconds between each retry round.
RATE_LIMIT_DELAY = 60   # Extra delay in seconds if a 403 Forbidden is encountered.

def read_config():
    """
    Reads configuration values from a file named 'config.txt' located in the same folder as this script.
    The file should have lines in key=value format.
    Lines starting with '#' or blank lines are ignored.
    """
    # Get the current folder where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.txt")
    
    if not os.path.exists(config_path):
        print(f"Config file '{config_path}' not found. Please create one with the required configurations.")
        exit(1)
    
    config = {}
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config

def random_string_newlined(length):
    """
    Generates a random string of the specified length where each character is on its own line.
    For example, if length is 3, a possible output is:
      A
      7
      %
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    return "\n".join(random.choice(characters) for _ in range(length))

def create_junk_file(repo, file_index, file_size, config):
    """
    Attempts to create (or update) a junk file in the given repository.
    
    - The file name is constructed from FILE_NAME_PREFIX and FILE_EXTENSION settings.
    - The content is a randomly generated string with each character on its own line.
    
    If the file already exists (i.e. error status 409), the function retrieves the file’s current
    SHA and attempts an update. If a 403 Forbidden error is encountered, a longer delay is applied 
    before returning for a retry.
    
    Returns True on success; otherwise, returns a tuple (repo, file_index, file_size) for retry.
    """
    file_prefix = config.get("FILE_NAME_PREFIX", "junk-")
    file_ext = config.get("FILE_EXTENSION", "txt")
    file_name = f"{file_prefix}{file_index}.{file_ext}"
    content = random_string_newlined(file_size)
    commit_message = f"Add/Update file {file_name} with junk content"
    
    try:
        repo.create_file(path=file_name, message=commit_message, content=content)
        print(f"  • Created file '{file_name}' in repository '{repo.name}'")
        return True
    except GithubException as e:
        if e.status == 409:
            # File conflict: file exists. Try to update.
            try:
                current_content = repo.get_contents(file_name)
                repo.update_file(path=file_name, message=commit_message, content=content, sha=current_content.sha)
                print(f"  • Updated file '{file_name}' in repository '{repo.name}'")
                return True
            except GithubException as update_err:
                print(f"  • Error updating file '{file_name}' in repository '{repo.name}': {update_err}")
                return (repo, file_index, file_size)
        elif e.status == 403:
            # 403 Forbidden: Likely due to rate limiting or insufficient permissions.
            print(f"  • 403 Forbidden error for file '{file_name}' in repository '{repo.name}': {e}")
            print(f"    Waiting for {RATE_LIMIT_DELAY} seconds before retrying.")
            time.sleep(RATE_LIMIT_DELAY)
            return (repo, file_index, file_size)
        else:
            print(f"  • Error creating file '{file_name}' in repository '{repo.name}': {e}")
            return (repo, file_index, file_size)
    except Exception as err:
        err_str = str(err)
        if "403" in err_str:
            print(f"  • 403 Forbidden error for file '{file_name}' in repository '{repo.name}': {err}")
            print(f"    Waiting for {RATE_LIMIT_DELAY} seconds before retrying.")
            time.sleep(RATE_LIMIT_DELAY)
            return (repo, file_index, file_size)
        else:
            print(f"  • Error creating file '{file_name}' in repository '{repo.name}': {err}")
            return (repo, file_index, file_size)

def process_repo(repo_index, num_files, file_size, org, config, slow_mode):
    """
    Creates a repository (with a name, description, and privacy setting from config)
    and concurrently creates junk files within it.
    
    Returns a list of failed file creation tasks (tuples) that will be retried later.
    """
    repo_name_prefix = config.get("REPO_NAME_PREFIX", "junk-repo-")
    repo_name = f"{repo_name_prefix}{repo_index}"
    repo_description = config.get("REPO_DESCRIPTION", "Repository filled with junk content")
    private_repo = config.get("PRIVATE_REPO", "False").strip().lower() == "true"
    
    failed_files = []
    try:
        repo = org.create_repo(
            name=repo_name,
            auto_init=True,
            description=repo_description,
            private=private_repo
        )
        print(f"Created repository: {repo_name}")
        
        # For file creation, use fewer concurrent threads if in slow mode.
        max_workers_files = 1 if slow_mode else num_files
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers_files) as file_executor:
            futures = [
                file_executor.submit(create_junk_file, repo, i, file_size, config)
                for i in range(1, num_files + 1)
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result is not True:
                    failed_files.append(result)
                # If in slow mode, insert a brief delay between file tasks.
                if slow_mode:
                    time.sleep(1)
    except Exception as err:
        print(f"Error creating repository '{repo_name}': {err}")
    
    return failed_files

def retry_failed_files(failed_tasks, config, slow_mode):
    """
    Sequentially retries file creation/update tasks for any files that failed.
    Each element in failed_tasks is a tuple: (repo, file_index, file_size).
    Returns a new list of tasks that still fail after the retry.
    """
    new_failures = []
    for task in failed_tasks:
        repo, file_index, file_size = task
        if slow_mode:
            time.sleep(1)
        result = create_junk_file(repo, file_index, file_size, config)
        if result is not True:
            new_failures.append(result)
    return new_failures

def main():
    # Read configuration (config.txt must be in the same folder as this script).
    config = read_config()
    token = config.get("GITHUB_TOKEN")
    org_name = config.get("ORG_NAME")
    if not token or not org_name:
        print("Error: 'GITHUB_TOKEN' and 'ORG_NAME' must be set in config.txt")
        exit(1)
    
    try:
        github_client = Github(token)
        org = github_client.get_organization(org_name)
    except Exception as e:
        print(f"Error connecting to organization '{org_name}': {e}")
        exit(1)
    
    # Ask the user for mode selection.
    mode_input = input("Choose execution speed - Enter F for SUPER FAST or S for SLOW: ").strip().lower()
    slow_mode = True if mode_input == "s" else False
    if slow_mode:
        print("Running in SLOW mode. Concurrency is reduced and delays are added to avoid rate limiting.")
    else:
        print("Running in SUPER FAST mode. This will use maximum concurrency (use with caution).")
    
    try:
        num_repos = int(input("Enter the number of repositories to create: "))
        num_files = int(input("Enter the number of junk files per repository: "))
        file_size = int(input("Enter the number of characters (each on its own line) per junk file: "))
    except ValueError:
        print("Invalid input. Please enter valid integer values.")
        exit(1)
    
    global_failed_files = []
    # Use a reduced number of threads for repository creation when in slow mode.
    max_workers_repos = 1 if slow_mode else num_repos
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers_repos) as repo_executor:
        repo_futures = [
            repo_executor.submit(process_repo, i, num_files, file_size, org, config, slow_mode)
            for i in range(1, num_repos + 1)
        ]
        for future in concurrent.futures.as_completed(repo_futures):
            try:
                failed_files = future.result()
                if failed_files:
                    global_failed_files.extend(failed_files)
            except Exception as e:
                print(f"An error occurred during repository processing: {e}")
    
    # Global retry for failed file tasks.
    if global_failed_files:
        print(f"\nRetrying {len(global_failed_files)} failed file creation/update task(s) after a delay of {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)
        for attempt in range(MAX_RETRIES):
            print(f"\nRetry attempt {attempt + 1}:")
            global_failed_files = retry_failed_files(global_failed_files, config, slow_mode)
            if not global_failed_files:
                print("All previously failed file tasks have succeeded on retry.")
                break
            else:
                print(f"{len(global_failed_files)} file(s) still failed.")
                time.sleep(RETRY_DELAY)
        if global_failed_files:
            print(f"\nAfter {MAX_RETRIES} retry attempts, {len(global_failed_files)} file(s) still failed to be created/updated.")
    else:
        print("\nAll files created/updated successfully on the first pass.")

if __name__ == "__main__":
    main()
