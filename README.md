# Lambda Functions to Re-Ingest Failed Firehose output to Splunk from S3

The functions provided here are sample lambda functions to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. The "timeout" or "Retry duration" period before Firehose writes out to S3 is defined in the Firehose settings - default is 300 seconds (can be set from 0 to 7200s). However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

These functions are simple example solutions to allow 2 different ingest processes to be possible - one via the AWS Add-On, and the other to re-ingest the errors back via Firehose. 

The Add-On re-ingest route should be triggered from event notifications from these failed objects, and will read and decode the payload, writing the output back into S3 (same bucket) in another prefixed object with **SplashbackRawFailed/**. (Note that the event on the S3 bucket should exclude that prefix!)

The Firehose re-ingest route can be triggered from event notifications from these failed objects. The documented suggestion here is simply using the event notifications (which will already be delayed by Firehose itself retrying) - so this should give some element of time to "recover" connectivity issues. The function will re-try ingestion a set number of times before eventually writing out to S3. 

Note that the S3 bucket where Firehose sends the failed messages also contains objects (with different prefixes) that would not necessarily be suitable to ingest from - for example, if there is a pre-processing function set up (a lambda function for the Firehose), the failiure could be caused there - these events will have a "processing-failed/" prefix. As additional processing would have been done to the payloads of these events, the contents of the "raw" event may not be what you wish to ingest into Splunk. This is why the Event notification for these functions should always include the prefix "splunk-failed/" to ensure that only those with a completed processing are read into Splunk via this "splashback" route.

Note that these functions require certain configuration setup of Firehose to function properly. If you have issues with configuration, you may need to update according to how your Firehose configurations worked. The examples originally used Project Trumpet as a "base" configurator of Firehose. The main reason for failures are that the format of the log that drops into S3 from Firehose will potentially vary depending on whether the output was sent as "RAW" or "EVENT".

*DATA MANAGER UPDATE*

With Splunk Data Manager now able to create all of the configuration on the Firehose side for many AWS inputs, new updated functions are available in this library to support Firehose setups that used DM. These should also work for generic Firehose configurations.






