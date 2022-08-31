# Lambda Function to Re-Ingest Failed Firehose output to Splunk from S3 Via Add-On

This function is a sample lambda function to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose back using the AWS Add-On.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

This function is a simple solution to allow a re-ingest process to be possible. It should be triggered from these failed objects in S3, and will read and decode the payload, writing the output back into S3 (same bucket) in another prefixed object with **SplashbackRawFailed/**. (Note that the event on the S3 bucket should exclude that prefix!)

These objects can then be ingested by the AWS Splunk Add-On using an SQS-based S3 input.

For events that are set up and sent as "Events" to Splunk, (example Cloudwatch logs when set up with Data Manager) the event payload that is decoded into the S3 bucket will be in full "HEC Event" format (i.e. wrapped in JSON). Additional props/transforms will be required to ingest this into Splunk to provide the "event" data. Note that additional metadata is associated with this JSON such as the Data Manager id, index, source etc.

Note that the "Splashback" S3 bucket where Firehose sends the failed messages also contains objects (with different prefixes) that would not necessarily be suitable to ingest from - for example, if there is a pre-processing function set up (a lambda function for the Firehose), the failiure could be caused there - these events will have a "processing-failed/" prefix. As additional processing would have been done to the payloads of these events, the contents of the "raw" event may not be what you wish to ingest into Splunk. This is why the Event notification for these functions should always include the prefix "splunk-failed/" to ensure that only those with a completed processing are read into Splunk via this "splashback" route.

* **Sample sourcetype Update for Data Manager** *
If this function is used with Data Manager, CloudTrail events (or other JSON only sources) will be able to be read directly from the recovery S3 bucket as there is no change to the actual event sourcetype. However, for CloudWatch logs, the "recovered" events are wrapped with HEC event format, and therefore will require some "extration" to get the actual event. A sample props and transforms is available here - if you add these to where the AWS Add-On is installed (e.g. HF or private app on Splunk cloud) in  local/props.conf and local/transforms.conf, and set the S3 input (SQS-S3 based input) on the Add-On to use the sourcetype of aws:cloudwatchlogs:recovered, the transforms will extract all of the metadata and event data and convert the sourcetype back into aws:cloudwatch logs. (note that the escape characters in this example will not be transformed/removed - ammend the transforms accordingly if you wish to do so)


## Setup Process

1. Create a new AWS Lambda Function<br>
(Author from scratch)<br>
Select Python 3.9 (or latest supported) as the runtime<br>
Permissions - <br>
Create a new role from AWS policy templates<br>
Give it a Role Name<br>
Select "Amazon S3 object read-only permissions" from the Policy Templates<br>

Click on "Create function"

2. Update Permissions<br>
We will need to edit the policy to add write permission<br>
On your new function, select the "Permissions" tab, and click on the Execution role Role name (it will open up a new window with IAM Manager)<br>
In the Permissions Tab, you will see two attached policies, Click on the arrow next to the AWSLambdaS3ExecutionRole-xxxxx Policy<br>
Edit the Policy, and use the JSON view.<br>
Add "s3:PutObject" into the policy: it should now look like this:<br>

<pre>
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::*"
        }
    ]
}
</pre>

Click Review Policy, and Save Changes

3. Copy the function code<br>
Copy the function code from this repo, and replace/paste into your lambda function code, and then Deploy<br>

4. Create Event on S3 Bucket<br>
Navigate to your AWS S3 Firehose Error bucket in the console<br>
On the Properties of the Bucket, Create event notification.<br>
Give the event notification a name, and ensure you add the prefix "splunk-failed/" <br>
(note if you have added another prefix in your Firehose configuration, you will need to add that to this prefix, for example if you added FH as the prefix in the firehose config, you will need to add "FHsplunk-failed/" here)<br>
Select the "All object create events" check box.<br>
Select "Lambda Function" as the Destination, and select the Lambda Function you created in step 1 from the dropdown.<br>
Save Changes<br>

You are now all set with the function.

You will need to now follow the set-up process defined in the Add-On documentation on how to read these processed S3 objects into Splunk. see here https://docs.splunk.com/Documentation/AddOns/released/AWS/SQS-basedS3) <br>

**Important: Remember to set the prefix "SplashbackRawFailed/" in the event notification for the SNS set up for the Add-On, otherwise it will attempt to read ALL objects from that bucket.**


# Current Limitations

The function will allow the extraction of messages that have been wrapped with additional metadata (noting sourcetype is set with a Project Trumpet configured firehose). This generally happens when a the lambda function in the Kinesis Firehose processing adds the additional information. As the SQS-based S3 input on the add-on will add its own event metadata, only the raw payload is extracted from these failed events.
If there are more than one sourcetypes coming in through the firehose stream, it would not be possible to have one S3 input on the add-on to handle this (unless there are props/transforms on the input sourcetype to split this out).
A suggested workaround is to extend the function here to split out the sourcetype from the additional metadata (currently only the message is extracted by the test_event function), and add this additional "sourcetype" to the prefix of the object key being re-written to S3 - e.g. the object key could be SplashbackRawFailed/sourcetype/originalkey. The SQS-based S3 input could then be linked to the correct sourcetypes in the bucket.



