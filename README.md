# Lambda Function to Re-Ingest Failed Firehose output to Splunk from S3

This function is a sample lambda function to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

This function is a simple solution to allow an ingest process to be possible. It should be triggered from these failed objects, and will read and decode the payload, writing the output back into S3 (same bucket) in another prefixed object with *rawFailed/*. (Note that the event on the S3 bucket should exclude that prefix!)

These objects can then be ingested by the AWS Splunk Add-On using an SQS-based S3 input.


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
We will need to edit the policy to add write permission
On your new function, select the "Permissions" tab, and click on the Execution role Role name (it will open up a new window with IAM Manager)
In the Permissions Tab, you will see two attached policies, Click on the arrow next to the AWSLambdaS3ExecutionRole-xxxxx Policy
Edit the Policy, and use the JSON view.
Add "s3:PutObject" into the policy: it should now look like this:
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
<pre>

Click Review Policy, and Save Changes

3. Copy the function code
Copy the function code from this repo, and replace/paste into your lambda function code, and then Deploy


