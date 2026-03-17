FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY setup.cfg setup.py ./
COPY src/ src/

ENV SETUPTOOLS_SCM_PRETEND_VERSION=1.0.0

RUN pip install --no-cache-dir "setuptools<72" && pip install --no-cache-dir -e .

EXPOSE 8101

WORKDIR /ledger

CMD ["python", "/app/src/beancount_importers/beancount_import_run.py", \
     "--journal_file", "main.bean", \
#     "--data_dir", "/data", \
#     "--output_dir", "/output", \
     "--address", "0.0.0.0", \
     "--importers_config_file", "importers_config.yml"]

