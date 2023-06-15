FROM python:3.11-alpine

RUN apk add --no-cache git && \
    git clone https://github.com/Pikachu920/skript-doc-bot.git && \
    cd ./skript-doc-bot && \
    git fetch --tags && \
    latestTag=$(git describe --tags `git rev-list --tags --max-count=1`) && \
    git checkout $latestTag && \
    pip install --no-cache-dir -r ./requirements.txt

CMD [ "python", "./skript-doc-bot/src/main.py" ]
