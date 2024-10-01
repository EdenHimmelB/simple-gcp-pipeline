from pyspark.sql import SparkSession
import pyspark.sql.functions as F
from pyspark.sql.types import StructField, StructType, StringType, MapType
import argparse


def ndjson_to_structure_data(df):
    # Extract jobs and version from NDJSON objects.
    df1 = (
        (
            df.select(
                F.monotonically_increasing_id().alias("id"),
                F.from_json("value", schema=MapType(StringType(), StringType())).alias(
                    "col"
                ),
            )
        )
        .groupBy("id")
        .pivot("key")
        .agg(F.first("value"))
    )

    # Extract nested dump_group and dump_info from jobs column.
    df2 = (
        df1.select(
            "id",
            "version",
            F.from_json("jobs", schema=MapType(StringType(), StringType())).alias(
                "col"
            ),
        )
    ).select("id", "version", F.explode_outer("col").alias("dump_group", "dump_info"))

    # Extract relevant data from dump_info.
    df3 = (
        (
            df2.select(
                "id",
                "version",
                "dump_group",
                F.explode(
                    F.from_json(
                        "dump_info", schema=MapType(StringType(), StringType())
                    ).alias("dump_info")
                ),
            )
        )
        .groupBy("id", "version", "dump_group")
        .pivot("key")
        .agg(F.trim(F.first("value")))
    ).drop("id")

    return df3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File Conversion")
    parser.add_argument(
        "--input_path",
        type=str,
        help="Name of the NDJSON file which needs be transformed.",
    )
    parser.add_argument(
        "--output_path", type=str, help="Target Google Cloud Storage URI"
    )

    args = parser.parse_args()
    input_path = args.input_path
    output_path = args.output_path

    spark = (
        SparkSession.builder.master("local[*]")
        .appName("CSV to Parquet Conversion")
        .getOrCreate()
    )

    df = spark.read.option("multiline", "true").text(input_path)
    df = ndjson_to_structure_data(df)

    (
        df.write.format("parquet")
        .mode("overwrite")
        .option("compression", "zstd")
        .save(output_path)
    )

    spark.stop()
