# Lambda Function to Ingest S3 Failed Firehose output to Splunk

This function is a same lambda function to assist with ingesting logs from AWS that failed to write via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded.

This function should be triggered from these failed objects, and will read and decode the payload, writing the output back into S3 (same bucket) in another prefixed object with *rawFailed/*. (Note that the event on the S3 bucket should exclude that prefix!)

These objects can then be ingested by the AWS Splunk Add-On using an SQS-based S3 input.


