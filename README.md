# my-local-ai

A solution to run an AI LLM on your local machine based on docker containers, using the ollama and streamlit tools.

## Build Streamlit Front-End container image

Build the docker container - e.g. docker build -t streamlit-front-end:latest streamlit-front-end/.

## Run docker compose

To launch and detach: 'docker compose up -d'

To launch and see log output: 'docker compose up'
