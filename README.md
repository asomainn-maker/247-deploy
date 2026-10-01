```

██████╗ ██╗  ██╗███████╗      ██████╗ ███████╗██████╗ ██╗      ██████╗ ██╗   ██╗
╚════██╗██║  ██║╚════██║      ██╔══██╗██╔════╝██╔══██╗██║     ██╔═══██╗╚██╗ ██╔╝
 █████╔╝███████║    ██╔╝█████╗██║  ██║█████╗  ██████╔╝██║     ██║   ██║ ╚████╔╝ 
██╔═══╝ ╚════██║   ██╔╝ ╚════╝██║  ██║██╔══╝  ██╔═══╝ ██║     ██║   ██║  ╚██╔╝  
███████╗     ██║   ██║        ██████╔╝███████╗██║     ███████╗╚██████╔╝   ██║   
╚══════╝     ╚═╝   ╚═╝        ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝    ╚═╝   
                                                                                 
```
# 247-deploy

Run any script (Python, Bash, Node, etc.) 24/7 for free using GitHub Actions. Fork, add your code as a secret, and it runs automatically every 6 hours. No servers, no setup. Push your code and it runs forever.

---

## What This Does

247-deploy is a lightweight automation tool that runs scripts on GitHub's Actions infrastructure. Your script is stored as a base64-encoded secret, which means it is never visible in the repository itself. The workflow decodes the secret at runtime and executes it on a repeating schedule.

The result is a free, always-on execution environment for small scripts, bots, and automation tasks that would otherwise require a VPS or a paid cloud host.

---

## Requirements

- A GitHub account
- Python 3.8 or higher installed locally (needed for the splitter tool)
- A script you want to run (Python, Bash, Node, etc.)
- Optional: a requirements.txt file if your script needs dependencies

---

## Setup

### 1. Fork this repository

Click the Fork button in the top right corner of this page.

### 2. Get the splitter tool

Download tools/split.py from this repository to your local machine.

Or clone the entire repository:

```
git clone https://github.com/YOUR_USERNAME/247-deploy.git
cd 247-deploy
```

### 3. Encode your script

Open a terminal in the folder containing your script.

Run the splitter:

```
python tools/split.py discordbot.py
```

Replace your_script.py with the actual name of your script.

The splitter will:

- Read your file
- Convert it to base64
- Split it into chunks if needed
- Create a chunks folder with the output
- Print instructions for adding secrets

Example output:

```
============================================================
                    247-deploy Splitter
============================================================

File: /home/user/large_app.py
Original size: 55,672 bytes (54.37 KB)
Encoded size: 74,232 bytes (72.49 KB)
Chunk size: 45 KB
Total chunks: 2

Chunks written to:
  chunks/large_app_chunk_1.txt
  chunks/large_app_chunk_2.txt

GitHub Secrets to create:
--------------------------------------------------------
  APP_CODE_1: (paste contents of chunks/large_app_chunk_1.txt)
  APP_CODE_2: (paste contents of chunks/large_app_chunk_2.txt)
--------------------------------------------------------

Quick commands (GitHub CLI):
--------------------------------------------------------
  gh secret set APP_CODE_1 < chunks/large_app_chunk_1.txt
  gh secret set APP_CODE_2 < chunks/large_app_chunk_2.txt
--------------------------------------------------------

The workflow will automatically reassemble these chunks in order.
```

### 4. Add your code as secrets

Go to your forked repository on GitHub.

Navigate to Settings, then Secrets and variables, then Actions.

Click New repository secret.

For each chunk file created by the splitter:

- First chunk: Name = APP_CODE_1, Value = contents of chunk_1.txt
- Second chunk: Name = APP_CODE_2, Value = contents of chunk_2.txt
- Third chunk: Name = APP_CODE_3, Value = contents of chunk_3.txt
- Continue until all chunks are added

If your script produced only one chunk, use APP_CODE as the secret name instead.

### 5. Run the workflow

1. Go to the Actions tab.
2. Select 247 Deploy from the left sidebar.
3. Click Run workflow.
4. Wait a few seconds. Your script is now running.

The workflow will automatically restart every 6 hours.

---

## Splitting Large Scripts

GitHub limits secrets to 48 KB each. If your encoded script exceeds this limit, the splitter automatically divides it into multiple chunks.

To test chunking on a smaller file:

```
python tools/split.py your_script.py --chunk-size 10
```

This forces the splitter to use 10 KB chunks instead of 45 KB, which is useful for testing.

To create a larger test file from an existing script:

Windows:

```
copy large_test_bot.py + large_test_bot.py + large_test_bot.py triple_bot.py
```

Linux/Mac:

```
cat large_test_bot.py large_test_bot.py large_test_bot.py > triple_bot.py
```

---

## Optional Configuration

### Dependencies (APP_REQS)

If your script requires Python packages, create a requirements.txt file, encode it the same way, and add it as a secret named APP_REQS.

### Environment Variables (APP_ENV)

If your script needs environment variables, create a .env file, encode it, and add it as a secret named APP_ENV.

---

## How It Works

The workflow file (.github/workflows/loader.yml) triggers on a cron schedule every 6 hours. When it runs:

1. It checks for APP_CODE_1. If present, it collects all chunks in sequence.
2. If APP_CODE_1 is missing but APP_CODE exists, it uses the single chunk directly.
3. It concatenates all chunks and decodes them from base64.
4. It writes the decoded data to a file.
5. It installs dependencies if APP_REQS is present.
6. It loads environment variables if APP_ENV is present.
7. It executes the script and keeps it alive until the next cycle.

---

## Limits

- Secrets are limited to 48 KB each. Scripts larger than 48 KB must be split into chunks.
- Up to 100 secrets per repository. Maximum script size with chunking is approximately 4.8 MB.
- The workflow has a 6-hour timeout. Scripts are restarted automatically after each cycle.

---

## Roadmap

- Multi-file project support (zip upload)
- Language auto-detection
- Custom cron schedules
- Persistent storage via GitHub cache

---

## License

MIT

---
## Documentation

See docs/SETUP.md for detailed setup instructions and examples.
