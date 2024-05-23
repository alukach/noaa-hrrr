FROM continuumio/miniconda3 as base

COPY environment.yml ./
RUN conda update conda && \
    conda env update -f environment.yml -n base && \
    conda clean -af


FROM base as dependencies

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /opt/stactools-noaa-hrrr
COPY --from=base /opt/conda /opt/conda
COPY pyproject.toml ./
COPY src/stactools/noaa_hrrr/__init__.py src/stactools/noaa_hrrr/
RUN apt-get -y -q update \
    && apt-get -y -q install build-essential \
    && rm -rf /var/lib/apt/lists/
RUN python -m venv /opt/venv
RUN pip install . \
    && ls /opt/venv \
    && rm -r /opt/venv/lib/python3.11/site-packages/stactools/noaa_hrrr


FROM dependencies as builder

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /opt/stactools-noaa-hrrr
COPY --from=base /opt/conda /opt/conda
COPY --from=dependencies /opt/venv /opt/venv
COPY pyproject.toml ./
COPY src ./src
RUN pip install -U pip \
    && pip install .
WORKDIR /
RUN rm -rf /opt/stactools-noaa-hrrr
CMD [ "stac", "noaahrrr" ]


FROM dependencies as dev-dependencies

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /opt/stactools-noaa-hrrr
COPY --from=dependencies /opt/venv /opt/venv
COPY pyproject.toml .
RUN pip install -e '.[dev]' \
    && git init


FROM dev-dependencies as dev-builder

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /opt/stactools-noaa-hrrr
COPY --from=base /opt/conda /opt/conda
COPY --from=dependencies /opt/venv /opt/venv
COPY . .
CMD [ "stac", "noaahrrr" ]
