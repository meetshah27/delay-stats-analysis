# S3, Glue and Athena for the delay analysis. Every resource is tagged
# project=delay-stats-analysis so `make teardown` can prove nothing is left.
#
#   s3://<bucket>/landing/csv/year=YYYY/month=MM/      raw BTS CSV (cost comparison only)
#   s3://<bucket>/curated/parquet/year=YYYY/month=MM/  typed Parquet, what the analysis reads
#   s3://<bucket>/athena-results/                      query results, expire after 7 days
#
# Glue tables are declared here with explicit schemas (no crawler), with partition projection
# on year/month, so new months need no catalog update.

terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    key     = "delay-stats-analysis/terraform.tfstate"
    encrypt = true
  }
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "keep_csv_table" {
  description = "The raw CSV table exists only for the cost comparison; `make drop-csv` sets false."
  type        = bool
  default     = true
}

variable "bytes_scanned_cutoff" {
  description = "Athena per-query scan cap. Must exceed the full CSV table (about 10 GB)."
  type        = number
  default     = 25 * 1024 * 1024 * 1024
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "delay-stats-analysis" }
  }
}

data "aws_caller_identity" "current" {}

locals {
  bucket   = "delaystats-${data.aws_caller_identity.current.account_id}"
  database = "delaystats"
  # The analysis columns with the typed schema of ingest.py; year/month are partition keys.
  parquet_columns = {
    dayofmonth                      = "int"
    dayofweek                       = "int"
    flightdate                      = "date"
    reporting_airline               = "string"
    tail_number                     = "string"
    flight_number_reporting_airline = "int"
    origin                          = "string"
    originstate                     = "string"
    dest                            = "string"
    deststate                       = "string"
    crsdeptime                      = "int"
    depdelay                        = "int"
    crsarrtime                      = "int"
    arrdelay                        = "int"
    arrdelayminutes                 = "int"
    arrdel15                        = "int"
    cancelled                       = "int"
    cancellationcode                = "string"
    diverted                        = "int"
    distance                        = "int"
    carrierdelay                    = "int"
    weatherdelay                    = "int"
    nasdelay                        = "int"
    securitydelay                   = "int"
    lateaircraftdelay               = "int"
    primary_delay_cause             = "string"
  }
  # The raw BTS file: 109 named columns in file order, all strings (OpenCSVSerde).
  csv_columns = jsondecode(file("${path.module}/bts_csv_header.json"))
  projection = {
    "projection.enabled"      = "true"
    "projection.year.type"    = "integer"
    "projection.year.range"   = "2023,2030"
    "projection.month.type"   = "integer"
    "projection.month.range"  = "1,12"
    "projection.month.digits" = "2"
  }
}

resource "aws_s3_bucket" "data" {
  bucket        = local.bucket
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "expire-athena-results"
    status = "Enabled"
    filter {
      prefix = "athena-results/"
    }
    expiration {
      days = 7
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_glue_catalog_database" "this" {
  name = local.database
}

resource "aws_glue_catalog_table" "ontime" {
  name          = "ontime"
  database_name = aws_glue_catalog_database.this.name
  table_type    = "EXTERNAL_TABLE"
  parameters = merge(local.projection, {
    "classification"            = "parquet"
    "storage.location.template" = "s3://${local.bucket}/curated/parquet/year=$${year}/month=$${month}/"
  })
  partition_keys {
    name = "year"
    type = "int"
  }
  partition_keys {
    name = "month"
    type = "int"
  }
  storage_descriptor {
    location      = "s3://${local.bucket}/curated/parquet/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    dynamic "columns" {
      for_each = local.parquet_columns
      content {
        name = columns.key
        type = columns.value
      }
    }
  }
}

# Cost comparison only; dropped with its S3 prefix after `make cost-compare`.
resource "aws_glue_catalog_table" "ontime_csv" {
  count         = var.keep_csv_table ? 1 : 0
  name          = "ontime_csv"
  database_name = aws_glue_catalog_database.this.name
  table_type    = "EXTERNAL_TABLE"
  parameters = merge(local.projection, {
    "classification"            = "csv"
    "skip.header.line.count"    = "1"
    "storage.location.template" = "s3://${local.bucket}/landing/csv/year=$${year}/month=$${month}/"
  })
  partition_keys {
    name = "year"
    type = "int"
  }
  partition_keys {
    name = "month"
    type = "int"
  }
  storage_descriptor {
    location      = "s3://${local.bucket}/landing/csv/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"
      parameters            = { separatorChar = ",", quoteChar = "\"" }
    }
    dynamic "columns" {
      for_each = local.csv_columns
      content {
        name = lower(columns.value)
        type = "string"
      }
    }
  }
}

resource "aws_athena_workgroup" "this" {
  name          = "delaystats-wg"
  force_destroy = true
  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff
    result_configuration {
      output_location = "s3://${local.bucket}/athena-results/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

output "bucket" {
  value = aws_s3_bucket.data.bucket
}

output "glue_database" {
  value = aws_glue_catalog_database.this.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.this.name
}
