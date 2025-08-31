# my-local-ai

A solution to run an AI LLM on your local machine based on docker containers, using the ollama and streamlit tools.

## Build Streamlit Front-End container image

If it's not there already, create a symlink from the app config version you want to use to 'app.py', e.g.:
```
ln -s app-v4.py app.py
```

Build the docker container, e.g. 
```
docker build -t streamlit-front-end:latest streamlit-front-end/.
```

## Run docker compose

To launch and detach:
```
docker compose up -d
```

To launch and see log output:
```
docker compose up
```

## Load the model

Instruct Ollama to load and serve the model:
```
docker exec -it ollama ollama pull llama3.1:8b
```

## Launch web front-end

* Open preferred web browser on your local machine and navigate to 'http://localhost:8501'
* Send test chat message - e.g. 'test' - to check that the model is responding
