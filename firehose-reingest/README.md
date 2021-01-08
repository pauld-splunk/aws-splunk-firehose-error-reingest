# Lambda Function to Re-Ingest Failed Firehose output to Splunk from S3 via Firehose

This function is a sample lambda function to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose back via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

This function is a simple solution to allow a re-ingest process to be possible. It should be triggered from these failed objects in S3, and will read and decode the payload, writing the output back into Firehose (same one or a different specific one to re-ingest, e.g. to a different Splunk instance). Care should be taken if re-ingesting back into the same Firehose in case that the reasons for failure to write to Splunk are not related to connectivity (you could flood your Firehose with a continuous error loop).

Note that this is a template example, that is based on re-ingesting from a Firehose configuration set up using Project Trumpet. The format of the json messages that may come in via a different set-up may need some small changes to the construct of the re-ingested json payload.
(see Project Trupet here - https://github.com/splunk/splunk-aws-project-trumpet)

Note that the S3 bucket where Firehose sends the failed messages also contains objects (with different prefixes) that would not necessarily be suitable to ingest from - for example, if there is a pre-processing function set up (a lambda function for the Firehose), the failiure could be caused there - these events will have a "processing-failed/" prefix. As additional processing would have been done to the payloads of these events, the contents of the "raw" event may not be what you wish to ingest into Splunk. This is why the Event notification for these functions should always include the prefix "splunk-failed/" to ensure that only those with a completed processing are read into Splunk via this "splashback" route.

## Setup Process

1. Create a new AWS Lambda Function
(Author from scratch)
Select Python 3.8 as the runtime
Permissions - 
Create a new role from AWS policy templates
Give it a Role Name
Select "Amazon S3 object read-only permissions" from the Policy Templates

Click on "Create function"

2. Update Permissions
We will need to edit the policy to add write permission to Firehose
On your new function, select the "Permissions" tab, and click on the Execution role Role name (it will open up a new window with IAM Manager)
In the Permissions Tab, you will see two attached policies, click "Add inline policy". 
In the Visual Editor add the following:
Service - Firehose
Actions - Write - PutRecordBatch
Resources - Either enter the ARN for your Firehose OR tick the "Any in this account"

Click Review Policy, and Save Changes

3. Copy the function code
Copy the function code from this repo, and replace/paste into your lambda function code, and then Deploy

4. Create Event on S3 Bucket
Navigate to your AWS S3 Firehose Error bucket in the console
On the Properties of the Bucket, Create event notification.
Give the event notification a name, and ensure you add the prefix "splunk-failed/" 
(note if you have added another prefix in your Firehose configuration, you will need to add that to this prefix, for example if you added FH as the prefix in the firehose config, you will need to add "FHsplunk-failed/" here)
Select the "All object create events" check box.
Select "Lambda Function" as the Destination, and select the Lambda Function you created in step 1 from the dropdown.
Save Changes

You are now all set with the function.

Note if you wish to use a different Firehose to re-ingest, you will need to have created this before Step 1.


# Current Limitations

The function will allow the extraction of messages that have been wrapped with additional metadata (noting sourcetype is set with a Project Trumpet configured firehose). This generally happens when a the lambda function in the Kinesis Firehose processing adds the additional information. As the re-ingest process through Firehose will also add its own event metadata,  only CloudTrail and ConfigNotifications are set with the correct sourcetpe with this function - you will need to add further ones as required.




