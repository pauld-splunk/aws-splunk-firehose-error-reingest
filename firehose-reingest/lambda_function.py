# Lambda function for reading from Firehose's "Splashback" Backup S3 Bucket.
# Function will read from S3 and write back to Firehose. 
# Ensure that the appropriate lambda function is enabled on the Firehose, otherwise the events will lose "source" and
# also potentially continiously loop if no connection to HEC is restored
# Function will Drop any unsent Events back into the ORIGINATING S3 Bucket. (after timeout)
# Uses 3 Environment variables - firehose, region, and max_ingest

import urllib.robotparser, boto3, json, re, base64, os
s3=boto3.client('s3')


def lambda_handler(event, context):
    
    bucket=event['Records'][0]['s3']['bucket']['name']
    key=urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    try:
        firehose_dest=os.environ['Firehose']
    except:
        print('Firehose environment variable not set!!')
        return
    try:
        region=os.environ['Region']
    except:
        print('Region variable not set!!')
        return
    try:
        max_ingest=int(os.environ['max_ingest'])
        if max_ingest>10:
            max_ingest=9 #do not ingest more than 9 times, even if set in environment
    except:
        max_ingest=2
    try:
        response=s3.get_object(Bucket=bucket, Key=key)
        
        client = boto3.client('firehose', region_name=region)
        streamName=firehose_dest
        
        text=response["Body"].read().decode()
        payload=""
        recordBatch=[]
        reingestjson={}
        destFH=0
        destS3=0
        s3payload={}
        reingest_count=1
        for line in text.split("\n"): #process every 'batch'
            dest='FH' #default destination will be FH
            if len(line)>0:
                data=json.loads(line)
                base64_message = data['rawData']
                base64_bytes = base64_message.encode('utf-8')
                message_bytes = base64.b64decode(base64_bytes)
                message = message_bytes.decode('utf-8')
                for messageline in message.split("\n"): #process every line of the batch
                    if len(messageline)>0:
                    
                        try:
                            dest='FH'
                            jsondata=json.loads(messageline)

                            #get the metadata
                            if jsondata.get('source')!=None:
                                source=jsondata['source']
                            else:
                                source='aws:reingested'
                            if jsondata.get('sourcetype')!=None:
                                st=jsondata['sourcetype']
                            else:
                                st='aws:firehose'
                            fieldsreingest={}
                            
                            if jsondata.get('fields')!=None:
                                
                                fieldsreingest=jsondata['fields'] #get reingest fields
                                reingest_count=int(fieldsreingest['reingest'])+1 #advance counter
                                
                                fieldsreingest['reingest']=str(reingest_count)
                                mbucket=fieldsreingest["frombucket"]
                            else: #fields not set, first reingest
                                
                                fieldsreingest["reingest"]='1'
                                fieldsreingest["frombucket"]=bucket
                                mbucket=bucket
                                reingest_count=1
                                
                            
                            if reingest_count > max_ingest:
                                #package up for S3
                                destS3+=1
                                if s3payload.get(mbucket)==None:
                                    s3payload[mbucket]=json.dumps(jsondata['event'])+'\n'
                                else:
                                    s3payload[mbucket]=s3payload[mbucket]+json.dumps(jsondata['event'])+'\n'
                                dest='S3'
                            else:
                                if jsondata.get('time')!=None:
                                    reingestjson= {'sourcetype':st, 'source':source, 'event':jsondata['event'], 'fields': fieldsreingest, 'time':jsondata['time']}
                                else:
                                    reingestjson= {'sourcetype':st, 'source':source, 'event':jsondata['event'], 'fields': fieldsreingest}
                                
                        except Exception as e:
                            print(e)
                            #reingestjson= {'reingest':jsondata['fields'], 'sourcetype':jsondata['sourcetype'], 'source':'reingest:'+str(reingest_count), 'detail-type':'Reingested Firehose Message','event':jsondata['event']}
                        
                        
                        if dest=='FH':
                            messageline=json.dumps(reingestjson)
                            message_bytes=messageline.encode('utf-8')
                            recordBatch.append({'Data':message_bytes})
                            destFH+=1
                            if destFH>499:
                                #flush max batch 
                                putRecordsToFirehoseStream(streamName, recordBatch, client, attemptsMade=0, maxAttempts=20)
                                destFH=0
                                recordBatch=[]
        #flush all        
        if destFH>0: 
            putRecordsToFirehoseStream(streamName, recordBatch, client, attemptsMade=0, maxAttempts=20)
        if destS3>0:
            print('Already re-ingested more than max attempts, will write to S3 to prevent looping')
            file_name = key
            s3_path = "SplashbackRawFailed/" + file_name
            for wbucket in s3payload:
                bucket_name=wbucket
                print('writing to bucket:',bucket_name, ' s3_key:', s3_path)
                s3write = boto3.resource("s3")
                s3write.Bucket(bucket_name).put_object(Key=s3_path, Body=s3payload[wbucket].encode("utf-8")) 
        
        return 'Success!'
        
    except Exception as e:
        print(e)
        raise e
    
def test_event(message):
    #if the event has had some processing, it may have additional json wrapper. The RAW event should be contained in "event"
    #this function will attempt to extract that raw event field - if there is an error, i.e. the content isn't a json, it will return the message as is
    try:
        data=json.loads(message)
        event=data['event']
        return json.dumps(event)
    
    except:
        return message
        




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


def test_event(message):
    #if the event has had some processing, it may have additional json wrapper. The RAW event should be contained in "event"
    #this function will attempt to extract that raw event field - if there is an error, i.e. the content isn't a json, it will return the message as is
    try:
        data=json.loads(message)
        event=data['event']
        return json.dumps(event)
    
    except:
        return message
        
