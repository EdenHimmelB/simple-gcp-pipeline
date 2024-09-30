import os, logging, shutil
import requests
import pendulum
from concurrent.futures import ThreadPoolExecutor

from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from airflow.operators.python import PythonOperator

from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE")
STORAGE_BUCKET_NAME = os.getenv("GOOGLE_STORAGE_BUCKET")

TARGET_URL = os.getenv("TARGET_URL")

NDJSON_RAW_FILE_NAME = TARGET_URL.split("/")[-1]
LOCAL_NDJSON_FILE_PATH = os.path.join("data", NDJSON_RAW_FILE_NAME)
PARQUET_FOLDER_NAME = NDJSON_RAW_FILE_NAME.split(".")[0]
TABLE_SOURCE_FILE_URI = NDJSON_RAW_FILE_NAME.split(".")[0] + "/*.parquet"

CLOUD_PARQUET_FOLDER_URI = f"gs://{STORAGE_BUCKET_NAME}/{PARQUET_FOLDER_NAME}"


class MultiThreadedDownloader:
    def __init__(self, url: str, output_file, num_threads: int = 4) -> None:
        self.url = url
        self.output_file = output_file
        self.num_threads = num_threads
        self.temp_folder = "temp_folder"
        self.file_size = self._get_file_size()
        self.chunk_size = self.file_size // self.num_threads

        self.logger = logging.getLogger(__name__)

    def _get_file_size(self) -> int:
        response = requests.head(self.url)
        return int(response.headers["Content-Length"])

    def _download_chunk(self, chunk_number) -> str:
        start = chunk_number * self.chunk_size
        end = (
            start + self.chunk_size - 1
            if chunk_number < self.num_threads - 1
            else self.file_size - 1
        )

        headers = {"Range": f"bytes={start}-{end}"}
        chunk_filename = os.path.join(self.temp_folder, f"chunk_{chunk_number}")

        response = requests.get(self.url, headers=headers, stream=True)

        self.logger.info(f"Downloading")
        with open(chunk_filename, "wb") as chunk_file:
            for chunk in response.iter_content(chunk_size=8192):
                chunk_file.write(chunk)
        return chunk_filename

    def _merge_chunk(self) -> None:
        BUFFER_SIZE = 1024 * 1024  # 1MB

        self.logger.info(
            f"Merging {self.num_threads} into final file: {self.output_file}"
        )
        with open(self.output_file, "wb") as final_file:
            for i in range(self.num_threads):
                chunk_filename = os.path.join(self.temp_folder, f"chunk_{i}")
                with open(chunk_filename, "rb") as chunk_file:
                    # Implement reading and writing in small parts to prevent
                    # memory error if chunk_file is large.
                    while True:
                        chunk_data = chunk_file.read(BUFFER_SIZE)
                        if not chunk_data:
                            break
                        final_file.write(chunk_data)
        self.logger.info(f"All chunk succesfully merged into {self.output_file}")

    def _cleanup(self) -> None:
        self.logger.info("Cleaning up temporary folder.")
        shutil.rmtree(self.temp_folder)
        self.logger.info("Cleaned up temporary folder.")

    def download(self) -> None:
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)

        self.logger.info(f"Starting download with {self.num_threads} threads.")
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [
                executor.submit(self._download_chunk, i)
                for i in range(self.num_threads)
            ]
            for future in futures:
                future.result()

        self._merge_chunk()
        self._cleanup()
        self.logger.info("Complete download")


def download_data_to_local():
    downloader = MultiThreadedDownloader(TARGET_URL, LOCAL_NDJSON_FILE_PATH)
    downloader.download()


def load_parquet_to_bigquery() -> None:
    hook = BigQueryHook()
    job_config = {
        "sourceFormat": "PARQUET",
        "sourceUris": [f"gs://{STORAGE_BUCKET_NAME}/{TABLE_SOURCE_FILE_URI}"],
        "destinationTable": {
            "projectId": GOOGLE_CLOUD_PROJECT,
            "datasetId": BIGQUERY_DATASET,
            "tableId": BIGQUERY_TABLE,
        },
        "timePartitioning": {"type": "DAY", "field": "timestamp"},
        "writeDisposition": "WRITE_APPEND",
        "createDisposition": "CREATE_IF_NEEDED",
        "parquetOptions": {
            "enableListInference": True,
        },
        # Enable schema evolution by allowing new columns to be added, and allow REQUIRED column to change to NULLABLE.
        # Safe guard for schema evolution in ndjson files.
        "schemaUpdateOptions": ["ALLOW_FIELD_ADDITION", "ALLOW_FIELD_RELAXATION"],
    }
    hook.insert_job(
        configuration={"load": job_config},
        project_id=GOOGLE_CLOUD_PROJECT,
    )


def cleanup_downloaded_ndjson_file():
    shutil.rmtree(LOCAL_NDJSON_FILE_PATH)


# Making dag timezone aware.
previous_creation_day = pendulum.today(tz="Asia/Ho_Chi_Minh") - pendulum.duration(
    days=1
)
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": previous_creation_day,
    "retries": 3,
    "retry_delay": pendulum.duration(hours=1),
}

with DAG(
    dag_id="simple-gcp-pipeline",
    default_args=default_args,
    schedule_interval="0 7 * * *",  # Everyday at 07:00
) as dag:
    with TaskGroup(group_id="Ingest") as ingest_task:
        download_task = PythonOperator(
            task_id="download_data_to_local",
            python_callable=download_data_to_local,
        )
        ingest_task

    with TaskGroup(group_id="Transform") as transform_task:
        spark_transform_task = SparkSubmitOperator(
            task_id="convert_and_upload_as_parquet_to_gcs",
            application="/opt/airflow/spark-jobs/transform_enwiki_dumpstatus_metadata.py",
            name="your_spark_job_name",
            conn_id="spark_default",
            application_args=[
                "--input_path",
                LOCAL_NDJSON_FILE_PATH,
                "--output_path",
                CLOUD_PARQUET_FOLDER_URI,
            ],
            conf={
                "spark.jars": "/opt/airflow/spark-lib/gcs-connector-hadoop3-2.2.21-shaded.jar",
                "spark.hadoop.fs.gs.impl": "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem",
                "spark.hadoop.fs.AbstractFileSystem.gs.impl": "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFS",
                "fs.gs.auth.service.account.enable": "true",
                "fs.gs.auth.service.account.json.keyfile": GOOGLE_CREDENTIALS,
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
                "spark.dynamicAllocation.enabled": "true",
            },
        )
        spark_transform_task

    with TaskGroup(group_id="Load") as load_task:
        load_bigquery_table = PythonOperator(
            task_id="load_parquet_to_bigquery_custom",
            python_callable=load_parquet_to_bigquery,
        )
        load_bigquery_table

    clean_up_task = PythonOperator(
        task_id="clean_up_local_env",
        python_callable=cleanup_downloaded_ndjson_file,
    )

    ingest_task >> spark_transform_task >> load_task >> clean_up_task
