import urllib.robotparser, boto3, json, re, base64
s3=boto3.client('s3')


def lambda_handler(event, context):
    
    bucket=event['Records'][0]['s3']['bucket']['name']
    key=urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    try:
        response=s3.get_object(Bucket=bucket, Key=key)
        
        client = boto3.client('firehose', region_name='eu-west-1')
        streamName='outtocloud'
        
        text=response["Body"].read().decode()
        payload=""
        recordBatch=[]
        reingestjson={}
        
        for line in text.split("\n"):
            if len(line)>0:
                data=json.loads(line)
                base64_message = data['rawData']
                base64_bytes = base64_message.encode('utf-8')
                message_bytes = base64.b64decode(base64_bytes)
                message = message_bytes.decode('utf-8')
                try:
                    jsondata=json.loads(message)
                    st=jsondata['sourcetype']
                    detail='Reingested Firehose Message'
                    if st=='aws:cloudtrail':
                        detail='AWS API Call via CloudTrail'
                    if st=='aws:config:notification':
                        detail='Config Configuration Item Change'
                    reingestjson= {'source':st, 'detail-type':detail,'detail':jsondata['event']}
                except:
                    reingestjson= {'source':'reingest', 'detail-type':'Reingested Firehose Message','detail':message}
                
                message=json.dumps(reingestjson)
                message_bytes=message.encode('utf-8')
                
                recordBatch.append({'Data':message_bytes})
        putRecordsToFirehoseStream(streamName, recordBatch, client, attemptsMade=0, maxAttempts=20)
        
        
        return 'Success!'
        
    except Exception as e:
        print(e)
        raise e
    

        
def putRecordsToFirehoseStream(streamName, records, client, attemptsMade, maxAttempts):
    failedRecords = []
    codes = []
    errMsg = ''
    # if put_record_batch throws for whatever reason, response['xx'] will error out, adding a check for a valid
    # response will prevent this
    response = None
    try:
        response = client.put_record_batch(DeliveryStreamName=streamName, Records=records)
    except Exception as e:
        failedRecords = records
        errMsg = str(e)

    # if there are no failedRecords (put_record_batch succeeded), iterate over the response to gather results
    if not failedRecords and response and response['FailedPutCount'] > 0:
        for idx, res in enumerate(response['RequestResponses']):
            # (if the result does not have a key 'ErrorCode' OR if it does and is empty) => we do not need to re-ingest
            if 'ErrorCode' not in res or not res['ErrorCode']:
                continue

            codes.append(res['ErrorCode'])
            failedRecords.append(records[idx])

        errMsg = 'Individual error codes: ' + ','.join(codes)

    if len(failedRecords) > 0:
        if attemptsMade + 1 < maxAttempts:
            print('Some records failed while calling PutRecordBatch to Firehose stream, retrying. %s' % (errMsg))
            putRecordsToFirehoseStream(streamName, failedRecords, client, attemptsMade + 1, maxAttempts)
        else:
            raise RuntimeError('Could not put records after %s attempts. %s' % (str(maxAttempts), errMsg))
