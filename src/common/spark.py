from pyspark.sql import SparkSession


def get_spark(local: bool = False):
    if not local:
        return SparkSession.builder.getOrCreate()
    return (SparkSession.builder.master("local[2]").appName("supply-risk-local")
            .config("spark.sql.warehouse.dir", "/tmp/supply-risk-warehouse")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "4")
            .getOrCreate())
