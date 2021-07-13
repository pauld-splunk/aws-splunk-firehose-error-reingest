# Lambda Function to Re-Ingest Failed Firehose output to Splunk from S3 via Firehose

This function is a sample lambda function to assist with ingesting logs from AWS S3 that originally failed to write to Splunk via Firehose back via Firehose.

When Kinesis Firehose fails to write to Splunk via HEC (due to connection timeout, HEC token issues or other), it will write its logs into an S3 bucket. However, the contents of the logs in the bucket is not easily re-ingested into Splunk, as it is log contents is wrapped in additional information about the failure, and the original message base64 encoded. So for example, if using the AWS Splunk Add-On, it is not possible to decode the contents of the message.

(note there are 2 functions here - one for ingesting from S3, the other a lambda function for kinesis firehose)

This function is a simple solution to allow a re-ingest process to be possible. It should be triggered from these failed objects in S3, and will read and decode the payload, writing the output back into Firehose (same one or a different specific one to re-ingest, e.g. to a different Splunk instance). Care should be taken if re-ingesting back into the same Firehose in case that the reasons for failure to write to Splunk are not related to connectivity (you could flood your Firehose with a continuous error loop).
Also note that the function contains some logic to push out a re-ingested payload into S3 once the re-try has failed a maximum number of times. The messages will return to the original S3 bucket under the **SplashbackRawFailed/** prefix. This will keep sourcetypes from each of the firehoses that push to this re-try function separate.

This capability will prevent a "looping" scenario where the events are constantly re-ingested if the same firehose is used to "re-try", and if the connectivity is not re-established with Splunk. 

Note that this is a template example, that is based on re-ingesting from a Firehose configuration set up using Project Trumpet. It is assuming that a NEW Firehose data stream is set up to do the Re-ingest process itself. This is so that it can provide a generic solution for different sources of messages that pass through Firehose. (The format of the json messages that may come in via a different set-up may need some small changes to the construct of the re-ingested json payload.)
(see Project Trupet here - https://github.com/splunk/splunk-aws-project-trumpet)

Note that the "Splashback" S3 bucket where Firehose sends the failed messages also contains objects (with different prefixes) that would not necessarily be suitable to ingest from - for example, if there is a pre-processing function set up (a lambda function for the Firehose), the failiure could be caused there - these events will have a "processing-failed/" prefix. As additional processing would have been done to the payloads of these events, the contents of the "raw" event may not be what you wish to ingest into Splunk. This is why the Event notification for these functions should always include the prefix "splunk-failed/" to ensure that only those with a completed processing are read into Splunk via this "splashback" route.

## Setup Process

1. Create a new AWS Lambda Function (for kinesis processing)
(Author from scratch)<br>
Select Python 3.8 as the runtime<br>
Permissions - <br>
Create a new role with basic Lambda permissions<br>
Click on "Create function"<br>
Copy the function code <br>
Copy the function code from from the kinesis_lambda_function.py source this repo directory, and replace/paste into your lambda function code (copy into the function file - lambda_function.py).<br>
Increase the Timeout for the function to 5 minutes<br>
Deploy the function

2. Set up a new Kinesis Firehose for Re-ingesting
Create a new Kinesis Data Firehose delivery streams - <br>
Give the delivery stream a name <br>
Select "Direct PUT or other sources"<br>
Click Next<br>
Enable Transforming the records with Lambda<br>
Select the new lambda function created in step 1<br>
Click next<br>
Select Destination as Splunk (Third-party service provider -> Splunk)<br>
Enter the Splunk Cluster Endpoint URL<br>
Select Event endpoint <br>
Add Authentication token <br>
Either Create a New S3 bucket OR select an existing bucket for the destination of "Backup S3 bucket"<br>
Change the Timeout Period (Retry Duration) to a high value - suggest 600 seconds or above, so that it can give more time to retry the push to HEC <br>
Accept all other defaults for rest of configuration and Create delivery stream


3. Create a new AWS Lambda Function (for re-try processing) <br>
(Author from scratch)<br>
Select Python 3.8 as the runtime<br>
Permissions - <br>
Create a new role from AWS policy templates<br>
Give it a Role Name<br>
Select "Amazon S3 object read-only permissions" from the Policy Templates<br>

Click on "Create function"

4. Update Permissions<br>
We will need to edit the policy to add write permission to Firehose<br>
On your new function, select the "Permissions" tab, and click on the Execution role Role name (it will open up a new window with IAM Manager)<br>
In the Permissions Tab, you will see two attached policies, click "Add inline policy". <br>
In the Visual Editor add the following:<br>
Service - Firehose<br>
Actions - Write - PutRecordBatch<br>
Resources - Either enter the ARN for your Firehose OR tick the "Any in this account"<br>

Click Review Policy, and Save Changes

5. Copy the function code <br>
Copy the function code from from the lambda_function.py source this repo directory, and replace/paste into your lambda function code.<br>
Increase the Timeout for the function to 5 minutes

6. Update environment variables<br>
Add the two environment variables:<br>
**Firehose** - set the value to the name of the firehose that you wish to "reingesting" the messages <br>
**Region** - set the value of the AWS region where the firehose is set up <br>
(optional) **max_ingest** - set this to the number of times to re-ingest (perventing loops). If not set, defaults to 2 <br>
And then Deploy


7. Create Event on S3 Bucket<br>
Navigate to your AWS S3 Firehose Error bucket in the console (For the Source Kinesis Firehose)<br>
On the Properties of the Bucket, Create event notification.<br>
Give the event notification a name, and ensure you add the prefix "splunk-failed/" <br>
(note if you have added another prefix in your Firehose configuration, you will need to add that to this prefix, for example if you added FH as the prefix in the firehose config, you will need to add "FHsplunk-failed/" here)<br>
Select the "All object create events" check box.<br>
Select "Lambda Function" as the Destination, and select the Lambda Function you created in step 3 from the dropdown.<br>
Save Changes<br>

8. Repeat Step 7, but for the Retry Firehose S3 Backup bucket
Repeat the previous step, but this time, select the S3 bucket that was created / referred in step 2


You are now all set with the solution.



# Alternative Options

This example describes how the function can be triggered by the "error" objects being written to the Splashback S3 bucket. If there is a prolonged time of no connection to Splunk HEC, this could result in huge loops of data being re-ingested to Firehose. In most cases, the connectivity outage is short, and wouldn't cause issues. Where these cases are more likely to occur, it may be worth increasing the Firehose "Retry duration" on your Firehose configurations to minimise the initial write out to S3, or doing a mix of the two options provided here: <br>
Alternatively, this function could write to a Kinesis Stream - that would have more capacity to "queue" the events.

The function currently is launched from a trigger from a notification of an object in an S3 bucket. An alternative "batch" option could be to trigger execution from a periodic Cloudwatch Event trigger - the function could then be used to "flush" an SQS queue with Object notifications. This could potentially add a better "lag" in the re-try process to allow for connections to be re-established if there is a higher chance of a long disconnect. (Note that this is not documented / contained in the function here).

# Current Limitations

The function will allow the extraction of messages that have been set up using Project Trumpet as the creating method (noting sourcetype is set with a Project Trumpet configured firehose). The lambda function in the Kinesis Firehose processing adds additional information that is expected by the retry lambda function. If re-ingesting back into the originating Kinesis Firehose, that functin will need to add logic to copy the source, sourcetype, and frombucket values that are added to the payload on re-ingest. Failure to do this will result in losing the source, and also potentially run into an infinite loop if the Splunk instance never becomes available.

The function takes into consideration a "loop" scenario where data could potentially continiously re-ingest if there is no way of connecting back to Splunk HEC. Without this, it could essentially build up significant volumes in re-ingest and max-out the Firehose capacity. Increasing the Retry duration setting on Firehose can minimise this, but this will become an issue if Splunk becomes unavailable for a very long period. 