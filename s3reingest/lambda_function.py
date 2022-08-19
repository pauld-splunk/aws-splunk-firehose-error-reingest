import urllib.robotparser, boto3, json, re, base64
s3=boto3.client('s3')


def lambda_handler(event, context):
    
    bucket=event['Records'][0]['s3']['bucket']['name']
    key=urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    try:
        response=s3.get_object(Bucket=bucket, Key=key)
        
        text=response["Body"].read().decode()
        payload=""
        
        for line in text.split("\n"):
            if len(line)>0:
                data=json.loads(line)
                base64_message = data['rawData']
                base64_bytes = base64_message.encode('utf-8')
                message_bytes = base64.b64decode(base64_bytes)
                message = message_bytes.decode('utf-8')
                payload=payload+message+'\n'
        
        encoded_payload=payload.encode("utf-8")
        
        bucket_name = bucket
        file_name = key.split('/',1)[1] #drop the first part of the key (splunk-failed)
        s3_path = "SplashbackRawFailed/" + file_name
        
        print('writing to bucket:',bucket_name, ' s3_key:', s3_path)
        
        s3write = boto3.resource("s3")
        s3write.Bucket(bucket_name).put_object(Key=s3_path, Body=encoded_payload)        
        
        return 'Success!'
        
    except Exception as e:
        print(e)
        raise e
    

