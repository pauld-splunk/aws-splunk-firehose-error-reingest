# Lambda Function to Re-Ingest Failed Firehose output to Splunk from S3 via Firehose

This function is a sample lambda function to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose back via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

This function is a simple solution to allow a re-ingest process to be possible. It should be triggered from these failed objects in S3, and will read and decode the payload, writing the output back into Firehose (same one or a different specific one to re-ingest, e.g. to a different Splunk instance). Care should be taken if re-ingesting back into the same Firehose in case that the reasons for failure to write to Splunk are not related to connectivity (you could flood your Firehose with a continuous error loop).

Note that this is a template example, that is based on re-ingesting from a Firehose configuration set up using Project Trumpet. The format of the json messages that may come in via a different set-up may need some small changes to the construct of the re-ingested json payload.
(see Project Trupet here - https://github.com/splunk/splunk-aws-project-trumpet)

Note that the "Splashback" S3 bucket where Firehose sends the failed messages also contains objects (with different prefixes) that would not necessarily be suitable to ingest from - for example, if there is a pre-processing function set up (a lambda function for the Firehose), the failiure could be caused there - these events will have a "processing-failed/" prefix. As additional processing would have been done to the payloads of these events, the contents of the "raw" event may not be what you wish to ingest into Splunk. This is why the Event notification for these functions should always include the prefix "splunk-failed/" to ensure that only those with a completed processing are read into Splunk via this "splashback" route.

## Setup Process

1. Create a new AWS Lambda Function <br>
(Author from scratch)<br>
Select Python 3.8 as the runtime<br>
Permissions - <br>
Create a new role from AWS policy templates<br>
Give it a Role Name<br>
Select "Amazon S3 object read-only permissions" from the Policy Templates<br>

Click on "Create function"

2. Update Permissions<br>
We will need to edit the policy to add write permission to Firehose<br>
On your new function, select the "Permissions" tab, and click on the Execution role Role name (it will open up a new window with IAM Manager)<br>
In the Permissions Tab, you will see two attached policies, click "Add inline policy". <br>
In the Visual Editor add the following:<br>
Service - Firehose<br>
Actions - Write - PutRecordBatch<br>
Resources - Either enter the ARN for your Firehose OR tick the "Any in this account"<br>

Click Review Policy, and Save Changes

3. Copy the function code<br>
Copy the function code from this repo, and replace/paste into your lambda function code, and then Deploy

4. Create Event on S3 Bucket<br>
Navigate to your AWS S3 Firehose Error bucket in the console<br>
On the Properties of the Bucket, Create event notification.<br>
Give the event notification a name, and ensure you add the prefix "splunk-failed/" <br>
(note if you have added another prefix in your Firehose configuration, you will need to add that to this prefix, for example if you added FH as the prefix in the firehose config, you will need to add "FHsplunk-failed/" here)<br>
Select the "All object create events" check box.<br>
Select "Lambda Function" as the Destination, and select the Lambda Function you created in step 1 from the dropdown.<br>
Save Changes<br>

You are now all set with the function.

Note if you wish to use a different Firehose to re-ingest the data, you will need to have created this before Step 1.

# Alternative Options

This example describes how the function can be triggered by the "error" objects being written to the Splashback S3 bucket. If there is a prolonged time of no connection to Splunk HEC, this could result in huge loops of data being re-ingested to Firehose. In most cases, the connectivity outage is short, and wouldn't cause issues. Where these cases are more likely to occur, it may be worth doing a mix of the two options provided here. Stage 1 re-try would use the S3->Firehose method, but sending the "re-try" to a different, dedicated firehose. That firehose could then have its "Splashback" S3 bucket linked to the second solution which would copy the 2nd attempted failed events to an S3 bucket that could use the AWS Add-On as the "final route" into Splunk, possibly as a "manual recovery" process.

# Current Limitations

The function will allow the extraction of messages that have been wrapped with additional metadata (noting sourcetype is set with a Project Trumpet configured firehose). This generally happens when a the lambda function in the Kinesis Firehose processing adds the additional information. As the re-ingest process through Firehose will also add its own event metadata,  only CloudTrail and ConfigNotifications are set with the correct sourcetpe with this function - you will need to add further ones as required.

The function does not take into consideration a "loop" scenario where data will continiously re-ingest if there is no way of connecting back to Splunk HEC. This could essentially build up significant volumes in re-ingest and max-out the Firehose capacity.


