import tkinter as tk
import requests
import os
import time
from datetime import datetime, timedelta

def get_authenticated_session():
    username = input("Enter your GitHub username: ")
    token = input("Enter your GitHub Personal Access Token: ")
    session = requests.Session()
    session.auth = (username, token)
    return session

def should_clone_repo(repo, session):
    # Check for at least 100 stars and last updated within four months
    if repo['stargazers_count'] < 100:
        return False

    last_update = datetime.strptime(repo['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
    four_months_ago = datetime.now() - timedelta(days=120)
    return last_update >= four_months_ago

def download_python_files(repo, target_folder, session):
    contents_url = repo['contents_url'].replace('{+path}', '')
    response = session.get(contents_url)

    if response.status_code != 200:
        print(f"Failed to retrieve repository contents: {response.status_code}")
        return

    contents = response.json()
    for content in contents:
        if content['type'] == 'file' and content['name'].endswith('.py'):
            download_file(content['download_url'], os.path.join(target_folder, content['name']), session)

def download_file(url, path, session):
    response = session.get(url)
    if response.status_code == 200:
        with open(path, 'wb') as file:
            file.write(response.content)

def clone_repositories(username, target_folder, session):
    url = f"https://api.github.com/users/{username}/repos"
    while True:
        response = session.get(url)

        if response.status_code == 200:
            repositories = response.json()
            for repo in repositories:
                if should_clone_repo(repo, session):
                    download_python_files(repo, target_folder, session)
            break
        else:
            print("Waiting for API rate limit reset... Retrying in 30 seconds.")
            time.sleep(30)

def on_submit(session):
    username = username_entry.get()
    target_folder = target_folder_entry.get()
    clone_repositories(username, target_folder, session)

session = get_authenticated_session()

root = tk.Tk()
root.title("Clone GitHub Repositories")

tk.Label(root, text="GitHub Username:").pack()
username_entry = tk.Entry(root)
username_entry.pack()

tk.Label(root, text="Target Folder:").pack()
target_folder_entry = tk.Entry(root)
target_folder_entry.pack()

tk.Button(root, text="Submit", command=lambda: on_submit(session)).pack()
