# reforged-inbox

A mighty public-inbox <-> GitHub/GitLab bridge will be there, one day.


## Deployment

### Docker compose

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
