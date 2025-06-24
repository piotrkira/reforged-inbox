# Reforged Inbox ⚒️🔥📬

Reforged Inbox is a mighty public-inbox <-> GitHub/GitLab bridge.

## ⭐ Features

* Syncing patches from public-inbox to GitHub/GitLab
* Web UI for viewing status of patches
* Error notifications via email

## ⚓ How to Deploy

### 🐋 Docker Compose

1. Create a directory for the project and navigate into it:

   ```bash
   mkdir reforged-inbox && cd reforged-inbox
   ```
2. Configure the _reforged.toml_ file with your settings.
3. Copy the example docker-compose file and modify it as needed, make sure to mount the configuration file:

   ```bash
   cp docker-compose.example.yml docker-compose.yml
   ```
4. Start the application using Docker Compose:

   ```bash
    docker-compose up -d
    ```

## ⚙️ Configuration

Take a look at `reforged.example.toml` file for example configuration.
